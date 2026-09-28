#!/usr/bin/env python3
"""
Scrape a conference website for its published roster: speakers, sponsors,
partners, exhibitors.

Why this exists
---------------
Every other script in this repo works from search queries and SERP snippets.
That finds the event. It does not tell you who is in the room.

Conferences publish that themselves — a speakers page with 175 names, titles
and companies is the single highest-value list in event-based prospecting, and
it is sitting in public HTML. This script reads it.

The rendering problem
---------------------
Conference sites split three ways, and you cannot tell which from the outside:

  1. Server-rendered HTML   -> requests would work
  2. JS-hydrated            -> requests returns an empty shell
  3. Behind a form or login -> nothing works, and you should stop trying

So this uses Playwright for everything (case 1 and 2 both work), and detects
case 3 explicitly instead of returning an empty CSV that looks like a bad
selector. A gate is a fact about the event, not a bug in the scraper — and the
honest response is to tell you which page is gated so you can go fill the form
in yourself.

Output is CONTACT_FIELDS, so it feeds straight into the rest of the pipeline:

    scrape_conference_roster.py  ->  enrich_conference_companies.py
                                 ->  find_linkedin_profiles.py
                                 ->  generate_event_report.py

Usage
-----
    # Point it at a roster page
    python -X utf8 -m scripts.scrape_conference_roster \\
        --url https://example.com/2026/speakers \\
        --event-name "Example Conference 2026" \\
        --output data/example-roster.csv

    # Or let it find the roster pages itself from the conference home page
    python -X utf8 -m scripts.scrape_conference_roster \\
        --site https://example.com \\
        --event-name "Example Conference 2026" \\
        --output data/example-roster.csv

Cost: nothing. It is your own browser.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from urllib.parse import urljoin, urlparse

from scripts.common import CONTACT_FIELDS, compact_text, dedupe_rows, write_csv

# Paths that tend to hold a roster. Ordered by how useful they usually are.
ROSTER_PATHS = [
    "speakers", "our-speakers", "featured-speakers", "presenters", "faculty",
    "sponsors", "partners", "our-sponsors", "exhibitors", "exhibitor-list",
    "attendees", "companies-attending", "who-attends", "advisory-board",
    "committee", "board", "judges", "mentors",
]

# Text that means "this page is gated", not "this page is empty".
GATE_MARKERS = [
    "get instant access", "fill out the form", "register to view",
    "sign in to view", "log in to view", "download the list",
    "complete the form", "unlock access", "request access",
]

# Job-title words. Used to tell a person block from a nav block.
TITLE_WORDS = re.compile(
    r"\b(ceo|cto|coo|cfo|cmo|cio|chief|founder|co-founder|president|vp|vice president|"
    r"director|head of|manager|lead|principal|partner|professor|dr\.?|md|phd|"
    r"executive|officer|owner|advisor|consultant|analyst|engineer|designer|"
    r"strategist|supervisor|coordinator|associate|senior|svp|evp|avp)\b",
    re.I,
)

# Nav/footer/CTA text that shows up inside cards and must not become a name.
NOISE = re.compile(
    r"^(view profile|read more|learn more|register|sponsor|about|contact|home|"
    r"agenda|speakers|menu|close|search|login|sign in|back|next|previous|"
    r"newsletter|faqs|community|content|apply|submit|share|download)$",
    re.I,
)


def _looks_like_name(text: str) -> bool:
    """A person's name: 2-5 capitalised words, no digits, not nav text."""
    t = text.strip()
    if not t or len(t) > 70 or NOISE.match(t):
        return False
    if any(ch.isdigit() for ch in t):
        return False
    words = [w for w in re.split(r"\s+", t) if w]
    if not (2 <= len(words) <= 6):
        return False
    # Allow "A. Polly Jessen", "Andrey Ostrovsky, MD, FAAP"
    caps = sum(1 for w in words if w[:1].isupper())
    return caps >= 2


