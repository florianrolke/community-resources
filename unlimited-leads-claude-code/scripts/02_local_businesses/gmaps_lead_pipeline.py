#!/usr/bin/env python3
"""
Google Maps Lead Generation Pipeline

End-to-end pipeline that:
1. Scrapes Google Maps for businesses matching search criteria
2. Enriches each business by scraping their website for contact info
3. Uses Claude to extract structured contact data
4. Saves everything to a persistent Google Sheet

Usage:
    # CSV out, no Google account needed. This is the default path.
    python -X utf8 scripts/02_local_businesses/gmaps_lead_pipeline.py \\
        --search "barbers in Tuscaloosa AL" --limit 10 --out-csv output/gmaps.csv

    # Push to a Google Sheet instead (needs credentials.json — see
    # docs/GOOGLE_SHEETS_SETUP.md). Entirely optional.
    python -X utf8 scripts/02_local_businesses/gmaps_lead_pipeline.py \\
        --search "dentists in Miami FL" --limit 25 --sheet-url "https://..."
"""

import os
import sys
import json
import argparse
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Repo root on the path, so `scripts.lib.*` resolves no matter which directory
# you run this from. The sibling directory too, for the imports just below.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _HERE)

from scripts.lib.env import load_env
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import write_csv, write_json

fix_encoding()
load_env()

from scrape_google_maps import scrape_google_maps
from extract_website_contacts import scrape_website_contacts
from summarize_website import summarize_website

# gspread and the google-auth stack are imported lazily inside the Sheets
# functions. They are only needed if you pass --sheet-url, and a missing
# Google dependency should never break the CSV path.

# Google Sheets config
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Default sheet name for leads
DEFAULT_SHEET_NAME = "GMaps Lead Database"

# Lead schema - columns for the Google Sheet
LEAD_COLUMNS = [
    "lead_id",
    "scraped_at",
    "search_query",
    # Business basics from Google Maps
    "business_name",
    "category",
    "address",
    "city",
    "state",
    "zip_code",
    "country",
    "phone",
    "website",
    "google_maps_url",
    "place_id",
    # Ratings & reviews
    "rating",
    "review_count",
    "price_level",
    # Extracted contact info
    "emails",
    "additional_phones",
    "business_hours",
    # Social media
    "facebook",
    "twitter",
    "linkedin",
    "instagram",
    "youtube",
    "tiktok",
    # Owner/key person info
    "owner_name",
    "owner_title",
    "owner_email",
    "owner_phone",
    "owner_linkedin",
    # Team contacts (JSON string for multiple people)
    "team_contacts",
    # Additional data
    "additional_contact_methods",
    "pages_scraped",
    "search_enriched",
    "enrichment_status",
    # AI website analysis (the n8n `AI Agent` node)
    "summary",
    "fact_1",
    "fact_2",
    "fact_3",
    "fact_4",
    "fact_5",
]


def generate_lead_id(business_name: str, address: str) -> str:
    """Generate a unique ID for a lead based on name and address."""
    unique_string = f"{business_name}|{address}".lower()
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]


