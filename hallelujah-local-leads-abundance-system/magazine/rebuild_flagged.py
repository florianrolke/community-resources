#!/usr/bin/env python3
"""Magazine Multi-Issue Flagging — NEW vs SEEN Lead Detection

Processes multiple issues for an edition and flags leads as NEW or SEEN.
Issues are processed newest-first so that the latest report shows which
advertisers are new (first appearance) vs returning (seen in earlier issues).

Features:
- NEW leads: green badge, full opacity, displayed at top of report
- SEEN leads: gray badge with "ALREADY IN: {month} {year}", 45% opacity, at bottom
- Dedup: normalize names (lowercase, strip punctuation, strip LLC/Inc suffixes)
- Merge groups for fuzzy matches

Usage:
    python rebuild_flagged.py --edition johnsoncounty --data-dir data
    python rebuild_flagged.py --edition johnsoncounty --months 3,2,1,12,11
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import json
import re
import argparse
from pathlib import Path
from collections import OrderedDict
from dotenv import load_dotenv
load_dotenv()

from build_report import build_html_report


MONTH_NAMES = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december"
}

# Suffixes to strip for dedup
STRIP_SUFFIXES = [
    "llc", "inc", "corp", "co", "ltd", "llp", "pllc", "pc",
    "group", "company", "the", "of"
]


def normalize_name(name: str) -> str:
    """Normalize business name for deduplication.

    Strips punctuation, common suffixes (LLC, Inc), and lowercases.
    """
    if not name:
        return ""

    # Lowercase
    n = name.lower().strip()

    # Remove punctuation
    n = re.sub(r'[^\w\s]', '', n)

    # Remove common suffixes
    words = n.split()
    cleaned = [w for w in words if w not in STRIP_SUFFIXES]

    # Rejoin and collapse whitespace
    n = " ".join(cleaned).strip()
    n = re.sub(r'\s+', ' ', n)

    return n


def fuzzy_match(name1: str, name2: str) -> bool:
    """Check if two normalized names are fuzzy matches.

    Uses simple substring containment for short names and
    word overlap for longer names.
    """
    if not name1 or not name2:
        return False

    # Exact match
    if name1 == name2:
        return True

    # One contains the other (for short variations like "Smith Dental" vs "Smith Dental Care")
    if name1 in name2 or name2 in name1:
        if min(len(name1), len(name2)) >= 5:  # Avoid matching very short substrings
            return True

    # Word overlap: if 80%+ of words match
    words1 = set(name1.split())
    words2 = set(name2.split())
    if not words1 or not words2:
        return False
    overlap = len(words1 & words2)
    max_words = max(len(words1), len(words2))
    if max_words > 0 and overlap / max_words >= 0.8:
        return True

    return False


def load_hardcoded_merge_groups(merge_groups_path: str = None) -> list:
    """Load hardcoded merge groups from a JSON file.

    File format: list of lists, where each inner list contains name variants
    that should be treated as the same business.

    Example:
    [
        ["The Red Door Group", "Red Door"],
        ["Refresh Medical Spa", "Refresh", "Refresh Spa"],
        ["Fit Form Pilates", "Fit Form Bootcamp", "Fit Form"]
    ]

    Returns list of groups (each a list of name strings).
    """
    if not merge_groups_path:
        return []
    path = Path(merge_groups_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        groups = json.load(f)
    if isinstance(groups, list):
        return groups
    return []


def build_merge_groups(names: list, hardcoded_groups: list = None) -> dict:
    """Build merge groups for fuzzy-matching business names.

    Combines hardcoded merge groups (from production knowledge — e.g., brand
    name variations that can't be detected algorithmically) with automatic
    fuzzy matching.

    Args:
        names: List of business names from all issues
        hardcoded_groups: Optional list of lists with name variants

    Returns dict mapping each normalized name to its canonical form.
    """
    canonical = {}  # normalized_name -> canonical_name
    groups = []  # list of sets of normalized names

    # Seed with hardcoded groups first
    if hardcoded_groups:
        for hg in hardcoded_groups:
            norm_group = set()
            for name in hg:
                norm = normalize_name(name)
                if norm:
                    norm_group.add(norm)
            if norm_group:
                groups.append(norm_group)

    for name in names:
        norm = normalize_name(name)
        if not norm:
            continue

        # Check if this matches any existing group
        matched_group = None
        for group in groups:
            for existing in group:
                if fuzzy_match(norm, existing):
                    matched_group = group
                    break
            if matched_group:
                break

        if matched_group:
            matched_group.add(norm)
        else:
            groups.append({norm})

    # Build canonical mapping (use longest name in each group as canonical)
    for group in groups:
        canon = max(group, key=len)
        for name in group:
            canonical[name] = canon

    return canonical


def load_issue_data(leads_dir: Path, edition: str, month: int, year: int) -> list:
    """Load enriched data for a specific issue."""
    month_name = MONTH_NAMES.get(month, "unknown")
    filename = f"enriched_{edition}_{month_name}_{year}.json"
    filepath = leads_dir / filename
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_year_month_pairs(months_str: str, base_year: int) -> list:
    """Parse month list and resolve year boundaries.

    For months processed newest-first, if we see month 3,2,1,12,11,
    months 12,11 belong to (base_year - 1).

    Returns list of (year, month) tuples, newest first.
    """
    months = [int(m.strip()) for m in months_str.split(",")]
    pairs = []
    current_year = base_year
    prev_month = None

    for m in months:
        if prev_month is not None and m > prev_month:
            # Wrapped to previous year (e.g., going from Jan to Dec)
            current_year -= 1
        pairs.append((current_year, m))
        prev_month = m

    return pairs


def rebuild_flagged_reports(edition: str, year_month_pairs: list, data_dir: str = "data",
                            merge_groups_path: str = None, pages_base_dir: str = None):
    """Rebuild all issue reports with NEW/SEEN flags.

    Processes issues newest-first. For each issue, advertisers not seen
    in any later issue are flagged NEW; those already seen are SEEN.

    Args:
        edition: Edition slug
        year_month_pairs: List of (year, month) tuples, newest first
        data_dir: Path to data directory
        merge_groups_path: Optional path to JSON file with hardcoded merge groups
        pages_base_dir: Optional base directory for page images (subdir per issue)
    """
    leads_dir = Path("leads")
    if not leads_dir.exists():
        print(f"[ERROR] leads/ directory not found")
        return

    # Load all issue data
    all_issues = []
    for year, month in year_month_pairs:
        data = load_issue_data(leads_dir, edition, month, year)
        if data:
            all_issues.append({
                "year": year,
                "month": month,
                "month_name": MONTH_NAMES[month],
                "data": data
            })
            print(f"  Loaded: {MONTH_NAMES[month].title()} {year} ({len(data)} advertisers)")
        else:
            print(f"  Missing: {MONTH_NAMES[month].title()} {year}")

    if not all_issues:
        print("[ERROR] No issue data found")
        return

    # Collect all business names across all issues
    all_names = []
    for issue in all_issues:
        for ad in issue["data"]:
            all_names.append(ad.get("business_name", ""))

    # Build merge groups for fuzzy matching (with optional hardcoded groups)
    hardcoded = load_hardcoded_merge_groups(merge_groups_path)
    if hardcoded:
        print(f"  Loaded {len(hardcoded)} hardcoded merge groups")
    merge_map = build_merge_groups(all_names, hardcoded)

    # Track first appearance (scanning newest to oldest)
    # "first_seen" = the OLDEST issue where the business appears
    # We scan newest-first, so last occurrence in our scan = first appearance
    name_first_seen = {}  # canonical_name -> "month year"

    for issue in reversed(all_issues):  # oldest first
        for ad in issue["data"]:
            norm = normalize_name(ad.get("business_name", ""))
            canon = merge_map.get(norm, norm)
            if canon:
                name_first_seen[canon] = f"{issue['month_name'].title()} {issue['year']}"

    # Load edition config for report title
    editions_path = Path(data_dir) / "editions.json"
    edition_name = edition.replace("-", " ").title()
    if editions_path.exists():
        with open(editions_path, "r", encoding="utf-8") as f:
            editions = json.load(f)
        ed = next((e for e in editions.get("editions", []) if e["slug"] == edition), None)
        if ed:
            edition_name = ed["name"]

    # Rebuild each issue report with flags
    seen_so_far = {}  # canonical_name -> "month year" (tracks what we've seen in newer issues)

    for issue in all_issues:  # newest first
        month_name = issue["month_name"]
        year = issue["year"]
        advertisers = issue["data"]

        # Build flag data for this issue
        flag_data = {}
        new_leads = []
        seen_leads = []

        for ad in advertisers:
            name = ad.get("business_name", "")
            norm = normalize_name(name)
            canon = merge_map.get(norm, norm)

            if canon in seen_so_far:
                # Already appeared in a NEWER issue
                flag_data[name.lower()] = {
                    "status": "SEEN",
                    "first_seen": seen_so_far[canon]
                }
                seen_leads.append(ad)
            else:
                # Check if it appeared in an OLDER issue
                first_seen_label = name_first_seen.get(canon, f"{month_name.title()} {year}")
                if first_seen_label != f"{month_name.title()} {year}":
                    flag_data[name.lower()] = {
                        "status": "SEEN",
                        "first_seen": first_seen_label
                    }
                    seen_leads.append(ad)
                else:
                    flag_data[name.lower()] = {"status": "NEW"}
                    new_leads.append(ad)

        # Sort: NEW first, then SEEN
        sorted_advertisers = new_leads + seen_leads

        # Resolve pages directory for this issue (if provided)
        issue_pages_dir = None
        if pages_base_dir:
            candidate = Path(pages_base_dir) / f"{edition}_{year}_{month:02d}"
            if candidate.exists():
                issue_pages_dir = str(candidate)

        # Build report
        report_file = leads_dir / f"magazine_report_{edition}_{month_name}_{year}_flagged.html"
        build_html_report(
            sorted_advertisers, report_file, edition_name,
            month_name, year, flag_data=flag_data,
            pages_dir=issue_pages_dir
        )

        new_count = len(new_leads)
        seen_count = len(seen_leads)
        print(f"  {month_name.title()} {year}: {new_count} NEW, {seen_count} SEEN -> {report_file}")

        # Update seen_so_far for older issues
        for ad in advertisers:
            norm = normalize_name(ad.get("business_name", ""))
            canon = merge_map.get(norm, norm)
            if canon and canon not in seen_so_far:
                seen_so_far[canon] = f"{month_name.title()} {year}"

    # Summary
    total_unique = len(set(merge_map.values()))
    print(f"\n  Total unique advertisers across all issues: {total_unique}")
    print(f"  Reports rebuilt: {len(all_issues)}")


def main():
    parser = argparse.ArgumentParser(description="Rebuild magazine reports with NEW/SEEN flags")
    parser.add_argument("--edition", required=True, help="Edition slug (e.g., johnsoncounty)")
    parser.add_argument("--year", type=int, default=2026, help="Base year (for newest issue)")
    parser.add_argument("--months", default=None,
                        help="Comma-separated months newest-first (e.g., 3,2,1,12,11,10,9,8)")
    parser.add_argument("--data-dir", default="data", help="Data directory with editions.json")
    parser.add_argument("--merge-groups", default=None,
                        help="Path to JSON file with hardcoded merge groups (list of lists)")
    parser.add_argument("--pages-dir", default=None,
                        help="Base dir for page images (expects subdirs like edition_YYYY_MM/)")
    args = parser.parse_args()

    print(f"{'=' * 60}")
    print(f"  Rebuilding flagged reports: {args.edition}")
    print(f"{'=' * 60}")

    if args.months:
        year_month_pairs = resolve_year_month_pairs(args.months, args.year)
    else:
        # Default: scan leads/ for available issues
        leads_dir = Path("leads")
        year_month_pairs = []
        for month_num in range(12, 0, -1):
            month_name = MONTH_NAMES[month_num]
            for y in [args.year, args.year - 1]:
                filepath = leads_dir / f"enriched_{args.edition}_{month_name}_{y}.json"
                if filepath.exists():
                    year_month_pairs.append((y, month_num))

        # Sort newest first
        year_month_pairs.sort(key=lambda x: (x[0], x[1]), reverse=True)

    if not year_month_pairs:
        print("[ERROR] No issues found. Provide --months or ensure enriched JSON files exist.")
        return

    print(f"  Issues to process: {[(MONTH_NAMES[m].title(), y) for y, m in year_month_pairs]}")
    rebuild_flagged_reports(args.edition, year_month_pairs, args.data_dir,
                            merge_groups_path=args.merge_groups,
                            pages_base_dir=args.pages_dir)

    print(f"\n{'=' * 60}")
    print(f"  DONE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