def discover_roster_pages(page, site: str, verbose: bool = True) -> list[str]:
    """Find likely roster pages by reading the site's own navigation."""
    found: list[str] = []
    try:
        page.goto(site, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        hrefs = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.href)"
        )
    except Exception as exc:
        print(f"  could not read {site}: {str(exc)[:100]}", file=sys.stderr)
        return []

    host = urlparse(site).netloc
    for href in hrefs:
        if urlparse(href).netloc != host:
            continue
        path = urlparse(href).path.lower().rstrip("/")
        if any(path.endswith(p) or f"/{p}" in path for p in ROSTER_PATHS):
            clean = href.split("#")[0]
            if clean not in found:
                found.append(clean)

    if verbose:
        print(f"  found {len(found)} candidate roster pages")
        for f in found:
            print(f"    {f}")
    return found


def render(page, url: str, scrolls: int = 8, settle_ms: int = 3000) -> tuple[str, str]:
    """Load a page, scroll it to trigger lazy-loading, return (text, html)."""
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(settle_ms)
    last_height = 0
    for _ in range(scrolls):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(700)
        try:
            height = page.evaluate("document.body.scrollHeight")
            if height == last_height:
                break
            last_height = height
        except Exception:
            break
    # Some sites paginate rosters behind a "load more" button.
    for label in ["load more", "show more", "view all", "see all"]:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            for _ in range(10):
                if btn.count() == 0 or not btn.first.is_visible():
                    break
                btn.first.click(timeout=4000)
                page.wait_for_timeout(1800)
        except Exception:
            pass
    return page.inner_text("body"), page.content()


def detect_gate(text: str) -> str | None:
    """Return the gate phrase if this page is asking for a form/login."""
    low = text.lower()
    for marker in GATE_MARKERS:
        if marker in low:
            return marker
    return None


def _row(name, title, org, event_name, source_url, role_type, confidence) -> dict:
    return {
        "person_name": name,
        "title": title,
        "organization": org,
        "role_type": role_type,
        "event_name": event_name,
        "segment": "",
        "email": "",
        "phone": "",
        "linkedin_url": "",
        "facebook_url": "",
        "instagram_url": "",
        "website": "",
        "source": source_url,
        "confidence": confidence,
        "evidence": f"Listed on {source_url}",
        "next_action": "enrich",
    }


def find_card_anchor(lines: list[str]) -> str | None:
    """
    Find the repeating line that marks the start of each roster card.

    Roster pages are generated from a template, so every card carries the same
    call-to-action — "VIEW PROFILE", "Read Bio", "Learn More". That repetition
    is the most reliable structural signal on the page: far better than guessing
    which line is a job title, because it does not care what the content says.

    A line repeated 5+ times that is short and CTA-shaped is the anchor.
    """
    counts: dict[str, int] = {}
    for line in lines:
        if 3 <= len(line) <= 32:
            counts[line] = counts.get(line, 0) + 1
    candidates = [
        (n, l) for l, n in counts.items()
        if n >= 5 and re.search(
            r"view|read|learn|profile|bio|more|details|about",
            l, re.I,
        )
    ]
    if not candidates:
        return None
    return max(candidates)[1]


def _strip_credentials(text: str) -> str:
    """
    Remove trailing credentials so a name stops looking like a job title.

    "Jordan Avery, PhD" contains "PhD", which is also a title word. Without
    this, the parser reads the name as a title and shifts the whole card up by
    one line — producing a row whose "name" is the previous speaker's employer.
    """
    return re.sub(
        r",?\s*\b(PhD|Ph\.D\.?|MD|M\.D\.?|MBA|MPH|MSW|LCSW|RN|DO|DrPH|PsyD|"
        r"FAAP|FACHE|MHA|MS|MA|BSN|JD|CPA|LMFT|LPC|DNP|EdD|RPRS-CS|CPRS|DPA)\b",
        "", text, flags=re.I,
    ).strip(" ,")


