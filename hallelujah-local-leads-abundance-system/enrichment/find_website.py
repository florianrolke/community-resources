#!/usr/bin/env python3
"""
Website Discovery via Exa/Tavily

Finds official business websites using a waterfall search.
Filters out aggregator sites (LinkedIn, Yelp, BBB, etc.)

Usage:
    python -X utf8 find_website.py --company "Acme Corp" --city "Austin"
    python -X utf8 find_website.py --input leads.json --output leads_with_websites.json
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from lib.enrichment_engine import EnrichmentEngine
from lib.safe_io import safe_json_write, safe_json_read


def main():
    parser = argparse.ArgumentParser(description="Find business websites")
    parser.add_argument("--company", help="Company name (single lookup)")
    parser.add_argument("--city", default="", help="City for context")
    parser.add_argument("--input", help="Input JSON for batch mode")
    parser.add_argument("--output", help="Output JSON for batch mode")
    parser.add_argument("--company-field", default="company", help="JSON field for company name")
    args = parser.parse_args()

    engine = EnrichmentEngine()

    if args.company:
        url = engine.find_website(args.company, args.city)
        print(f"Website: {url or 'not found'}")
    elif args.input:
        data = safe_json_read(args.input)
        if not data or not isinstance(data, list):
            print(f"[ERROR] Could not load {args.input}")
            return
        found = 0
        for i, lead in enumerate(data):
            company = lead.get(args.company_field, "")
            if not company or lead.get("website"):
                if lead.get("website"):
                    found += 1
                continue
            city = lead.get("city", "")
            print(f"  [{i + 1}/{len(data)}] {company[:40]}...", end="")
            url = engine.find_website(company, city)
            if url:
                lead["website"] = url
                found += 1
                print(f" -> {url[:50]}")
            else:
                print(" -> not found")
            if engine.exa.all_exhausted and engine.tavily.all_exhausted:
                print("\n[STOP] All API keys exhausted.")
                break
        output = args.output or str(Path(args.input).with_stem(Path(args.input).stem + "_websites"))
        safe_json_write(output, data)
        print(f"\nWebsites found: {found}/{len(data)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
