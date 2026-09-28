#!/usr/bin/env python3
"""Magazine Advertiser Pipeline — Full Issue Processor

Orchestrates the full pipeline for one magazine issue:
1. Screenshot pages via Firecrawl (scrape_pages.py)
2. Detect ads via Claude Haiku vision (detect_ads.py)
3. Enrich advertisers (enrich_advertisers.py)
4. Build HTML report (build_report.py)

Usage:
    python process_issue.py --edition johnsoncounty --year 2026 --month 3
    python process_issue.py --edition johnsoncounty --year 2026 --month 3 --skip-enrich
    python process_issue.py --edition johnsoncounty --year 2026 --month 3 --skip-smtp
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from scrape_pages import screenshot_issue
from detect_ads import detect_ads_in_pages
from enrich_advertisers import enrich_advertisers
from build_report import build_html_report


MONTH_NAMES = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december"
}


def load_edition(data_dir: str, edition_slug: str) -> dict:
    """Load edition config from editions.json."""
    editions_path = Path(data_dir) / "editions.json"
    if not editions_path.exists():
        print(f"[ERROR] editions.json not found at {editions_path}")
        return None
    with open(editions_path, "r", encoding="utf-8") as f:
        editions = json.load(f)

    edition = next(
        (e for e in editions.get("editions", []) if e["slug"] == edition_slug),
        None
    )
    if not edition:
        print(f"[ERROR] Edition '{edition_slug}' not found in editions.json")
        print(f"  Available: {[e['slug'] for e in editions.get('editions', [])]}")
    return edition


def build_issuu_slug(edition: dict, month_name: str, year: int) -> str:
    """Build the Issuu slug from edition config + month/year."""
    slug_pattern = edition.get("slug_pattern", "{edition}_{state}_{month}_{year}")
    return slug_pattern.format(
        edition=edition["issuu_name"],
        state=edition.get("state", "").lower(),
        month=month_name,
        year=year
    )


def load_checkpoint(checkpoint_path: Path) -> dict:
    """Load checkpoint state if exists."""
    if checkpoint_path.exists():
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"step": 0, "pages": [], "ads": [], "enriched": []}


def save_checkpoint(checkpoint_path: Path, state: dict):
    """Save checkpoint state."""
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Process a City Lifestyle magazine issue")
    parser.add_argument("--edition", required=True, help="Edition name (e.g., johnsoncounty)")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--skip-enrich", action="store_true", help="Skip enrichment step")
    parser.add_argument("--skip-smtp", action="store_true", help="Skip email SMTP verification")
    parser.add_argument("--data-dir", default="data", help="Data directory with editions.json")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()

    if args.month < 1 or args.month > 12:
        print(f"[ERROR] Invalid month: {args.month}")
        return

    # Load edition config
    edition = load_edition(args.data_dir, args.edition)
    if not edition:
        return

    month_name = MONTH_NAMES[args.month]
    issuu_slug = build_issuu_slug(edition, month_name, args.year)

    print(f"{'=' * 60}")
    print(f"  Processing: {edition['name']} - {month_name.title()} {args.year}")
    print(f"  Issuu slug: {issuu_slug}")
    print(f"{'=' * 60}")

    # Setup directories
    output_dir = Path("leads")
    output_dir.mkdir(exist_ok=True)
    tmp_dir = Path(".tmp") / "magazine_pages" / f"{args.edition}_{args.year}_{args.month}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Checkpoint support
    checkpoint_path = tmp_dir / "checkpoint.json"
    if args.resume:
        state = load_checkpoint(checkpoint_path)
        print(f"  Resuming from step {state['step']}")
    else:
        state = {"step": 0, "pages": [], "ads": [], "enriched": []}

    start_time = time.time()

    # ── Step 1: Screenshot pages ────────────────────────────────
    if state["step"] < 1:
        print("\n[Step 1/4] Screenshotting pages from Issuu...")
        pages = screenshot_issue(issuu_slug, tmp_dir)
        if not pages:
            print("[ERROR] No pages captured. Check Issuu slug and Firecrawl API key.")
            return
        state["pages"] = [str(p) for p in pages]
        state["step"] = 1
        save_checkpoint(checkpoint_path, state)
        print(f"  Captured {len(pages)} pages")
    else:
        pages = [Path(p) for p in state["pages"]]
        print(f"\n[Step 1/4] Loaded {len(pages)} pages from checkpoint")

    # ── Step 2: Detect ads ──────────────────────────────────────
    if state["step"] < 2:
        print("\n[Step 2/4] Detecting ads via Claude Haiku vision...")
        ads = detect_ads_in_pages(pages, tmp_dir)
        state["ads"] = ads
        state["step"] = 2
        save_checkpoint(checkpoint_path, state)
        print(f"  Detected {len(ads)} advertisers")
    else:
        ads = state["ads"]
        print(f"\n[Step 2/4] Loaded {len(ads)} ads from checkpoint")

    # ── Step 3: Enrich advertisers ──────────────────────────────
    if not args.skip_enrich:
        if state["step"] < 3:
            print("\n[Step 3/4] Enriching advertisers...")
            enriched = enrich_advertisers(ads, verify_smtp=not args.skip_smtp)
            state["enriched"] = enriched
            state["step"] = 3
            save_checkpoint(checkpoint_path, state)
            print(f"  Enriched {len(enriched)} advertisers")
        else:
            enriched = state["enriched"]
            print(f"\n[Step 3/4] Loaded {len(enriched)} enriched from checkpoint")
    else:
        enriched = ads
        print("\n[Step 3/4] Skipped enrichment (--skip-enrich)")

    # Save enriched data
    output_file = output_dir / f"enriched_{args.edition}_{month_name}_{args.year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {output_file}")

    # ── Step 4: Build HTML report ───────────────────────────────
    print("\n[Step 4/4] Building HTML report...")
    report_file = output_dir / f"magazine_report_{args.edition}_{month_name}_{args.year}.html"
    build_html_report(enriched, report_file, edition["name"], month_name, args.year)
    print(f"  Report: {report_file}")

    # Summary
    elapsed = time.time() - start_time
    linkedin_count = sum(1 for a in enriched if a.get("linkedin_url"))
    email_count = sum(1 for a in enriched if a.get("email"))
    owner_count = sum(1 for a in enriched if a.get("owner_name"))

    print(f"\n{'=' * 60}")
    print(f"  DONE: {len(enriched)} advertisers processed in {elapsed:.0f}s")
    print(f"  Owners: {owner_count} | LinkedIn: {linkedin_count} | Emails: {email_count}")
    print(f"  Report: {report_file}")
    print(f"{'=' * 60}")

    # Clean up checkpoint on success
    if checkpoint_path.exists():
        checkpoint_path.unlink()


if __name__ == "__main__":
    main()