def stringify_value(value) -> str:
    """Convert any value to a string suitable for Google Sheets."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        # Filter out None values and convert to comma-separated string
        return ", ".join(str(v) for v in value if v)
    if isinstance(value, dict):
        # Convert dict to a readable string format
        parts = []
        for k, v in value.items():
            if v:
                parts.append(f"{k}: {v}")
        return "; ".join(parts) if parts else ""
    return str(value)


def parse_address(address: str) -> dict:
    """Parse an address string into components."""
    # Simple parsing - not perfect but handles common US formats
    parts = {
        "city": "",
        "state": "",
        "zip_code": "",
        "country": "USA"
    }

    if not address:
        return parts

    # Try to extract zip code
    import re
    zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address)
    if zip_match:
        parts["zip_code"] = zip_match.group(1)

    # Try to extract state (2-letter code)
    state_match = re.search(r'\b([A-Z]{2})\b', address)
    if state_match:
        parts["state"] = state_match.group(1)

    # City is harder - take the part before the state
    if parts["state"]:
        city_match = re.search(rf',\s*([^,]+),?\s*{parts["state"]}', address)
        if city_match:
            parts["city"] = city_match.group(1).strip()

    return parts


def flatten_lead(gmaps_data: dict, contacts: dict, search_query: str) -> dict:
    """
    Flatten Google Maps data and extracted contacts into a single lead record.

    Args:
        gmaps_data: Raw data from Google Maps scraper
        contacts: Extracted contact data from website
        search_query: Original search query

    Returns:
        Flattened dictionary matching LEAD_COLUMNS schema
    """
    # Parse address components
    address = gmaps_data.get("address", "")
    addr_parts = parse_address(address)

    # Extract social media
    social = contacts.get("social_media", {}) or {}

    # Extract owner info
    owner = contacts.get("owner_info", {}) or {}

    # Format team contacts as JSON string
    team = contacts.get("team_members", []) or []
    team_json = json.dumps(team) if team else ""

    # Format lists as comma-separated strings
    emails = contacts.get("emails", []) or []
    phones = contacts.get("phone_numbers", []) or []
    additional_contacts = contacts.get("additional_contacts", []) or []

    # Generate lead ID
    lead_id = generate_lead_id(
        gmaps_data.get("title", ""),
        address
    )

    # Determine enrichment status
    enrichment_status = "success" if emails or owner.get("email") else "partial"
    if contacts.get("error"):
        enrichment_status = f"error: {contacts.get('error')}"

    return {
        "lead_id": lead_id,
        "scraped_at": datetime.now().isoformat(),
        "search_query": search_query,
        # Business basics
        "business_name": gmaps_data.get("title", ""),
        "category": gmaps_data.get("categoryName", ""),
        "address": address,
        "city": addr_parts["city"] or gmaps_data.get("city", ""),
        "state": addr_parts["state"] or gmaps_data.get("state", ""),
        "zip_code": addr_parts["zip_code"] or gmaps_data.get("postalCode", ""),
        "country": gmaps_data.get("countryCode", "USA"),
        "phone": gmaps_data.get("phone", ""),
        "website": gmaps_data.get("website", ""),
        "google_maps_url": gmaps_data.get("url", ""),
        "place_id": gmaps_data.get("placeId", ""),
        # Ratings
        "rating": gmaps_data.get("totalScore", ""),
        "review_count": gmaps_data.get("reviewsCount", ""),
        "price_level": gmaps_data.get("price", ""),
        # Extracted contacts
        "emails": stringify_value(emails),
        "additional_phones": stringify_value(phones),
        "business_hours": stringify_value(contacts.get("business_hours", "")),
        # Social media
        "facebook": stringify_value(social.get("facebook", "")),
        "twitter": stringify_value(social.get("twitter", "")),
        "linkedin": stringify_value(social.get("linkedin", "")),
        "instagram": stringify_value(social.get("instagram", "")),
        "youtube": stringify_value(social.get("youtube", "")),
        "tiktok": stringify_value(social.get("tiktok", "")),
        # Owner info
        "owner_name": stringify_value(owner.get("name", "")),
        "owner_title": stringify_value(owner.get("title", "")),
        "owner_email": stringify_value(owner.get("email", "")),
        "owner_phone": stringify_value(owner.get("phone", "")),
        "owner_linkedin": stringify_value(owner.get("linkedin", "")),
        # Team
        "team_contacts": team_json,
        # Additional
        "additional_contact_methods": stringify_value(additional_contacts),
        "pages_scraped": contacts.get("_pages_scraped", 0),
        "search_enriched": "yes" if contacts.get("_search_enriched") else "no",
        "enrichment_status": enrichment_status,
    }


def get_credentials():
    """Get OAuth2 credentials for Google Sheets API. Only called on the --sheet-url path."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = None

    if os.path.exists('token.json'):
        try:
            with open('token.json', 'r') as token:
                token_data = json.load(token)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"Error loading token: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def get_or_create_sheet(sheet_url: str = None, sheet_name: str = None) -> tuple:
    """
    Get existing sheet or create a new one.

    Returns:
        Tuple of (spreadsheet, worksheet, is_new)
    """
    import gspread

    creds = get_credentials()
    client = gspread.authorize(creds)

    if sheet_url:
        # Open existing sheet by URL
        if '/d/' in sheet_url:
            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
        else:
            sheet_id = sheet_url

        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        is_new = False
        print(f"Opened existing sheet: {spreadsheet.title}")
    else:
        # Create new sheet
        name = sheet_name or DEFAULT_SHEET_NAME
        spreadsheet = client.create(name)
        worksheet = spreadsheet.sheet1

        # Set up headers
        worksheet.update(values=[LEAD_COLUMNS], range_name='A1')

        # Format header row (bold)
        worksheet.format('A1:AK1', {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
        })

        # Freeze header row
        worksheet.freeze(rows=1)

        is_new = True
        print(f"Created new sheet: {name}")
        print(f"Sheet URL: {spreadsheet.url}")

    return spreadsheet, worksheet, is_new


def get_existing_lead_ids(worksheet) -> set:
    """Get all existing lead IDs from the sheet to avoid duplicates."""
    try:
        # Get all values in column A (lead_id)
        lead_ids = worksheet.col_values(1)
        return set(lead_ids[1:])  # Skip header
    except Exception:
        return set()


