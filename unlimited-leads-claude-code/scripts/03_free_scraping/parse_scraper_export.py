#!/usr/bin/env python3
"""
Pull emails, phones, handles, and URLs out of a messy scraper export.

Instant Data Scraper gives you a CSV with whatever columns the page happened to
have — usually a few wide cells of run-together text with the useful bits buried
inside. This finds them.

Regex only by default, so it costs nothing and runs offline. `--llm` adds a
Claude pass for the leftovers, which is worth it when the bios are free-text
("reach me at hello (at) shop dot com") and the regex can't see through the
obfuscation.

Usage:
    python -X utf8 scripts/03_free_scraping/parse_scraper_export.py \\
        --input ~/Downloads/instant-data-scraper.csv \\
        --out-csv output/free_leads.csv
"""

import os
import re
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.env import load_env
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import read_any, write_csv, write_json

fix_encoding()
load_env()

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
HANDLE_RE = re.compile(r"(?<![\w/])@([A-Za-z0-9._]{3,30})\b")
URL_RE = re.compile(r"https?://[^\s,\"'<>）)]+")

# Addresses that show up on every page and belong to the platform, not a lead.
JUNK_EMAIL = re.compile(
    r"@(example|sentry|wix|squarespace|godaddy|shopify|facebook|instagram|google|"
    r"gstatic|schema|w3|youtube|linkedin|cloudflare|jquery)\.",
    re.I,
)
JUNK_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js|ico|woff2?)$", re.I)


def deobfuscate(text: str) -> str:
    """Undo the usual tricks people use to hide an address from scrapers."""
    t = text
    t = re.sub(r"\s*\(\s*at\s*\)\s*|\s+at\s+(?=\w+\s*(\(|\[)?\s*dot)", "@", t, flags=re.I)
    t = re.sub(r"\s*\[\s*at\s*\]\s*", "@", t, flags=re.I)
    t = re.sub(r"\s*\(\s*dot\s*\)\s*|\s*\[\s*dot\s*\]\s*", ".", t, flags=re.I)
    t = re.sub(r"\s+dot\s+", ".", t, flags=re.I)
    return t


def extract(row: dict) -> dict:
    """Find every contact detail anywhere in the row."""
    blob = " ".join(str(v) for v in row.values() if v)
    clean = deobfuscate(blob)

    emails = []
    for e in EMAIL_RE.findall(clean):
        e = e.strip(".,;:").lower()
        if JUNK_EMAIL.search(e) or JUNK_EXT.search(e):
            continue
        if e not in emails:
            emails.append(e)

    phones = []
    for p in PHONE_RE.findall(blob):
        digits = re.sub(r"\D", "", p)
        if len(digits) in (10, 11) and digits not in [re.sub(r"\D", "", x) for x in phones]:
            phones.append(p.strip())

    handles = [h for h in dict.fromkeys(HANDLE_RE.findall(blob)) if not h.isdigit()]

    urls, socials = [], {}
    for u in dict.fromkeys(URL_RE.findall(blob)):
        u = u.rstrip(".,);")
        if JUNK_EXT.search(u):
            continue
        low = u.lower()
        for platform in ("instagram", "facebook", "linkedin", "tiktok", "twitter", "x.com", "yelp"):
            if platform in low and platform not in socials:
                socials[platform.replace(".com", "")] = u
                break
        else:
            urls.append(u)

    # The best guess at a business name: the longest short-ish text cell.
    name = ""
    for v in row.values():
        s = str(v or "").strip()
        if 3 < len(s) < 70 and not EMAIL_RE.search(s) and not s.startswith("http") and len(s) > len(name):
            name = s

    return {
        "business_name": name,
        "email": emails[0] if emails else "",
        "all_emails": ", ".join(emails),
        "phone": phones[0] if phones else "",
        "handle": f"@{handles[0]}" if handles else "",
        "website": urls[0] if urls else "",
        "instagram": socials.get("instagram", ""),
        "facebook": socials.get("facebook", ""),
        "linkedin": socials.get("linkedin", ""),
        "_source": "free-scraping",
    }


def llm_pass(rows: list[dict], originals: list[dict], model: str) -> list[dict]:
    """Ask Claude to read the rows the regex found nothing in."""
    from scripts.lib.claude import structured

    schema = {
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "website": {"type": "string"},
        },
        "required": ["business_name", "email", "phone", "website"],
        "additionalProperties": False,
    }
    system = (
        "You extract contact details from messy scraped text. Return only what is "
        "actually present — never guess, never construct an address from a name and "
        "a domain. If a field is not there, return an empty string."
    )

    fixed = 0
    for i, row in enumerate(rows):
        if row["email"] or row["phone"]:
            continue
        blob = " ".join(str(v) for v in originals[i].values() if v)[:3000]
        if len(blob) < 20:
            continue
        try:
            got = structured(system=system, user=blob, schema=schema, model=model, max_tokens=512)
            for k in ("business_name", "email", "phone", "website"):
                if got.get(k) and not row.get(k):
                    row[k] = got[k]
            if row["email"] or row["phone"]:
                fixed += 1
        except Exception:
            continue
    print(f"  LLM pass recovered contacts for {fixed} more rows")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Extract contacts from a scraper CSV export (System 3, step 2)")
    parser.add_argument("--input", required=True, help="CSV or JSON from Instant Data Scraper")
    parser.add_argument("--out-csv", dest="out_csv", help="Output CSV (default: <input>_parsed.csv)")
    parser.add_argument("--out-json", dest="out_json", help="Also write JSON here")
    parser.add_argument("--llm", action="store_true",
                        help="Use Claude on rows the regex missed (costs ~$0.001/row, needs ANTHROPIC_API_KEY)")
    parser.add_argument("--model", default="claude-opus-5", help="Claude model for --llm")
    parser.add_argument("--keep-empty", dest="keep_empty", action="store_true",
                        help="Keep rows with no email and no phone")
    args = parser.parse_args()

    raw = read_any(args.input)
    print(f"Read {len(raw)} rows from {args.input}")

    parsed = [extract(r) for r in raw]
    if args.llm:
        print("Running the LLM pass on rows the regex missed...")
        parsed = llm_pass(parsed, raw, args.model)

    # Dedupe on email, then phone, then name.
    seen, unique = set(), []
    for r in parsed:
        key = r["email"] or r["phone"] or r["business_name"]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(r)

    if not args.keep_empty:
        kept = [r for r in unique if r["email"] or r["phone"]]
        print(f"Dropped {len(unique) - len(kept)} rows with no email and no phone (--keep-empty to keep them)")
        unique = kept

    out_csv = args.out_csv or args.input.rsplit(".", 1)[0] + "_parsed.csv"
    write_csv(unique, out_csv)
    print(f"\n{len(unique)} contacts saved to {out_csv}")
    if args.out_json:
        write_json(unique, args.out_json)
        print(f"JSON saved to {args.out_json}")

    with_email = sum(1 for r in unique if r["email"])
    with_phone = sum(1 for r in unique if r["phone"])
    print(f"  {with_email} have an email, {with_phone} have a phone")


if __name__ == "__main__":
    main()
