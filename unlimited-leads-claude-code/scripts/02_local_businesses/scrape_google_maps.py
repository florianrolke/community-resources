#!/usr/bin/env python3
"""
SYSTEM 2 — Scrape Google Maps business listings via Apify.

This replaces the `Scrape Google Maps` node from the n8n workflow — and then
some. The actor has grown since the course was recorded.

What changed
------------
The course needed six steps to get from "businesses on a map" to "emails in a
spreadsheet": scrape Maps, loop over every result, fetch each website, have an
AI read the HTML for contact details, export a CSV, then upload that CSV to
AnyMailFinder and download the results.

The actor now does all of it. Three flags:

    --contacts        emails + social profiles pulled from each business website
    --leads N         up to N decision-makers per business, with name, job title,
                      email, phone, and LinkedIn URL
    --verify-emails   checks each of those emails is real before you send to it

So the loop node, the website-fetch node, the AI-extraction node, and the entire
AnyMailFinder round trip collapse into one call. This is the single biggest
"the video is old" difference in the repo.

Usage:
    # Just the businesses (cheapest)
    python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \\
        --search "barbers in Tuscaloosa AL" --limit 10 --out-csv output/gmaps.csv

    # Businesses + emails + decision-makers, verified
    python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \\
        --search "law firms in Mobile AL" --limit 25 \\
        --contacts --leads 3 --departments "C-Suite" --verify-emails \\
        --out-csv output/lawyers.csv

Cost: see docs/COSTS.md. Each add-on bills separately, so start without them.
"""

import os
import sys
import json
import argparse
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.env import load_env, require
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import write_csv, write_json

fix_encoding()
load_env()

from apify_client import ApifyClient

ACTORS = {
    # What the course used. Cheaper, plenty for lead gen.
    "extractor": "compass/google-maps-extractor",
    # Richer: reviews, hours, popular times. Costs more.
    "crawler": "compass/crawler-google-places",
}
DEFAULT_ACTOR = "extractor"


def scrape_google_maps(
    search_query: str,
    max_results: int = 10,
    location: str = None,
    language: str = "en",
    actor: str = DEFAULT_ACTOR,
    min_stars: str = "",
    skip_closed: bool = False,
    contacts: bool = False,
    leads: int = 0,
    departments: list[str] | None = None,
    verify_emails: bool = False,
) -> list[dict]:
    """
    Run the Apify Google Maps scraper actor.

    Args:
        search_query: Search term (e.g., "barbers in Tuscaloosa AL")
        max_results: Maximum number of places to scrape
        location: Optional location to focus the search
        language: Language code (default: en)
        actor: "extractor" (the course default) or "crawler" (richer, pricier)
        min_stars: Only return places rated at least this (e.g. "4"). "" = all.
        skip_closed: Drop permanently closed businesses
        contacts: Pull emails + social profiles from each business website
        leads: Decision-makers to find per business (0 = off)
        departments: Restrict leads to e.g. ["C-Suite"], ["Sales"]
        verify_emails: Verify each lead email before returning it

    Returns:
        List of business dictionaries with scraped data
    """
    api_token = require(
        "APIFY_API_TOKEN",
        hint="Get one at https://console.apify.com -> Settings -> API & Integrations",
    )

    actor_id = ACTORS.get(actor, actor)
    client = ApifyClient(api_token)

    # Build search string with location if provided
    full_search = search_query
    if location and location.lower() not in search_query.lower():
        full_search = f"{search_query} in {location}"

    # These fields mirror the n8n node's body so results match the course.
    run_input = {
        "searchStringsArray": [full_search],
        "maxCrawledPlacesPerSearch": max_results,
        "language": language,
        "skipClosedPlaces": skip_closed,
        "placeMinimumStars": min_stars,
        "website": "allPlaces",
        "searchMatching": "all",
    }
    if location:
        run_input["locationQuery"] = location
    if actor_id == ACTORS["crawler"]:
        run_input["deeperCityScrape"] = False
        run_input["oneReviewPerRow"] = False

    # The enrichment add-ons. Each one bills separately — see docs/COSTS.md.
    if contacts:
        run_input["scrapeContacts"] = True
    if leads:
        run_input["maximumLeadsEnrichmentRecords"] = int(leads)
        if departments:
            run_input["leadsEnrichmentDepartments"] = departments
        if verify_emails:
            run_input["verifyLeadsEnrichmentEmails"] = True
    elif verify_emails:
        print("Note: --verify-emails only applies to --leads results; ignoring.")

    print(f"Starting Google Maps scrape: '{full_search}' (limit: {max_results})...")
    print(f"Actor: {actor_id}")
    addons = [n for n, on in
              [("contacts", contacts), (f"leads x{leads}", leads), ("email verification", leads and verify_emails)]
              if on]
    if addons:
        print(f"Add-ons: {', '.join(addons)}  (these cost extra — see docs/COSTS.md)")

    try:
        run = client.actor(actor_id).call(run_input=run_input)
    except Exception as e:
        print(f"Error running Apify actor: {e}", file=sys.stderr)
        return []

    if not run:
        print("Error: Actor run failed to start", file=sys.stderr)
        return []

    print(f"Scrape finished. Fetching results from dataset {run['defaultDatasetId']}...")

    results = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        results.append(item)

    print(f"Retrieved {len(results)} businesses from Google Maps")
    return results


