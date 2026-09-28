#!/usr/bin/env python3
"""
Batch Lead Enrichment with Checkpoint/Resume

Takes a JSON file of leads (from any source: chambers, BNI, magazines)
and enriches each with: website, LinkedIn, company research, emails.

Uses the waterfall pattern: Perplexity → Exa → Tavily with automatic
fallback on rate limits + API key rotation across 6 keys per service.

Checkpoint saves every 5 records — survives interruptions and resumes
exactly where it left off.

Usage:
    python -X utf8 enrich_batch.py --input leads.json --output enriched.json
    python -X utf8 enrich_batch.py --input leads.json --resume
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from lib.enrichment_engine import EnrichmentEngine
from lib.checkpoint import CheckpointManager
from lib.icp_classifier import classify_business
from lib.safe_io import safe_json_write, safe_json_read


def load_leads(input_path: str) -> list[dict]:
    """Load leads from JSON file. Supports multiple formats:
    - Array of lead objects
    - Chamber format: array of chamber objects with 'members' arrays
    - BNI format: object with 'chapters' containing member arrays
    """
    data = safe_json_read(input_path)
    if not data:
        print(f"[ERROR] Could not load {input_path}")
        return []

    # Direct array of leads
    if isinstance(data, list):
        # Check if it's chamber format (objects with 'members' key)
        if data and isinstance(data[0], dict) and "members" in data[0]:
            leads = []
            for chamber in data:
                for member in chamber.get("members", []):
                    member["_source_chamber"] = chamber.get("name", "")
                    member["_source_slug"] = chamber.get("slug", "")
                    leads.append(member)
            return leads
        return data

    # Object with chapters (BNI format)
    if isinstance(data, dict) and "chapters" in data:
        leads = []
        for chapter in data["chapters"]:
            for member in chapter.get("members", []):
                member["_source_chapter"] = chapter.get("name", "")
                leads.append(member)
        return leads

    # Object with results (generic)
    if isinstance(data, dict):
        for key in ["results", "leads", "members", "businesses"]:
            if key in data and isinstance(data[key], list):
                return data[key]

    print(f"[WARN] Unrecognized format in {input_path}")
    return []


def enrich_leads(leads: list[dict], engine: EnrichmentEngine,
                 checkpoint: CheckpointManager, tier_filter: str = None) -> list[dict]:
    """Enrich a list of leads using the waterfall engine.

    Args:
        leads: List of lead dicts (must have 'company' or 'name' key)
        engine: EnrichmentEngine instance
        checkpoint: CheckpointManager for resume capability
        tier_filter: Optional ICP tier filter (e.g., "A,B" to only enrich Tier A and B)
    """
    allowed_tiers = set(tier_filter.upper().split(",")) if tier_filter else None
    enriched = []
    skipped = 0

    for i, lead in enumerate(leads):
        # Determine the lead's identity key
        company = lead.get("company", lead.get("business_name", ""))
        name = lead.get("name", lead.get("contact", ""))
        city = lead.get("city", lead.get("_source_chamber", ""))
        key = f"{company}::{name}" if name else company

        if not key or key == "::":
            continue

        # Filter by ICP tier if specified
        if allowed_tiers:
            tier = lead.get("icp_tier", "D")
            if tier not in allowed_tiers:
                skipped += 1
                continue

        # Skip if already enriched (checkpoint resume)
        if checkpoint.is_done(key):
            enriched.append(checkpoint.get_result(key))
            continue

        print(f"  [{i + 1}/{len(leads)}] Enriching: {company[:50]}", end="")

        # Run enrichment
        result = engine.enrich_lead(company, city=city, person_name=name)

        # Merge with original lead data
        enriched_lead = {**lead, **result}
        enriched_lead["enriched_at"] = datetime.now(timezone.utc).isoformat()

        # Classify ICP if not already done
        if "icp_tier" not in lead:
            category = lead.get("category", "")
            tier, label = classify_business(category)
            enriched_lead["icp_tier"] = tier
            enriched_lead["icp_label"] = label

        checkpoint.save_result(key, enriched_lead)
        enriched.append(enriched_lead)

        li = " + LI" if result.get("linkedin") else ""
        web = " + web" if result.get("website") else ""
        print(f"{li}{web}")

        # Check if all API keys exhausted
        if engine.exa.all_exhausted and engine.tavily.all_exhausted:
            print("\n[STOP] All API keys exhausted. Checkpoint saved — resume later.")
            break

    if skipped:
        print(f"\n  Skipped {skipped} leads (ICP tier filter: {tier_filter})")

    return enriched


def main():
    parser = argparse.ArgumentParser(
        description="Batch enrich leads with LinkedIn, website, and company research"
    )
    parser.add_argument("--input", required=True, help="Input JSON file with leads")
    parser.add_argument("--output", help="Output JSON file (default: input_enriched.json)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--tier", help="Only enrich these ICP tiers (e.g., 'A,B')")
    parser.add_argument("--limit", type=int, help="Max leads to enrich")
    parser.add_argument("--exa-start", type=int, default=0,
                        help="Exa key index to start with (skip exhausted keys)")
    parser.add_argument("--tavily-start", type=int, default=0,
                        help="Tavily key index to start with")
    args = parser.parse_args()

    # Load leads
    leads = load_leads(args.input)
    if not leads:
        return

    if args.limit:
        leads = leads[:args.limit]

    print(f"Loaded {len(leads)} leads from {args.input}")

    # Setup
    engine = EnrichmentEngine(exa_start=args.exa_start, tavily_start=args.tavily_start)
    input_stem = Path(args.input).stem
    checkpoint = CheckpointManager(f"enrich_{input_stem}", save_every=5, output_dir=".tmp")

    if args.resume:
        print(f"  Resuming from checkpoint ({checkpoint.count} already done)")

    # Enrich
    enriched = enrich_leads(leads, engine, checkpoint, tier_filter=args.tier)
    checkpoint.finalize()

    # Save output
    output_path = args.output or str(Path(args.input).with_stem(input_stem + "_enriched"))
    safe_json_write(output_path, enriched)

    # Stats
    li_count = sum(1 for e in enriched if e.get("linkedin"))
    web_count = sum(1 for e in enriched if e.get("website"))
    research_count = sum(1 for e in enriched if e.get("research"))

    print(f"\n{'=' * 60}")
    print(f"  ENRICHMENT COMPLETE")
    print(f"  Total: {len(enriched)} leads")
    print(f"  LinkedIn: {li_count} ({li_count * 100 // max(len(enriched), 1)}%)")
    print(f"  Websites: {web_count} ({web_count * 100 // max(len(enriched), 1)}%)")
    print(f"  Research: {research_count}")
    print(f"  Output: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
