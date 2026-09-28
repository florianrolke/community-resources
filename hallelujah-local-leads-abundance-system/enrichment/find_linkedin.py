#!/usr/bin/env python3
"""
LinkedIn Profile Discovery Waterfall

Finds LinkedIn profiles for business owners/contacts using a 3-source waterfall:
  1. Exa (best for LinkedIn — structured results)
  2. Tavily (good fallback)
  3. Perplexity (expensive, last resort)

All results are validated: the person's name must appear in the LinkedIn slug.
This prevents false positives where search APIs return unrelated profiles.

Usage:
    python -X utf8 find_linkedin.py --name "John Smith" --company "Acme Corp"
    python -X utf8 find_linkedin.py --input leads.json --output leads_with_linkedin.json
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from lib.enrichment_engine import EnrichmentEngine
from lib.linkedin_validator import extract_linkedin_url, validate_linkedin_for_person
from lib.safe_io import safe_json_write, safe_json_read


def find_linkedin_single(name: str, company: str = "", city: str = "",
                         engine: EnrichmentEngine = None) -> dict:
    """Find LinkedIn for a single person.

    Returns dict with: linkedin_url, linkedin_source, validated
    """
    if engine is None:
        engine = EnrichmentEngine()

    url = engine.find_linkedin(name, company, city)

    return {
        "linkedin_url": url,
        "linkedin_source": "exa_or_tavily" if url else None,
        "validated": validate_linkedin_for_person(url, name, company) if url else False,
    }


def find_linkedin_batch(input_path: str, output_path: str,
                        name_field: str = "name", company_field: str = "company"):
    """Find LinkedIn profiles for a batch of leads."""
    data = safe_json_read(input_path)
    if not data or not isinstance(data, list):
        print(f"[ERROR] Could not load leads from {input_path}")
        return

    engine = EnrichmentEngine()
    found = 0
    total = len(data)

    for i, lead in enumerate(data):
        name = lead.get(name_field, "")
        company = lead.get(company_field, "")

        if not name:
            continue

        # Skip if already has LinkedIn
        if lead.get("linkedin") or lead.get("linkedin_url"):
            found += 1
            continue

        print(f"  [{i + 1}/{total}] {name} @ {company[:30]}...", end="")
        result = find_linkedin_single(name, company, engine=engine)

        if result["linkedin_url"]:
            lead["linkedin"] = result["linkedin_url"]
            lead["linkedin_source"] = result["linkedin_source"]
            found += 1
            print(f" -> {result['linkedin_url'][:50]}")
        else:
            print(" -> not found")

        # Check exhaustion
        if engine.exa.all_exhausted and engine.tavily.all_exhausted:
            print("\n[STOP] All API keys exhausted.")
            break

    safe_json_write(output_path, data)
    print(f"\nDone: {found}/{total} LinkedIn profiles found ({found * 100 // max(total, 1)}%)")
    print(f"Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Find LinkedIn profiles for leads")
    parser.add_argument("--name", help="Person name (single lookup)")
    parser.add_argument("--company", default="", help="Company name")
    parser.add_argument("--city", default="", help="City for context")
    parser.add_argument("--input", help="Input JSON for batch mode")
    parser.add_argument("--output", help="Output JSON for batch mode")
    parser.add_argument("--name-field", default="name", help="JSON field for person name")
    parser.add_argument("--company-field", default="company", help="JSON field for company")
    args = parser.parse_args()

    if args.name:
        # Single lookup
        result = find_linkedin_single(args.name, args.company, args.city)
        if result["linkedin_url"]:
            print(f"LinkedIn: {result['linkedin_url']}")
            print(f"Validated: {result['validated']}")
        else:
            print("LinkedIn profile not found")
    elif args.input:
        output = args.output or str(Path(args.input).with_stem(Path(args.input).stem + "_linkedin"))
        find_linkedin_batch(args.input, output, args.name_field, args.company_field)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