def save_results(results: list[dict], prefix: str = "gmaps") -> str:
    """Save results to a timestamped JSON file in output/."""
    if not results:
        print("No results to save.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"output/{prefix}_{timestamp}.json"
    write_json(results, filename)
    print(f"Results saved to {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(description="Scrape Google Maps businesses using Apify (System 2)")
    parser.add_argument("--search", required=True, help="Search query (e.g., 'barbers in Tuscaloosa AL')")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of results (default: 10)")
    parser.add_argument("--location", help="Optional location to focus search")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument("--actor", default=DEFAULT_ACTOR, choices=list(ACTORS.keys()),
                        help="'extractor' = what the course used (default), 'crawler' = richer but pricier")
    parser.add_argument("--min-stars", dest="min_stars", default="",
                        help="Only places rated at least this, e.g. 4 (default: all)")
    parser.add_argument("--skip-closed", dest="skip_closed", action="store_true",
                        help="Drop permanently closed businesses")
    parser.add_argument("--contacts", action="store_true",
                        help="Pull emails + social profiles from each business website")
    parser.add_argument("--leads", type=int, default=0, metavar="N",
                        help="Find up to N decision-makers per business (name, title, email, phone, LinkedIn)")
    parser.add_argument("--departments", nargs="+",
                        help='Restrict --leads to departments, e.g. --departments "C-Suite" Sales')
    parser.add_argument("--verify-emails", dest="verify_emails", action="store_true",
                        help="Verify each --leads email is real before returning it")
    parser.add_argument("--output", default="gmaps", help="Output file prefix (default: gmaps)")
    parser.add_argument("--out-csv", dest="out_csv", help="Also write a CSV here")
    parser.add_argument("--json", action="store_true", help="Print results as JSON to stdout")

    args = parser.parse_args()

    results = scrape_google_maps(
        search_query=args.search,
        max_results=args.limit,
        location=args.location,
        language=args.language,
        actor=args.actor,
        min_stars=args.min_stars,
        skip_closed=args.skip_closed,
        contacts=args.contacts,
        leads=args.leads,
        departments=args.departments,
        verify_emails=args.verify_emails,
    )

    if not results:
        print("No results found or error occurred.")
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        filename = save_results(results, prefix=args.output)
        if args.out_csv:
            write_csv(results, args.out_csv)
            print(f"CSV saved to {args.out_csv}")
        if filename:
            print(f"\nSample result:")
            sample = results[0]
            for key in ["title", "address", "phone", "website", "categoryName"]:
                if key in sample:
                    print(f"  {key}: {sample.get(key)}")


if __name__ == "__main__":
    main()
