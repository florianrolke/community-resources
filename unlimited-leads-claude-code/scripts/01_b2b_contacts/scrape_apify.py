#!/usr/bin/env python3
"""
SYSTEM 1 — Scrape B2B contacts using Apify's code_crafter/leads-finder actor.

This replaces the `HTTP Request1` node from the n8n workflow. Same actor, same
filters, except the filters are CLI flags instead of a JSON blob pasted into a
node you have to click into to read.

Usage:
    # Always test-scrape 25 first and eyeball the relevance before going big.
    python -X utf8 scripts/01_b2b_contacts/scrape_apify.py \\
        --query "Plumbers" --location "Alabama" --max_items 25 --no-email-filter

    # Then the real run, with CSV out.
    python -X utf8 scripts/01_b2b_contacts/scrape_apify.py \\
        --query "Plumbers" --location "Alabama" --max_items 500 \\
        --output output/leads.json --out-csv output/leads.csv

Cost: roughly $0.004 per lead (~$1.50 per 1,000).
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from scripts.lib.env import load_env, require
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import write_csv, write_json

fix_encoding()
load_env()

from apify_client import ApifyClient

# Apify bills per lead returned. Rough figure so the script can warn you before
# a big run; check the actor page for current pricing.
COST_PER_LEAD_USD = 0.0015

# US states for auto-formatting "Texas" -> "texas, us"
US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming"
}

# Countries that are valid as-is (no suffix needed)
COUNTRY_LOCATIONS = {
    "united states", "united kingdom", "canada", "australia", "germany",
    "france", "india", "china", "japan", "brazil", "mexico", "spain",
    "italy", "netherlands", "sweden", "switzerland", "ireland", "singapore",
    "south korea", "new zealand", "israel", "portugal", "belgium",
    "austria", "norway", "denmark", "finland", "poland", "south africa",
    "united arab emirates"
}

def format_location(location):
    """
    Auto-format location to Apify's required format.
    - US states: "Texas" -> "texas, us"
    - Countries: "United States" -> "united states" (as-is)
    - Already formatted: "texas, us" -> "texas, us" (no change)
    """
    loc = location.strip().lower()

    # Already formatted with country suffix
    if ", " in loc:
        return loc

    # Known country - use as-is
    if loc in COUNTRY_LOCATIONS:
        return loc

    # US state - append ", us"
    if loc in US_STATES:
        return f"{loc}, us"

    # Unknown - return as-is and let the API error if invalid
    return loc

def scrape_leads(query, location, max_items, job_titles=None, company_keywords=None,
                 require_email=True, cities=None, company_size=None):
    """
    Run the Apify actor to scrape leads.
    """
    api_token = require(
        "APIFY_API_TOKEN",
        hint="Get one at https://console.apify.com -> Settings -> API & Integrations",
    )

    client = ApifyClient(api_token)

    formatted_location = format_location(location)
    if formatted_location != location.strip().lower():
        print(f"Location auto-formatted: '{location}' -> '{formatted_location}'")

    run_input = {
        "fetch_count": int(max_items),
        "contact_job_title": job_titles if job_titles else [query],
        "company_keywords": company_keywords if company_keywords else [query],
        "contact_location": [formatted_location],
        "language": "en",
    }

    # These two were in the n8n body but unreachable from the old CLI.
    if cities:
        run_input["contact_city"] = [c.strip().lower() for c in cities]
    if company_size:
        run_input["size"] = company_size

    # Only add email filter if required
    if require_email:
        run_input["email_status"] = ["validated"]

    est = int(max_items) * COST_PER_LEAD_USD
    print(f"Starting scrape for '{query}' in '{location}' (Limit: {max_items})...")
    print(f"Estimated cost: ~${est:.2f}")
    print(f"Debug: run_input = {json.dumps(run_input, indent=2)}")


    try:
        # Run the actor and wait for it to finish
        run = client.actor("code_crafter/leads-finder").call(run_input=run_input)
    except Exception as e:
        print(f"Error running actor: {e}") # Print to stdout
        return None

    if not run:
        print("Error: Actor run failed to start", file=sys.stderr)
        return None

    print(f"Scrape finished. Fetching results from dataset {run['defaultDatasetId']}...")

    # Fetch results from the actor's default dataset
    results = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        results.append(item)
            
    return results

def save_results(results, output=None, out_csv=None, prefix="leads"):
    """
    Save results. JSON is the machine-readable handoff to the next step;
    CSV is the one you open in Excel.
    """
    if not results:
        print("No results to save.")
        return None

    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"output/{prefix}_{timestamp}.json"

    write_json(results, output)
    print(f"Results saved to {output}")

    if out_csv:
        write_csv(results, out_csv)
        print(f"CSV saved to {out_csv}")

    return output

def main():
    parser = argparse.ArgumentParser(description="Scrape B2B contacts using Apify (System 1)")
    parser.add_argument("--query", required=True, help="Search query (e.g., 'Plumbers')")
    parser.add_argument("--location", required=True, help="Location (e.g., 'New York')")
    parser.add_argument("--max_items", type=int, default=25, help="Maximum number of items to scrape")
    parser.add_argument("--output", default=None, help="Output JSON path (default: output/leads_TIMESTAMP.json)")
    parser.add_argument("--out-csv", dest="out_csv", default=None, help="Also write a CSV here (e.g., output/leads.csv)")
    parser.add_argument("--output_prefix", default="leads", help="Prefix for auto-generated output file (ignored if --output is set)")
    parser.add_argument("--job_titles", nargs='+', help="Specific job titles to target (e.g., CEO Founder)")
    parser.add_argument("--company_keywords", nargs='+', help="Company keywords to filter (e.g., 'software' 'SaaS')")
    parser.add_argument("--city", dest="cities", nargs='+', help="Narrow to specific cities (e.g., --city leeds manchester)")
    parser.add_argument("--size", dest="company_size", nargs='+', help="Company headcount bands (e.g., --size 21-50 51-100)")
    parser.add_argument("--no-email-filter", action="store_true", help="Don't filter by validated emails (faster, larger results)")

    args = parser.parse_args()

    require_email = not args.no_email_filter
    results = scrape_leads(
        args.query, args.location, args.max_items,
        args.job_titles, args.company_keywords, require_email,
        cities=args.cities, company_size=args.company_size,
    )

    if results:
        print(f"Found {len(results)} leads.")
        save_results(results, output=args.output, out_csv=args.out_csv, prefix=args.output_prefix)
        print("\nNext: research each lead ->")
        print("  python -X utf8 scripts/01_b2b_contacts/research_lead.py --input <that json>")
    else:
        print("No leads found or error occurred.")
        sys.exit(1)

if __name__ == "__main__":
    main()
