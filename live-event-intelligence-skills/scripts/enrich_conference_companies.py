#!/usr/bin/env python3
"""
Turn a conference roster into named decision-makers with LinkedIn URLs and
verified emails.

The problem this solves
-----------------------
A sponsor logo wall gives you 186 company names. That is not a lead list —
you cannot email "Brightside Health". You need the person inside it whose job
is the thing you sell, their LinkedIn, and an address that will not bounce.

Four layers, each independently skippable, cheapest first:

  1. Website        find the company's real domain               free (Tavily)
  2. People         find the decision-makers by role             free (Tavily)
  3. LinkedIn       match each name to a profile URL             free (Exa)
  4. Email          find and SMTP-verify an address              Apify, paid

Layers 1-3 run on free tiers. Layer 4 costs money and is off unless you ask
for it, because verifying 186 companies' worth of contacts is the only step
here that can surprise you with a bill.

Why Tavily for search and Exa for LinkedIn
------------------------------------------
They are good at different things. Tavily answers "who runs marketing at this
company" as a search engine would. Exa is embedding-based and is markedly
better at "which LinkedIn profile is this exact person", which is the step
where a keyword engine confidently hands you the wrong Sarah Chen.

Both have generous free tiers. Neither needs a card.

Usage
-----
    # Free layers only: website, people, LinkedIn
    python -X utf8 -m scripts.enrich_conference_companies \\
        --input data/example-sponsors.csv \\
        --output data/example-enriched.csv \\
        --roles "VP Marketing" "Head of Brand" "Chief Marketing Officer"

    # Add paid email discovery + SMTP verification
    python -X utf8 -m scripts.enrich_conference_companies \\
        --input data/example-sponsors.csv \\
        --output data/example-enriched.csv \\
        --roles "VP Marketing" --emails --verify-emails --limit 25

Always --limit first. Read the output. Then scale.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from scripts.common import (
    CONTACT_FIELDS,
    compact_text,
    dedupe_rows,
    load_env,
    read_csv,
    write_csv,
)

LINKEDIN_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")

# Default roles. Override with --roles for your own offer: a web designer wants
# marketing, a compliance vendor wants legal, a recruiter wants HR.
DEFAULT_ROLES = [
    "Chief Marketing Officer",
    "VP of Marketing",
    "Head of Brand",
    "Director of Communications",
    "Founder",
]

FREE_MAIL = re.compile(r"@(gmail|yahoo|outlook|hotmail|icloud|aol|proton)\.", re.I)
JUNK_DOMAIN = re.compile(
    r"(linkedin|facebook|twitter|instagram|youtube|wikipedia|crunchbase|"
    r"bloomberg|glassdoor|indeed|zoominfo|apollo|pitchbook)\.", re.I
)


def _keys(prefix: str) -> list[str]:
    """Collect KEY, KEY_2, KEY_3 ... so an exhausted key rotates to the next."""
    out = []
    for name in [prefix] + [f"{prefix}_{i}" for i in range(2, 11)]:
        v = os.getenv(name)
        if v and v.strip():
            out.append(v.strip())
    return out


def tavily(query: str, max_results: int = 5) -> dict:
    """Search via Tavily, rotating keys when one hits its monthly cap."""
    import requests

    keys = _keys("TAVILY_API_KEY")
    if not keys:
        return {"error": "no_key"}
    for key in keys:
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "include_answer": True,
                },
                timeout=30,
            )
            if r.status_code in (401, 403, 429, 432):
                continue  # exhausted or rejected — try the next key
            r.raise_for_status()
            return r.json()
        except Exception:
            continue
    return {"error": "all_keys_exhausted"}


def _slug_matches(person: str, url: str) -> bool:
    """
    Does this LinkedIn URL actually belong to this person?

    A neural search will happily return a plausible-looking profile for a name
    it has never seen. Attaching that URL to a contact is worse than returning
    nothing: the row looks complete, so nobody checks it, and the outreach goes
    to a stranger. So the surname must appear in the profile slug or we drop
    the URL entirely.
    """
    # Drop credentials so "Cara McNulty, DPA" compares as "Cara McNulty".
    cleaned = re.sub(
        r"\b(PhD|MD|MBA|MPH|MSW|LCSW|RN|DO|PsyD|FAAP|DPA|JD|CPA|MS|MA)\b",
        "", person, flags=re.I,
    )
    parts = [p for p in re.split(r"[\s,]+", cleaned) if len(p) > 1]
    if len(parts) < 2:
        return False
    surname = re.sub(r"[^a-z]", "", parts[-1].lower())
    first = re.sub(r"[^a-z]", "", parts[0].lower())
    slug = re.sub(r"[^a-z]", "", url.rsplit("/", 1)[-1].lower())
    if len(surname) < 3 or len(first) < 2:
        return False
    # BOTH names must be present. Surname alone is not enough: an uncommon
    # surname is often an uncommon *family*, so "Alex Marchetti-Vaughn" happily
    # matched "brian-marchetti-vaughn" — the right household, wrong person, and
    # a message that lands as obviously automated.
    return surname in slug and first in slug


def exa_find_linkedin(person: str, company: str) -> tuple[str, str]:
    """
    Match a person to their LinkedIn profile URL. Returns (url, confidence).

    Returns ("", "") rather than a guess when the surname does not appear in
    the profile slug. An empty cell is honest; a wrong cell is a wrong email.
    """
    import requests

    keys = _keys("EXA_API_KEY")
    if not keys:
        return "", ""
    query = f"{person} {company} LinkedIn"
    for key in keys:
        try:
            r = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "numResults": 10,
                    "includeDomains": ["linkedin.com"],
                    "type": "neural",
                },
                timeout=30,
            )
            if r.status_code in (401, 403, 429):
                continue
            r.raise_for_status()
            for item in r.json().get("results", []):
                url = item.get("url", "")
                # Only real profile pages. /posts/ and /company/ are not people.
                m = LINKEDIN_RE.search(url)
                if not m or "/posts/" in url:
                    continue
                clean = m.group(0)
                if _slug_matches(person, clean):
                    return clean, "confirmed"
            return "", ""
        except Exception:
            continue
    return "", ""


def find_company_website(company: str) -> str:
    """Resolve a company name to its real domain."""
    data = tavily(f"{company} official website", max_results=5)
    if data.get("error"):
        return ""
    for item in data.get("results", []):
        url = item.get("url", "")
        host = urlparse(url).netloc
        if host and not JUNK_DOMAIN.search(host):
            return f"https://{host}"
    return ""


# Words that never appear inside a real person's name. Mining names out of
# search-result prose picks up fragments like "with sports marketing" or
# "combine design" without a list like this.
NOT_A_NAME = re.compile(
    r"\b(the|and|for|our|new|with|from|this|that|your|their|about|more|health|"
    r"care|inc|llc|ltd|corp|group|team|company|solutions|services|partners|"
    r"marketing|design|brand|sales|read|view|learn|see|join|click|posts?|"
    r"today|latest|news|announces|launches|welcome|meet|introducing)\b",
    re.I,
)


def _is_person_name(text: str) -> bool:
    """
    Strict: does this look like an actual human name?

    Deliberately conservative. A missed contact costs one row; a fabricated one
    costs a misdirected email and, if it reaches the wrong person at a company
    you are courting, a bit of credibility.
    """
    t = compact_text(text).strip(" ,.-")
    if not t or len(t) > 45 or NOT_A_NAME.search(t):
        return False
    words = [w for w in t.split() if w]
    if not (2 <= len(words) <= 4):
        return False
    # Every word starts uppercase and is alphabetic (allow O'Brien, Smith-Jones)
    for w in words:
        core = w.strip(".,")
        if not core or not core[0].isupper():
            return False
        if not re.fullmatch(r"[A-Za-z][A-Za-z'\-\.]*", core):
            return False
    return True


def find_people(company: str, roles: list[str], per_role: int = 1) -> list[dict]:
    """
    Find named decision-makers at a company for the given roles.

    Reads the search result TITLES rather than the body prose. A LinkedIn or
    company-bio result title has a predictable shape — "Jane Doe - VP Marketing
    - Acme" — whereas body text is arbitrary sentences, and mining names out of
    arbitrary sentences is how you end up with a contact called "combine design".
    """
    found: list[dict] = []
    seen: set[str] = set()

    for role in roles:
        data = tavily(f'"{company}" "{role}" LinkedIn', max_results=6)
        if data.get("error"):
            break
        hits = 0
        company_low = company.lower().strip()
        for item in data.get("results", []):
            title = compact_text(item.get("title", ""))
            if not title:
                continue
            parts = [p.strip() for p in re.split(r"\s+[-–|]\s+", title) if p.strip()]
            head = parts[0] if parts else ""
            tail = parts[-1] if parts else ""
            for idx, candidate in ((0, head), (len(parts) - 1, tail)):
                name = compact_text(candidate).strip(" ,.-")
                if not _is_person_name(name) or name.lower() in seen:
                    continue
                # The company's own name is not a person.
                if name.lower() == company_low or name.lower() in company_low:
                    continue
                # The result must actually be about this company or this role.
                blob = f"{title} {item.get('content','')}".lower()
                if company.split()[0].lower() not in blob and role.lower() not in blob:
                    continue
                # Their REAL title is the segment next to the name, when the
                # source gives one. Recording the role we searched for instead
                # would assert something we never confirmed.
                real_title = ""
                neighbour = parts[idx + 1] if idx == 0 and len(parts) > 1 else (
                    parts[-2] if idx and len(parts) > 1 else ""
                )
                if neighbour and not _is_person_name(neighbour) and len(neighbour) < 70:
                    if company.split()[0].lower() not in neighbour.lower():
                        real_title = neighbour
                seen.add(name.lower())
                found.append({
                    "person_name": name,
                    "title": real_title or role,
                    "matched_role": role,
                    "title_confirmed": bool(real_title),
                })
                hits += 1
                break
            if hits >= per_role:
                break
    return found


def find_email_apify(person: str, company: str, domain: str, verify: bool) -> tuple[str, str]:
    """
    Find and optionally verify an email via Apify. This is the paid layer.

    Returns (email, status).
    """
    import requests

    token = os.getenv("APIFY_API_TOKEN") or ""
    if not token or not domain:
        return "", ""
    host = urlparse(domain).netloc or domain
    try:
        r = requests.post(
            "https://api.apify.com/v2/acts/"
            "snipercoder~decision-maker-email-finder/run-sync-get-dataset-items",
            params={"token": token},
            json={"domains": [host], "names": [person]},
            timeout=180,
        )
        if r.status_code >= 400:
            return "", f"apify_{r.status_code}"
        for item in r.json() or []:
            for value in item.values():
                if isinstance(value, str):
                    m = EMAIL_RE.search(value)
                    if m and not FREE_MAIL.search(m.group(0)):
                        return m.group(0), "found"
        return "", "not_found"
    except Exception as exc:
        return "", f"error:{str(exc)[:40]}"


def enrich_one(row: dict, roles: list[str], want_emails: bool, verify: bool) -> list[dict]:
    """Run the enrichment layers for a single company row."""
    company = (row.get("organization") or "").strip()
    if not company:
        return []

    website = (row.get("website") or "").strip()
    if not website or JUNK_DOMAIN.search(website):
        website = find_company_website(company)

    people = find_people(company, roles)
    if not people:
        # Keep the company even with no named contact — it is still a booth to
        # visit. Silently dropping it would hide real coverage gaps.
        out = dict(row)
        out.update({
            "website": website,
            "confidence": "weak",
            "evidence": f"{row.get('evidence','')} | no named contact found".strip(" |"),
            "next_action": "research-manually",
        })
        return [out]

    results = []
    for p in people:
        linkedin, conf = exa_find_linkedin(p["person_name"], company)
        email, status = ("", "")
        if want_emails:
            email, status = find_email_apify(p["person_name"], company, website, verify)
        out = dict(row)
        # Say plainly whether the title is theirs or just what we searched for.
        title_note = (
            "title from source"
            if p.get("title_confirmed")
            else f"title unconfirmed; matched on search for '{p.get('matched_role','')}'"
        )
        out.update({
            "person_name": p["person_name"],
            "title": p["title"],
            "organization": company,
            "segment": p.get("matched_role", ""),
            "website": website,
            "linkedin_url": linkedin,
            "email": email,
            "confidence": conf or ("probable" if linkedin else "weak"),
            "evidence": compact_text(
                f"{row.get('evidence','')} | {title_note}"
                + (f" | email {status}" if status else "")
            ),
            "next_action": "outreach" if (linkedin or email) else "verify-before-outreach",
        })
        results.append(out)
    return results


def run_linkedin_only(args) -> int:
    """
    Match LinkedIn profiles for people we already have names for.

    A speaker list arrives complete — name, title, company, straight from the
    conference's own site. There is nothing to discover, so the expensive
    "who works here" step is wasted on it. This does the one thing that is
    actually missing, using only Exa's free tier.
    """
    rows = read_csv(args.input)
    targets = [r for r in rows if (r.get("person_name") or "").strip()]
    if args.limit:
        targets = targets[:args.limit]

    if not _keys("EXA_API_KEY"):
        print("This mode needs EXA_API_KEY. Free at https://exa.ai", file=sys.stderr)
        return 1

    print(f"Matching LinkedIn profiles for {len(targets)} known people")
    started = time.time()
    done: list[dict] = []

    def one(row: dict) -> dict:
        out = dict(row)
        url, conf = exa_find_linkedin(
            row.get("person_name", ""), row.get("organization", "")
        )
        if url:
            out["linkedin_url"] = url
            out["confidence"] = conf
            out["next_action"] = "outreach"
            out["evidence"] = compact_text(
                f"{row.get('evidence','')} | LinkedIn matched, surname verified in slug"
            )
        else:
            out["next_action"] = "find-linkedin-manually"
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, r): r for r in targets}
        for i, fut in enumerate(as_completed(futures), 1):
            person = (futures[fut].get("person_name") or "?")[:32]
            try:
                r = fut.result()
                done.append(r)
                mark = "found" if r.get("linkedin_url") else "-"
                print(f"  [{i}/{len(targets)}] {person:<34} {mark}")
            except Exception as exc:
                print(f"  [{i}/{len(targets)}] {person:<34} FAILED: {str(exc)[:50]}")
                done.append(dict(futures[fut]))

    # Keep any rows we did not touch (e.g. company-only rows) so the file stays whole.
    touched = {(r.get("person_name") or "").lower() for r in done}
    done.extend(r for r in rows
                if (r.get("person_name") or "").lower() not in touched)

    write_csv(args.output, done, CONTACT_FIELDS)
    hits = sum(1 for r in done if (r.get("linkedin_url") or "").strip())
    print(f"\n{'='*66}")
    print(f"{len(done)} rows -> {args.output}")
    print(f"  {hits} LinkedIn profiles matched and surname-verified")
    print(f"  {time.time() - started:.0f}s, $0.00")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Enrich conference companies into named decision-makers",
    )
    ap.add_argument("--input", required=True, help="Roster CSV from scrape_conference_roster.py")
    ap.add_argument("--output", required=True)
    ap.add_argument("--roles", nargs="+", default=DEFAULT_ROLES,
                    help="Job titles to look for. Set these to match what YOU sell.")
    ap.add_argument("--limit", type=int, help="Only process the first N companies. Use this first.")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--emails", action="store_true", help="PAID: find emails via Apify")
    ap.add_argument("--verify-emails", dest="verify", action="store_true",
                    help="PAID: SMTP-verify each email before you send to it")
    ap.add_argument("--skip-known", action="store_true",
                    help="Skip rows that already have a person_name (companies only)")
    ap.add_argument("--linkedin-only", dest="linkedin_only", action="store_true",
                    help="Rows already have names (e.g. a speaker list) — just find "
                         "each person's LinkedIn URL. Free, and the fastest win available.")
    args = ap.parse_args()

    load_env()

    if args.linkedin_only:
        return run_linkedin_only(args)

    if not _keys("TAVILY_API_KEY"):
        print("No TAVILY_API_KEY set. Free at https://tavily.com — 1,000/month, no card.",
              file=sys.stderr)
        return 1
    if not _keys("EXA_API_KEY"):
        print("Note: no EXA_API_KEY. LinkedIn matching will be skipped.\n"
              "      Free at https://exa.ai — it is by far the best step for this.",
              file=sys.stderr)

    rows = read_csv(args.input)
    if args.skip_known:
        rows = [r for r in rows if not (r.get("person_name") or "").strip()]
    # One row per company; the roster may list a company several times.
    seen: set[str] = set()
    companies = []
    for r in rows:
        key = (r.get("organization") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            companies.append(r)
    if args.limit:
        companies = companies[:args.limit]

    if args.emails:
        est = len(companies) * len(args.roles) * 0.02
        print(f"Email discovery is ON for {len(companies)} companies. Rough cost: ${est:.2f}")

    print(f"Enriching {len(companies)} companies for roles: {', '.join(args.roles)}")
    started = time.time()
    out_rows: list[dict] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(enrich_one, c, args.roles, args.emails, args.verify): c
            for c in companies
        }
        for i, fut in enumerate(as_completed(futures), 1):
            company = (futures[fut].get("organization") or "?")[:34]
            try:
                got = fut.result()
                out_rows.extend(got)
                named = sum(1 for g in got if g.get("person_name"))
                li = sum(1 for g in got if g.get("linkedin_url"))
                print(f"  [{i}/{len(companies)}] {company:<36} {named} contacts, {li} LinkedIn")
            except Exception as exc:
                print(f"  [{i}/{len(companies)}] {company:<36} FAILED: {str(exc)[:60]}")

    out_rows = dedupe_rows(out_rows, ["person_name", "organization"])
    write_csv(args.output, out_rows, CONTACT_FIELDS)

    named = sum(1 for r in out_rows if r.get("person_name"))
    with_li = sum(1 for r in out_rows if r.get("linkedin_url"))
    with_em = sum(1 for r in out_rows if r.get("email"))
    print(f"\n{'='*66}")
    print(f"{len(out_rows)} rows -> {args.output}")
    print(f"  {named} named contacts")
    print(f"  {with_li} with a LinkedIn profile")
    if args.emails:
        print(f"  {with_em} with an email")
    print(f"  {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
