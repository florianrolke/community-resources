#!/usr/bin/env python3
"""
Export enriched BNI members to CSV for easy import into CRM or Google Sheets.

Columns: Name, Company, Category, ICP Tier, Phone, Website, LinkedIn, Email, Chapter,
         Meeting Day, Meeting Time, City, State

Usage:
    python export_csv.py --input leads/enriched_members.json --output leads/bni_export.csv
    python export_csv.py --input leads/enriched_members.json --tier A,B
    python export_csv.py --input leads/enriched_members.json --chapter "Power Players"
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
import csv
import json
from pathlib import Path

# CSV column definitions
CSV_COLUMNS = [
    "Name",
    "Company",
    "Category",
    "ICP Tier",
    "Phone",
    "Website",
    "LinkedIn",
    "Email",
    "Chapter",
    "Meeting Day",
    "Meeting Time",
    "City",
    "State",
]

# Mapping from JSON keys to CSV columns
FIELD_MAP = {
    "Name": "name",
    "Company": "company",
    "Category": "category",
    "ICP Tier": "icp_tier",
    "Phone": "phone",
    "Website": "website",
    "LinkedIn": "linkedin",
    "Email": "email",
    "Chapter": "chapter",
    "Meeting Day": "meeting_day",
    "Meeting Time": "meeting_time",
    "City": "city",
    "State": "state",
}


def export_csv(
    input_path: str,
    output_path: str,
    tier_filter: list[str] | None = None,
    chapter_filter: str | None = None,
    linkedin_only: bool = False,
):
    """Export enriched members JSON to CSV."""
    inp = Path(input_path)
    if not inp.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    with open(inp, "r", encoding="utf-8") as f:
        members = json.load(f)

    print(f"[LOADED] {len(members)} members from {input_path}")

    # Apply filters
    if tier_filter:
        tier_upper = [t.upper() for t in tier_filter]
        members = [m for m in members if m.get("icp_tier", "D") in tier_upper]
        print(f"[FILTER] {len(members)} members in tiers: {', '.join(tier_upper)}")

    if chapter_filter:
        target = chapter_filter.lower()
        members = [m for m in members if target in m.get("chapter", "").lower()]
        print(f"[FILTER] {len(members)} members in chapter matching '{chapter_filter}'")

    if linkedin_only:
        members = [m for m in members if m.get("linkedin")]
        print(f"[FILTER] {len(members)} members with LinkedIn profiles")

    if not members:
        print("[WARN] No members to export after filtering")
        return

    # Write CSV
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for member in members:
            row = {}
            for col, key in FIELD_MAP.items():
                row[col] = member.get(key, "")
            writer.writerow(row)

    print(f"\n[EXPORTED] {len(members)} members -> {out}")

    # Quick stats
    with_linkedin = sum(1 for m in members if m.get("linkedin"))
    with_email = sum(1 for m in members if m.get("email"))
    with_phone = sum(1 for m in members if m.get("phone"))
    print(f"  LinkedIn: {with_linkedin}, Email: {with_email}, Phone: {with_phone}")


def main():
    parser = argparse.ArgumentParser(description="Export BNI members to CSV")
    parser.add_argument("--input", default="leads/enriched_members.json",
                        help="Input JSON file")
    parser.add_argument("--output", default="leads/bni_export.csv",
                        help="Output CSV file")
    parser.add_argument("--tier", type=str, default=None,
                        help="Filter by ICP tier(s), comma-separated (e.g., A,B)")
    parser.add_argument("--chapter", type=str, default=None,
                        help="Filter by chapter name (partial match)")
    parser.add_argument("--linkedin-only", action="store_true",
                        help="Only export members with LinkedIn profiles")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / args.input
    output_path = script_dir / args.output

    tier_filter = None
    if args.tier:
        tier_filter = [t.strip() for t in args.tier.split(",")]

    export_csv(
        input_path=str(input_path),
        output_path=str(output_path),
        tier_filter=tier_filter,
        chapter_filter=args.chapter,
        linkedin_only=args.linkedin_only,
    )


if __name__ == "__main__":
    main()