def append_leads_to_sheet(worksheet, leads: list[dict], existing_ids: set) -> int:
    """
    Append new leads to the sheet, skipping duplicates.

    Returns:
        Number of leads added
    """
    # Filter out duplicates
    new_leads = [lead for lead in leads if lead["lead_id"] not in existing_ids]

    if not new_leads:
        print("No new leads to add (all duplicates)")
        return 0

    # Convert to rows
    rows = []
    for lead in new_leads:
        row = [lead.get(col, "") for col in LEAD_COLUMNS]
        rows.append(row)

    # Batch append
    worksheet.append_rows(rows, value_input_option='RAW')

    print(f"Added {len(new_leads)} new leads to sheet")
    return len(new_leads)


def enrich_businesses(businesses: list[dict], max_workers: int = 3) -> list[dict]:
    """
    Enrich businesses with website contact information.

    Args:
        businesses: List of business dicts from Google Maps
        max_workers: Parallel workers for website scraping

    Returns:
        List of dicts with added contact information
    """
    print(f"\nEnriching {len(businesses)} businesses with website data...")

    enriched = []

    # Filter to only businesses with websites
    with_websites = [b for b in businesses if b.get("website")]
    without_websites = [b for b in businesses if not b.get("website")]

    print(f"  {len(with_websites)} have websites, {len(without_websites)} do not")

    # Process businesses without websites
    for business in without_websites:
        enriched.append({
            "gmaps": business,
            "contacts": {"error": "No website available"}
        })

    # Process businesses with websites in parallel
    if with_websites:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_business = {
                executor.submit(
                    scrape_website_contacts,
                    business.get("website"),
                    business.get("title")
                ): business
                for business in with_websites
            }

            for i, future in enumerate(as_completed(future_to_business), 1):
                business = future_to_business[future]
                try:
                    contacts = future.result()
                    enriched.append({
                        "gmaps": business,
                        "contacts": contacts
                    })
                    print(f"  [{i}/{len(with_websites)}] Enriched: {business.get('title')}")
                except Exception as e:
                    print(f"  [{i}/{len(with_websites)}] Error enriching {business.get('title')}: {e}")
                    enriched.append({
                        "gmaps": business,
                        "contacts": {"error": str(e)}
                    })

    return enriched


