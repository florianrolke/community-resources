#!/usr/bin/env python3
"""
Company Research via Perplexity Sonar

Deep research on a company: description, industry, size, founders, notable info.
Returns structured JSON.

Usage:
    python -X utf8 research_company.py --company "Acme Corp" --city "Austin"
    python -X utf8 research_company.py --input leads.json --output researched.json
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
from lib.safe_io import safe_json_write, safe_json_read
from lib.checkpoint import CheckpointManager


def main():
    parser = argparse.ArgumentParser(description="Research companies via Perplexity")
    parser.add_argument("--company", help="Company name (single lookup)")
    parser.add_argument("--website", default="", help="Company website")
    parser.add_argument("--city", default="", help="City for context")
    parser.add_argument("--input", help="Input JSON for batch mode")
    parser.add_argument("--output", help="Output JSON for batch mode")
    args = parser.parse_args()

    engine = EnrichmentEngine()

    if not os.environ.get("PERPLEXITY_API_KEY"):
        print("[ERROR] PERPLEXITY_API_KEY required for company research")
        return

    if args.company:
        result = engine.research_company(args.company, args.website, args.city)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.input:
        data = safe_json_read(args.input)
        if not data or not isinstance(data, list):
            return
        cp = CheckpointManager("research", save_every=3, output_dir=".tmp")
        for i, lead in enumerate(data):
            company = lead.get("company", lead.get("business_name", ""))
            if not company:
                continue
            key = company
            if cp.is_done(key):
                lead["research"] = cp.get_result(key)
                continue
            print(f"  [{i + 1}/{len(data)}] Researching: {company[:40]}")
            result = engine.research_company(
                company, lead.get("website", ""), lead.get("city", "")
            )
            lead["research"] = result
            cp.save_result(key, result)
        cp.finalize()
        output = args.output or str(
            Path(args.input).with_stem(Path(args.input).stem + "_researched")
        )
        safe_json_write(output, data)
        print(f"\nResearched {len(data)} companies -> {output}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
