#!/usr/bin/env python3
"""
BNI member enrichment using the waterfall engine.

Takes scraped BNI members and enriches with LinkedIn profiles and websites.
BNI members have high LinkedIn hit rates (~92%) because they're active
business networkers with consistent name+company pairings.

Usage:
    python enrich_members.py --input leads/bni_all_members.json --output leads/enriched_members.json
    python enrich_members.py --input leads/bni_all_members.json --resume
    python enrich_members.py --input leads/bni_all_members.json --tier A,B
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from lib.enrichment_engine import EnrichmentEngine
from lib.checkpoint import CheckpointManager
from lib.icp_classifier import classify_business

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# BNI members are active networkers -- LinkedIn search pattern is highly effective
LINKEDIN_SEARCH_TEMPLATE = '"{name}" "{company}" site:linkedin.com/in'
WEBSITE_SEARCH_TEMPLATE = '"{company}" {city} {state} website'

# Rate limiting
DEFAULT_DELAY = 2.0  # seconds between API calls
PAUSE_EVERY = 15  # pause after this many calls
PAUSE_DURATION = 10  # seconds to pause


# ---------------------------------------------------------------------------
# Enrichment logic
# ---------------------------------------------------------------------------


def enrich_single_member(
    engine: EnrichmentEngine, member: dict, delay: float = DEFAULT_DELAY
) -> dict:
    """
    Enrich a single BNI member with LinkedIn profile and additional data.

    Search strategy:
    1. LinkedIn lookup via "{name}" "{company}" site:linkedin.com/in
    2. Website lookup if not already present
    3. Additional company info

    Returns the member dict with enrichment fields added.
    """
    name = member.get("name", "").strip()
    company = member.get("company", "").strip()
    city = member.get("city", "").strip()
    state = member.get("state", "").strip()

    if not name:
        member["enrichment_status"] = "skipped_no_name"
        return member

    print(f"  [ENRICH] {name} @ {company}")

    # --- LinkedIn lookup ---
    if not member.get("linkedin"):
        query = LINKEDIN_SEARCH_TEMPLATE.format(name=name, company=company)
        try:
            result = engine.search(query, num_results=3)
            if result:
                for r in result:
                    url = r.get("url", "")
                    if "linkedin.com/in/" in url:
                        member["linkedin"] = url
                        print(f"    [LI] Found: {url}")
                        break
            if not member.get("linkedin"):
                # Fallback: try name-only search
                query_simple = f'"{name}" site:linkedin.com/in'
                result2 = engine.search(query_simple, num_results=3)
                if result2:
                    for r in result2:
                        url = r.get("url", "")
                        if "linkedin.com/in/" in url:
                            member["linkedin"] = url
                            print(f"    [LI] Found (name-only): {url}")
                            break
        except Exception as e:
            print(f"    [LI-ERR] {e}")

        time.sleep(delay)

    # --- Website lookup (if not already present) ---
    if not member.get("website") and company:
        query = WEBSITE_SEARCH_TEMPLATE.format(
            company=company, city=city, state=state
        )
        try:
            result = engine.search(query, num_results=3)
            if result:
                for r in result:
                    url = r.get("url", "")
                    # Skip social media and directory sites
                    skip_domains = [
                        "linkedin.com", "facebook.com", "yelp.com",
                        "yellowpages.com", "bbb.org", "mapquest.com",
                        "bni.com", "instagram.com", "twitter.com",
                    ]
                    if url and not any(d in url for d in skip_domains):
                        member["website"] = url
                        print(f"    [WEB] Found: {url}")
                        break
        except Exception as e:
            print(f"    [WEB-ERR] {e}")

        time.sleep(delay)

    # --- Re-classify ICP if we have more info now ---
    if member.get("website") or member.get("linkedin"):
        try:
            classification = classify_business(
                company, member.get("category", ""), member.get("website", "")
            )
            member["icp_tier"] = classification.get("tier", member.get("icp_tier", "D"))
            member["icp_reason"] = classification.get("reason", "")
        except Exception:
            pass

    member["enriched_at"] = datetime.now(timezone.utc).isoformat()
    member["enrichment_status"] = "complete"

    status_parts = []
    if member.get("linkedin"):
        status_parts.append("LI")
    if member.get("website"):
        status_parts.append("WEB")
    print(f"    [DONE] {' + '.join(status_parts) if status_parts else 'no new data'}")

    return member


def enrich_members(
    input_path: str,
    output_path: str,
    resume: bool = True,
    tier_filter: list[str] | None = None,
    delay: float = DEFAULT_DELAY,
    max_members: int = 0,
):
    """
    Enrich all BNI members from input file.

    Uses checkpoint/resume pattern: saves progress every 5 members so
    interrupted runs can continue where they left off.
    """
    # Load input
    inp = Path(input_path)
    if not inp.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    with open(inp, "r", encoding="utf-8") as f:
        members = json.load(f)

    print(f"[LOADED] {len(members)} members from {input_path}")

    # Filter by ICP tier if requested
    if tier_filter:
        tier_filter_upper = [t.upper() for t in tier_filter]
        members = [m for m in members if m.get("icp_tier", "D") in tier_filter_upper]
        print(f"[FILTER] {len(members)} members in tiers: {', '.join(tier_filter_upper)}")

    # Limit if requested
    if max_members > 0:
        members = members[:max_members]
        print(f"[LIMIT] Processing first {max_members} members")

    # Initialize checkpoint
    script_dir = Path(__file__).resolve().parent
    checkpoint_path = script_dir / ".tmp" / "bni_enrich_checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    cp = CheckpointManager(str(checkpoint_path))

    # Determine which members still need enrichment
    if resume:
        completed_keys = set(cp.get_completed_keys())
        to_process = []
        already_enriched = []
        for m in members:
            key = f"{m.get('name', '')}|{m.get('company', '')}"
            if key in completed_keys:
                # Load the enriched version from checkpoint
                enriched = cp.get_result(key)
                if enriched:
                    already_enriched.append(enriched)
                else:
                    already_enriched.append(m)
            else:
                to_process.append(m)
        print(f"[RESUME] {len(already_enriched)} already enriched, {len(to_process)} remaining")
    else:
        to_process = members
        already_enriched = []

    if not to_process:
        print("[DONE] All members already enriched")
        all_enriched = already_enriched
    else:
        # Initialize enrichment engine
        engine = EnrichmentEngine()
        print(f"[ENGINE] Initialized with available API keys")

        all_enriched = list(already_enriched)
        call_count = 0

        for i, member in enumerate(to_process, 1):
            key = f"{member.get('name', '')}|{member.get('company', '')}"
            print(f"\n[{i}/{len(to_process)}] Enriching: {member.get('name', '?')}")

            enriched = enrich_single_member(engine, member, delay=delay)
            all_enriched.append(enriched)

            # Save to checkpoint
            cp.mark_complete(key, enriched)
            call_count += 1

            # Checkpoint save every 5 members
            if i % 5 == 0:
                _save_intermediate(all_enriched, output_path)
                print(f"  [CHECKPOINT] Saved {len(all_enriched)} members")

            # Rate limit pause
            if call_count % PAUSE_EVERY == 0:
                print(f"  [PAUSE] {PAUSE_DURATION}s cooldown after {call_count} API calls")
                time.sleep(PAUSE_DURATION)

    # Final save
    _save_intermediate(all_enriched, output_path)

    # Summary
    total = len(all_enriched)
    with_linkedin = sum(1 for m in all_enriched if m.get("linkedin"))
    with_website = sum(1 for m in all_enriched if m.get("website"))
    with_phone = sum(1 for m in all_enriched if m.get("phone"))

    print(f"\n{'='*60}")
    print(f"[ENRICHMENT COMPLETE]")
    print(f"  Total members: {total}")
    print(f"  LinkedIn: {with_linkedin} ({with_linkedin/total*100:.0f}%)" if total else "  LinkedIn: 0")
    print(f"  Website: {with_website} ({with_website/total*100:.0f}%)" if total else "  Website: 0")
    print(f"  Phone: {with_phone} ({with_phone/total*100:.0f}%)" if total else "  Phone: 0")

    # Tier breakdown
    tiers = {}
    for m in all_enriched:
        tier = m.get("icp_tier", "D")
        tiers[tier] = tiers.get(tier, 0) + 1
    print(f"  ICP tiers: {', '.join(f'{t}={c}' for t, c in sorted(tiers.items()))}")

    return all_enriched


def _save_intermediate(members: list[dict], output_path: str):
    """Save current enrichment results."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(members, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Enrich BNI members with LinkedIn and website data")
    parser.add_argument("--input", default="leads/bni_all_members.json",
                        help="Input JSON file with scraped members")
    parser.add_argument("--output", default="leads/enriched_members.json",
                        help="Output JSON file for enriched members")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from checkpoint (default: True)")
    parser.add_argument("--no-resume", action="store_true",
                        help="Start fresh, ignore checkpoint")
    parser.add_argument("--tier", type=str, default=None,
                        help="Filter by ICP tier(s), comma-separated (e.g., A,B)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Delay between API calls in seconds (default: {DEFAULT_DELAY})")
    parser.add_argument("--max", type=int, default=0,
                        help="Max members to process (0 = all)")
    args = parser.parse_args()

    # Resolve paths relative to script directory
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / args.input
    output_path = script_dir / args.output

    tier_filter = None
    if args.tier:
        tier_filter = [t.strip() for t in args.tier.split(",")]

    enrich_members(
        input_path=str(input_path),
        output_path=str(output_path),
        resume=not args.no_resume,
        tier_filter=tier_filter,
        delay=args.delay,
        max_members=args.max,
    )


if __name__ == "__main__":
    main()
