#!/usr/bin/env python3
"""
SYSTEM 3 — Build Google search queries that surface exposed contact details.

Free. No API keys, no credits, no account. This runs offline.

The course teaches one operator:

    site:instagram.com "barber" "gmail.com" OR "yahoo.com" OR "outlook.com"

The idea: people put their email in their bio. Google has indexed those bios.
So instead of paying a database for contact details, ask Google for the pages
that already show them. This script builds that query and about a dozen useful
variants, then prints the Instant Data Scraper walkthrough for turning the
results page into a CSV.

Usage:
    python -X utf8 scripts/03_free_scraping/build_dorks.py \\
        --niche "barber" --location "Tuscaloosa AL"

    python -X utf8 scripts/03_free_scraping/build_dorks.py \\
        --niche "roofing contractor" --location "Mobile AL" \\
        --platforms instagram facebook linkedin --output output/dorks.md
"""

import os
import sys
import argparse
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import ensure_dir

fix_encoding()

PLATFORMS = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "linkedin": "linkedin.com/in",
    "yelp": "yelp.com",
    "x": "x.com",
    "tiktok": "tiktok.com",
}

PROVIDERS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]


def google_url(query: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query) + "&num=100"


def build(niche: str, location: str, platforms: list[str], providers: list[str]) -> list[tuple[str, str]]:
    """Return [(label, query), ...]."""
    email_or = " OR ".join(f'"{p}"' for p in providers)
    loc = f' "{location}"' if location else ""
    out: list[tuple[str, str]] = []

    for p in platforms:
        domain = PLATFORMS.get(p, p)
        out.append((
            f"{p} — bios with an email",
            f'site:{domain} "{niche}" {email_or}',
        ))
        if location:
            out.append((
                f"{p} — bios with an email, in {location}",
                f'site:{domain} "{niche}"{loc} {email_or}',
            ))

    # Not platform-specific: business sites that leak an address on a contact page.
    out.append((
        "Any website — contact pages",
        f'"{niche}"{loc} ("contact us" OR "get in touch") {email_or}',
    ))
    out.append((
        "Any website — the owner's own address",
        f'"{niche}"{loc} ("owner" OR "founder" OR "proprietor") {email_or}',
    ))
    out.append((
        "Directories and association member lists",
        f'"{niche}"{loc} ("member directory" OR "our members" OR "find a {niche}")',
    ))
    out.append((
        "PDFs — member lists and sponsor sheets leak contacts constantly",
        f'filetype:pdf "{niche}"{loc} {email_or}',
    ))
    out.append((
        "Phone numbers instead of emails",
        f'"{niche}"{loc} ("call us" OR "phone") -site:yelp.com -site:yellowpages.com',
    ))
    return out


WALKTHROUGH = """
## Turning a results page into a CSV

You need the **Instant Data Scraper** extension (free, Chrome or Brave).

1. Install it: search the Chrome Web Store for "Instant Data Scraper".
2. Run one of the queries above. Add `&num=100` to the URL — it's already in the
   links below — so you get 100 results a page instead of 10.
3. Click the extension. It guesses which table on the page holds the data;
   if it guesses wrong, click "Try another table" until the preview looks right.
4. Click **Locate "Next" button**, then click Google's Next link when it asks.
5. Click **Start crawling**. Let it page through.
6. Click **CSV** to download.

Then pull the emails out of that CSV:

    python -X utf8 scripts/03_free_scraping/parse_scraper_export.py \\
        --input ~/Downloads/instant-data-scraper.csv \\
        --out-csv output/free_leads.csv

Total cost: nothing.

## Making these work harder

- Search one city at a time. "barber Alabama" returns noise; "barber Tuscaloosa"
  returns businesses.
- Swap the niche word for what they call themselves. Plumbers say "plumbing";
  lawyers say "attorney" or "law firm", rarely "lawyer".
- `-site:yelp.com -site:yellowpages.com` strips out the aggregators so you get
  the businesses themselves.
- If a query returns nothing, drop the location first, then drop a provider.
  Too many quoted terms and Google finds no page containing all of them.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Build free Google search queries that surface contact details (System 3)",
    )
    parser.add_argument("--niche", required=True, help='What they do, e.g. "barber", "roofing contractor"')
    parser.add_argument("--location", default="", help='City and state, e.g. "Tuscaloosa AL"')
    parser.add_argument("--platforms", nargs="+", default=["instagram", "facebook", "linkedin"],
                        choices=list(PLATFORMS.keys()), help="Which platforms to target")
    parser.add_argument("--providers", nargs="+", default=PROVIDERS[:3],
                        help="Email providers to look for (default: gmail, yahoo, outlook)")
    parser.add_argument("--output", help="Write a markdown file here (otherwise prints to screen)")
    args = parser.parse_args()

    queries = build(args.niche, args.location, args.platforms, args.providers)

    title = f"Search queries — {args.niche}" + (f" in {args.location}" if args.location else "")
    lines = [f"# {title}", "",
             "Click a link to run the search, or copy the query into Google yourself.",
             "Every one of these is free.", ""]

    for label, q in queries:
        lines += [f"### {label}", "", "```", q, "```", "", f"[Run this search]({google_url(q)})", ""]

    lines.append(WALKTHROUGH)
    text = "\n".join(lines)

    if args.output:
        path = ensure_dir(args.output)
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {len(queries)} queries to {path}")
        print("\nOpen it, click a link, and start scraping. No API keys needed.")
    else:
        print(text)


if __name__ == "__main__":
    main()