def extract_people(text: str, event_name: str, source_url: str, role_type: str) -> list[dict]:
    """
    Pull (name, title, organization) triples out of rendered page text.

    Two strategies, in order of reliability:

    1. Card anchor. If every card starts with the same CTA line, split on it
       and read the next three lines as name / title / organization. This is
       structural, so it does not care whether a name contains "MD" or a title
       contains a comma.

    2. Title-word heuristic. No anchor found, so look for a line that reads
       like a job title and take the line above as the name. Credentials are
       stripped before the test so "Jordan Avery, PhD" is not mistaken for one.
    """
    lines = [compact_text(l) for l in text.split("\n")]
    lines = [l for l in lines if l]

    anchor = find_card_anchor(lines)
    people: list[dict] = []

    if anchor:
        idxs = [i for i, l in enumerate(lines) if l == anchor]
        for i in idxs:
            card = [l for l in lines[i + 1:i + 5] if l != anchor][:3]
            if not card:
                continue
            name = card[0]
            if not _looks_like_name(_strip_credentials(name)):
                continue
            title = card[1] if len(card) > 1 else ""
            org = card[2] if len(card) > 2 else ""
            # If the "title" is really the org (no title words and the next
            # line is missing), keep it as the org instead of inventing a title.
            if title and not org and not TITLE_WORDS.search(title):
                org, title = title, ""
            people.append(_row(
                name, title, org, event_name, source_url, role_type,
                "confirmed" if (title and org) else "probable",
            ))
        return people

    # Fallback: no repeating card marker on this page.
    lines = [l for l in lines if not NOISE.match(l)]
    for i, line in enumerate(lines):
        if len(line) > 130 or not TITLE_WORDS.search(_strip_credentials(line)):
            continue
        if _looks_like_name(_strip_credentials(line)) and not TITLE_WORDS.search(
            _strip_credentials(line).split(",")[0]
        ):
            continue  # this is a credentialed name, not a title
        name = lines[i - 1] if i >= 1 else ""
        if not _looks_like_name(_strip_credentials(name)):
            continue
        org = ""
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt and len(nxt) < 90 and not TITLE_WORDS.search(nxt):
                org = nxt
        people.append(_row(
            name, line, org, event_name, source_url, role_type,
            "confirmed" if org else "probable",
        ))
    return people