def run_pipeline(
    search_query: str,
    max_results: int = 10,
    location: str = None,
    sheet_url: str = None,
    sheet_name: str = None,
    workers: int = 3,
    save_intermediate: bool = True,
    out_csv: str = None,
    out_json: str = None,
    summarize: bool = True,
) -> dict:
    """
    Run the full lead generation pipeline.

    Args:
        search_query: What to search for on Google Maps
        max_results: Maximum number of businesses to scrape
        location: Optional location filter
        sheet_url: Existing Google Sheet URL (creates new if not provided)
        sheet_name: Name for new sheet (if creating)
        workers: Parallel workers for website enrichment
        save_intermediate: Whether to save intermediate JSON files

    Returns:
        Dictionary with pipeline results
    """
    # Defined up front — the output filenames use it whether or not we're
    # saving intermediates.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {
        "search_query": search_query,
        "started_at": datetime.now().isoformat(),
        "businesses_found": 0,
        "leads_enriched": 0,
        "leads_added": 0,
        "sheet_url": None,
        "errors": []
    }

    # Step 1: Scrape Google Maps
    print(f"\n{'='*60}")
    print(f"STEP 1: Scraping Google Maps for '{search_query}'")
    print(f"{'='*60}")

    businesses = scrape_google_maps(
        search_query=search_query,
        max_results=max_results,
        location=location,
    )

    if not businesses:
        results["errors"].append("No businesses found on Google Maps")
        return results

    results["businesses_found"] = len(businesses)
    print(f"Found {len(businesses)} businesses")

    # Save intermediate results
    if save_intermediate:
        os.makedirs(".tmp", exist_ok=True)
        with open(f".tmp/gmaps_raw_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(businesses, f, indent=2, ensure_ascii=False)

    # Step 2: Enrich with website data
    print(f"\n{'='*60}")
    print(f"STEP 2: Enriching businesses with website contact data")
    print(f"{'='*60}")

    enriched = enrich_businesses(businesses, max_workers=workers)
    results["leads_enriched"] = len(enriched)

    # Step 3: Flatten to lead records
    print(f"\n{'='*60}")
    print(f"STEP 3: Processing lead records")
    print(f"{'='*60}")

    leads = []
    for item in enriched:
        lead = flatten_lead(item["gmaps"], item["contacts"], search_query)
        leads.append(lead)

    # Step 4: AI summary + 5 facts per business (this is the n8n `AI Agent` node)
    if summarize:
        print(f"\n{'='*60}")
        print(f"STEP 4: Writing a summary + 5 facts for each business")
        print(f"{'='*60}")

        for i, (lead, item) in enumerate(zip(leads, enriched), 1):
            page_text = (item.get("contacts") or {}).get("_page_text", "")
            if not page_text:
                lead["summary"] = ""
                for n in range(1, 6):
                    lead[f"fact_{n}"] = ""
                continue
            try:
                result = summarize_website(page_text, business_name=lead.get("business_name", ""))
                lead["summary"] = result.get("summary", "")
                facts = result.get("facts", [])
                for n in range(1, 6):
                    lead[f"fact_{n}"] = facts[n - 1] if len(facts) >= n else ""
                print(f"  [{i}/{len(leads)}] {lead.get('business_name','?')[:40]} — summarized")
            except Exception as e:
                results["errors"].append(f"Summary failed for {lead.get('business_name')}: {e}")
                lead["summary"] = ""
                for n in range(1, 6):
                    lead[f"fact_{n}"] = ""

    # Step 5: Write the output files
    print(f"\n{'='*60}")
    print(f"STEP 5: Saving results")
    print(f"{'='*60}")

    if out_json:
        write_json(leads, out_json)
        print(f"JSON saved to {out_json}")
    if out_csv:
        write_csv(leads, out_csv, columns=LEAD_COLUMNS)
        print(f"CSV saved to {out_csv}")
    if not out_json and not out_csv and not sheet_url:
        # Never let a run end with the data only in memory.
        default_csv = f"output/gmaps_leads_{timestamp}.csv"
        write_csv(leads, default_csv, columns=LEAD_COLUMNS)
        print(f"CSV saved to {default_csv}")

    # Step 6: Google Sheet — only if explicitly asked for
    if sheet_url or sheet_name:
        print(f"\n{'='*60}")
        print(f"STEP 6: Saving to Google Sheet")
        print(f"{'='*60}")

        try:
            spreadsheet, worksheet, is_new = get_or_create_sheet(sheet_url, sheet_name)
            results["sheet_url"] = spreadsheet.url

            existing_ids = get_existing_lead_ids(worksheet)
            added = append_leads_to_sheet(worksheet, leads, existing_ids)
            results["leads_added"] = added

        except Exception as e:
            results["errors"].append(f"Google Sheets error: {str(e)}")
            print(f"Error saving to sheet: {e}")
            print("Your leads are safe in the CSV/JSON above — the Sheets step is optional.")

    # Summary
    results["completed_at"] = datetime.now().isoformat()
    results["leads"] = leads

    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"Businesses found: {results['businesses_found']}")
    print(f"Leads enriched: {results['leads_enriched']}")
    if results["sheet_url"]:
        print(f"New leads added to sheet: {results['leads_added']}")
        print(f"Sheet URL: {results['sheet_url']}")
    if results["errors"]:
        print(f"Errors: {results['errors']}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Google Maps Lead Generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search
  python3 execution/gmaps_lead_pipeline.py --search "plumbers in Austin TX" --limit 10

  # With specific location
  python3 execution/gmaps_lead_pipeline.py --search "dentists" --location "Miami FL" --limit 25

  # Append to existing sheet
  python3 execution/gmaps_lead_pipeline.py --search "lawyers" --limit 10 --sheet-url "https://docs.google.com/spreadsheets/d/..."
        """
    )

    parser.add_argument("--search", required=True, help="Search query for Google Maps")
    parser.add_argument("--limit", type=int, default=10, help="Max results to scrape (default: 10)")
    parser.add_argument("--location", help="Location to focus search")
    parser.add_argument("--out-csv", dest="out_csv", help="Write a CSV here (this is the default deliverable)")
    parser.add_argument("--out-json", dest="out_json", help="Write a JSON here")
    parser.add_argument("--sheet-url", help="OPTIONAL: existing Google Sheet URL to append to (needs credentials.json)")
    parser.add_argument("--sheet-name", help="OPTIONAL: name for a new sheet")
    parser.add_argument("--no-summary", action="store_true", help="Skip the AI summary + 5 facts step (saves ~$0.002/lead)")
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers for enrichment (default: 3)")
    parser.add_argument("--no-intermediate", action="store_true", help="Don't save intermediate JSON files")
    parser.add_argument("--json", action="store_true", help="Print the run report as JSON")

    args = parser.parse_args()

    results = run_pipeline(
        search_query=args.search,
        max_results=args.limit,
        location=args.location,
        sheet_url=args.sheet_url,
        sheet_name=args.sheet_name,
        workers=args.workers,
        save_intermediate=not args.no_intermediate,
        out_csv=args.out_csv,
        out_json=args.out_json,
        summarize=not args.no_summary,
    )

    if args.json:
        print(json.dumps(results, indent=2))

    # Exit with error if no leads were added
    if results["leads_added"] == 0 and results["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
