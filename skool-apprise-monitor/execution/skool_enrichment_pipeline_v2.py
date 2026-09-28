"""
skool_enrichment_pipeline_v2.py — Member Enrichment Pipeline

Wraps existing enrichment scripts without modifying them:
  - find_linkedin_profiles.py → LinkedIn URL
  - enrich_leads_v2.py → Perplexity semantic summary (services, industries, revenue signals)

Enrichment cache: {state_dir}/enrichment_cache.json
Skips members enriched within cache_days to stay within token budget.

Max 20 members enriched per run (configurable via tenant config).

Usage:
  python execution/skool_enrichment_pipeline_v2.py --tenant aiautomationsbyjack --dry-run
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


def load_enrichment_cache(state_dir: Path) -> dict:
    """Load enrichment cache. Returns empty dict if not found."""
    path = state_dir / "enrichment_cache.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_enrichment_cache(state_dir: Path, cache: dict):
    """Save enrichment cache atomically."""
    path = state_dir / "enrichment_cache.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def is_cache_valid(cache_entry: dict, cache_days: int) -> bool:
    """Check if a cache entry is still fresh."""
    enriched_at = cache_entry.get("enriched_at")
    if not enriched_at:
        return False
    try:
        dt = datetime.fromisoformat(enriched_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) < timedelta(days=cache_days)
    except (ValueError, TypeError):
        return False


def _find_linkedin(member: dict) -> dict:
    """
    Find LinkedIn URL using find_linkedin_profiles.py waterfall.
    Returns member dict with 'linkedin' and 'linkedin_source' fields added.
    """
    try:
        from find_linkedin_profiles import find_linkedin_for_member
        return find_linkedin_for_member(member, skip_apollo=False)
    except (ImportError, Exception) as e:
        print(f"  LinkedIn finder error for {member.get('name', '?')}: {e}")
        return {**member, "linkedin": None, "linkedin_source": "error"}


def _run_perplexity_enrichment(member: dict) -> dict:
    """
    Run semantic enrichment via enrich_leads_v2.py.
    Returns enrichment dict with services, industries, revenue signals etc.
    """
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")

        from enrich_leads_v2 import enrich_single_lead
        import openai
        from tavily import TavilyClient

        # Build clients
        perplexity_client = openai.OpenAI(
            api_key=os.getenv("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
        )
        tavily_key = os.getenv("TAVILY_API_KEY_5") or os.getenv("TAVILY_API_KEY")
        tavily_client = TavilyClient(api_key=tavily_key) if tavily_key else None
        exa_client = None  # Exa keys exhausted per memory

        # Build lead dict in format enrich_leads_v2 expects
        lead = {
            "name": member.get("name", ""),
            "first_name": member.get("name", "").split()[0] if member.get("name") else "",
            "last_name": " ".join(member.get("name", "").split()[1:]) if member.get("name") else "",
            "linkedin_url": member.get("linkedin", ""),
            "websites": [],
            "notes": member.get("bio", ""),
        }
        result = enrich_single_lead((perplexity_client, tavily_client, exa_client), lead)
        return result.get("enrichment", {})

    except (ImportError, Exception) as e:
        print(f"  Enrichment error for {member.get('name', '?')}: {e}")
        # Return basic enrichment from bio parsing
        return _basic_enrichment_from_bio(member)


def _basic_enrichment_from_bio(member: dict) -> dict:
    """Minimal enrichment when API not available — parse bio only."""
    bio = member.get("bio", "")
    return {
        "bio_summary": bio[:500],
        "services": [],
        "industries": [],
        "pain_signals": [],
        "revenue_signals": "",
        "employee_count": "",
        "company_name": "",
        "website": None,
        "email": None,
        "linkedin_url": member.get("linkedin"),
        "sources_used": ["bio_only"],
        "confidence": "low",
    }


def enrich_member(member: dict, cache: dict, cache_days: int = 30, dry_run: bool = False) -> dict:
    """
    Enrich a single member. Checks cache first.

    Returns member dict enriched with:
      - linkedin (str or None)
      - linkedin_source (str)
      - enrichment (dict from Perplexity)
      - enriched_at (ISO timestamp)
    """
    handle = member.get("handle", "").lower()

    # Check cache
    if handle in cache and is_cache_valid(cache[handle], cache_days):
        print(f"  Cache hit: {member.get('name', handle)}")
        cached = cache[handle]
        return {**member, **cached}

    if dry_run:
        print(f"  [DRY RUN] Would enrich: {member.get('name', handle)}")
        return {**member, "linkedin": None, "linkedin_source": "dry_run",
                "enrichment": _basic_enrichment_from_bio(member),
                "enriched_at": datetime.now(timezone.utc).isoformat()}

    print(f"  Enriching: {member.get('name', handle)}")

    # Step 1: LinkedIn
    member_with_linkedin = _find_linkedin(member)
    time.sleep(5)  # Rate limit between LinkedIn + Perplexity calls

    # Step 2: Perplexity semantic summary
    enrichment = _run_perplexity_enrichment(member_with_linkedin)
    time.sleep(2)

    enriched = {
        **member_with_linkedin,
        "enrichment": enrichment,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Cache result
    cache[handle] = {
        "linkedin": enriched.get("linkedin"),
        "linkedin_source": enriched.get("linkedin_source", ""),
        "enrichment": enrichment,
        "enriched_at": enriched["enriched_at"],
    }

    return enriched


def enrich_members_batch(
    members: list,
    config: dict,
    state_dir: Path,
    dry_run: bool = False,
) -> list:
    """
    Enrich a batch of members (new + churn-risk combined).

    Applies max_enrich_per_run limit and cache.
    Returns list of enriched member dicts.
    """
    max_per_run = config["members"].get("max_enrich_per_run", 20)
    cache_days = config["members"].get("enrich_cache_days", 30)

    cache = load_enrichment_cache(state_dir)
    handle_cache = {h: v for h, v in cache.items()}

    # Count cache hits to estimate how many fresh enrichments we'll need
    to_enrich = []
    for m in members:
        handle = m.get("handle", "").lower()
        if handle in handle_cache and is_cache_valid(handle_cache[handle], cache_days):
            to_enrich.insert(0, m)  # Prioritize cached (fast)
        else:
            to_enrich.append(m)

    # Apply limit (after cache hits are counted)
    if len(to_enrich) > max_per_run:
        print(f"  Enrichment capped at {max_per_run} (of {len(to_enrich)} members)")
        to_enrich = to_enrich[:max_per_run]

    enriched_results = []
    for i, member in enumerate(to_enrich):
        print(f"  [{i+1}/{len(to_enrich)}] ", end="")
        result = enrich_member(member, handle_cache, cache_days=cache_days, dry_run=dry_run)
        enriched_results.append(result)

    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
        save_enrichment_cache(state_dir, handle_cache)
        print(f"  Enrichment cache updated ({len(handle_cache)} entries)")

    return enriched_results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Skool Enrichment Pipeline v2")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--member", help="Path to single member JSON file (for testing)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    tenant_dir = EXECUTION_DIR / "tenants" / args.tenant
    with open(tenant_dir / "config.json", "r") as f:
        config = json.load(f)

    state_dir = BASE_DIR / ".tmp" / "intelligence_v2" / args.tenant

    if args.member:
        with open(args.member, "r") as f:
            member = json.load(f)
        cache = {}
        result = enrich_member(member, cache, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Pass --member <path> to test enrichment on a single member JSON file.")


if __name__ == "__main__":
    main()