def extract_companies(page, text: str, event_name: str, source_url: str, role_type: str) -> list[dict]:
    """
    Pull sponsor/exhibitor companies out of a logo wall.

    Logo walls are images, so the company name lives in the alt text or the
    link target, not the visible text. That is exactly why this needs a real
    browser rather than an HTTP fetch.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    # The organiser's own domain must not become a "sponsor". Derive it from the
    # page we are reading rather than hardcoding one conference's host.
    own_host = urlparse(source_url).netloc.replace("www.", "")
    own_root = own_host.split(".")[0] if own_host else ""
    try:
        imgs = page.eval_on_selector_all(
            "img",
            "els => els.map(e => ({alt: e.alt || '', src: e.src || '', "
            "href: (e.closest('a') ? e.closest('a').href : '')}))",
        )
    except Exception:
        imgs = []

    for img in imgs:
        alt = compact_text(img.get("alt", ""))
        href = img.get("href", "") or ""
        name = ""
        # Prefer alt text; fall back to the outbound link's domain.
        if alt and 2 < len(alt) < 70 and not NOISE.match(alt):
            name = re.sub(r"\s*(logo|icon|image|photo)\s*$", "", alt, flags=re.I).strip()
        if not name and href:
            host = urlparse(href).netloc
            if host and own_root and own_root not in host and "." in host:
                name = host.replace("www.", "").split(".")[0].replace("-", " ").title()
        key = name.lower()
        if not name or key in seen or len(name) < 3:
            continue
        seen.add(key)
        rows.append({
            "person_name": "",
            "title": "",
            "organization": name,
            "role_type": role_type,
            "event_name": event_name,
            "segment": "",
            "email": "",
            "phone": "",
            "linkedin_url": "",
            "facebook_url": "",
            "instagram_url": "",
            "website": href if href and own_root and own_root not in href else "",
            "source": source_url,
            "confidence": "probable",
            "evidence": f"Logo on {source_url}",
            "next_action": "enrich",
        })
    return rows


def role_from_url(url: str) -> str:
    low = url.lower()
    for key, role in [
        ("speaker", "speaker"), ("presenter", "speaker"), ("faculty", "speaker"),
        ("sponsor", "sponsor"), ("partner", "sponsor"),
        ("exhibitor", "exhibitor"), ("attend", "attendee"),
        ("board", "organizer"), ("committee", "organizer"), ("judge", "organizer"),
    ]:
        if key in low:
            return role
    return "roster"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scrape a conference site for speakers, sponsors and exhibitors",
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", nargs="+", help="One or more roster page URLs")
    src.add_argument("--site", help="Conference home page — roster pages are discovered")
    ap.add_argument("--event-name", required=True, help='e.g. "Example Conference 2026"')
    ap.add_argument("--output", required=True, help="Output CSV path")
    ap.add_argument("--headed", action="store_true", help="Show the browser (useful for debugging)")
    ap.add_argument("--scrolls", type=int, default=8, help="Scroll passes per page (default 8)")
    ap.add_argument("--no-companies", action="store_true", help="Skip logo-wall company extraction")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        return 1

    rows: list[dict] = []
    gated: list[tuple[str, str]] = []
    started = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(
            viewport={"width": 1440, "height": 2200},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"),
        )

        urls = args.url or []
        if args.site:
            print(f"Discovering roster pages on {args.site}")
            urls = discover_roster_pages(page, args.site)
            if not urls:
                print("  none found — pass --url with the roster page directly", file=sys.stderr)

        for url in urls:
            role = role_from_url(url)
            print(f"\nReading {url}  (role: {role})")
            try:
                text, _html = render(page, url, scrolls=args.scrolls)
            except Exception as exc:
                print(f"  failed: {str(exc)[:140]}", file=sys.stderr)
                continue

            gate = detect_gate(text)
            if gate:
                gated.append((url, gate))
                print(f"  GATED — page says \"{gate}\". Nothing to scrape here.")

            people = extract_people(text, args.event_name, url, role)
            print(f"  {len(people)} people")
            rows.extend(people)

            if not args.no_companies:
                companies = extract_companies(page, text, args.event_name, url, role)
                # Only keep logo-wall companies on sponsor/exhibitor pages —
                # on a speakers page every headshot alt would become a "company".
                if role in {"sponsor", "exhibitor", "attendee"}:
                    print(f"  {len(companies)} companies from logos")
                    rows.extend(companies)

        browser.close()

    rows = dedupe_rows(rows, ["person_name", "organization", "event_name"])
    write_csv(args.output, rows, CONTACT_FIELDS)

    people_n = sum(1 for r in rows if r["person_name"])
    orgs = {r["organization"] for r in rows if r["organization"]}
    print(f"\n{'='*66}")
    print(f"{len(rows)} rows -> {args.output}")
    print(f"  {people_n} named people")
    print(f"  {len(orgs)} distinct organizations")
    print(f"  {time.time() - started:.0f}s, $0.00")

    if gated:
        print("\nGated pages — a form or login stands between you and this list:")
        for url, marker in gated:
            print(f"  {url}\n    (\"{marker}\")")
        print("  These are worth filling in by hand. You are a real prospective")
        print("  attendee, so the form is the intended way in — and the list you")
        print("  get back is usually the exhibitor list, which is the best one.")

    if rows:
        print("\nNext: enrich these organizations into named decision-makers ->")
        print(f"  python -X utf8 -m scripts.enrich_conference_companies --input {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
