"""
skool_intelligence_orchestrator_v2.py — Skool Intelligence System v2

Main entry point for the config-driven, multi-tenant community intelligence pipeline.

Runs 2 jobs per invocation:
  Job A: Member Delta
    1. Scrape current members → detect new + churn-risk
    2. Enrich (LinkedIn + Perplexity semantic summary)
    3. Score (Financial Qualification + Heroes Arc ICP — independent tracks)
    4. Route alerts to configured recipients
    5. Draft personalized messages → email to Florian

  Job B: Post Monitor
    1. Scrape posts since last run
    2. Detect monetary wins + anti-gravity mentions
    3. Vectorize new posts to Supabase
    4. Route alerts

Designed to run 3x/day (8am, 2pm, 8pm EST) via Coolify cron.

Usage:
  python execution/skool_intelligence_orchestrator_v2.py --tenant aiautomationsbyjack
  python execution/skool_intelligence_orchestrator_v2.py --tenant aiautomationsbyjack --dry-run
  python execution/skool_intelligence_orchestrator_v2.py --tenant aiautomationsbyjack --job members
  python execution/skool_intelligence_orchestrator_v2.py --tenant aiautomationsbyjack --job posts
  python execution/skool_intelligence_orchestrator_v2.py --tenant aiautomationsbyjack --visible
"""

import asyncio
import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


# ============================================================================
# Config Loading
# ============================================================================

def load_tenant_config(tenant_slug: str) -> dict:
    """Load tenant config from execution/tenants/{slug}/config.json."""
    config_path = EXECUTION_DIR / "tenants" / tenant_slug / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"No config found at {config_path}\n"
            f"Create it with the tenant config template. Available tenants: "
            + ", ".join(d.name for d in (EXECUTION_DIR / "tenants").iterdir() if d.is_dir())
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_state_dir(tenant_slug: str) -> Path:
    """State directory for this tenant's run data."""
    return BASE_DIR / ".tmp" / "intelligence_v2" / tenant_slug


# ============================================================================
# Job A: Member Delta
# ============================================================================

async def run_job_a_members(config: dict, state_dir: Path, headless: bool = True,
                           dry_run: bool = False, init_mode: bool = False) -> dict:
    """
    Job A: Member Delta → Enrich → Score → Alert → Draft

    If init_mode=True, only scrapes + saves state (no enrich/score/alert).
    Returns summary dict with counts and qualified member list.
    """
    tenant_id = config["tenant_id"]
    fin_threshold = config["scoring"]["financial"]["threshold_alert"]
    icp_threshold = config["scoring"]["heroes_arc_icp"]["threshold_alert"]

    print(f"\n{'='*60}")
    print(f"JOB A: MEMBER DELTA — {tenant_id}" + (" [INIT MODE]" if init_mode else ""))
    print(f"{'='*60}")

    # Step 1: Member delta
    from skool_member_delta_v2 import run_member_delta
    new_members, churn_risk = await run_member_delta(
        config=config,
        state_dir=state_dir,
        headless=headless,
        dry_run=dry_run,
    )

    all_flagged = new_members + churn_risk

    # In init mode, just save state and return counts — no enrichment or alerting
    if init_mode:
        print(f"\n[INIT MODE] State saved. {len(new_members)} new, {len(churn_risk)} churn-risk.")
        print(f"  Skipping enrichment, scoring, and alerting.")
        return {
            "new_count": len(new_members), "churn_count": len(churn_risk),
            "qualified_count": 0, "new_qualified": 0, "churn_qualified": 0,
            "qualified": [], "mode": "init",
        }

    if not all_flagged:
        print("\n  No new members or churn-risk members this run.")
        return {"new_count": 0, "churn_count": 0, "qualified_count": 0, "qualified": []}

    # Step 2: Enrich
    print(f"\n[Enrichment] Processing {len(all_flagged)} members...")
    from skool_enrichment_pipeline_v2 import enrich_members_batch
    enriched = enrich_members_batch(
        members=all_flagged,
        config=config,
        state_dir=state_dir,
        dry_run=dry_run,
    )

    # Step 3: Score (both tracks)
    print(f"\n[Scoring] Scoring {len(enriched)} members...")
    from skool_icp_scorer_v2 import score_all_members
    scored = score_all_members(enriched, config)

    # Step 4: Filter qualified
    qualified = [
        m for m in scored
        if m.get("financial_score", 0) >= fin_threshold or m.get("icp_score", 0) >= icp_threshold
    ]

    new_qualified = [m for m in qualified if not m.get("_churn_risk")]
    churn_qualified = [m for m in qualified if m.get("_churn_risk")]

    print(f"\n[Results] {len(qualified)} qualified of {len(scored)} scored")
    print(f"  New qualified:   {len(new_qualified)}")
    print(f"  Churn qualified: {len(churn_qualified)}")

    # Step 5: Alerts + Message Drafts
    from skool_alert_router_v2 import route_alert
    from skool_message_drafter_v2 import draft_and_send

    messaging_mode = config.get("messaging", {}).get("mode", "off")

    for member in qualified:
        signal_type = "churn_qualified_member" if member.get("_churn_risk") else "new_qualified_member"
        name = member.get("name", member.get("handle", "?"))
        fin_score = member.get("financial_score", "?")
        icp_score = member.get("icp_score", "?")
        fin_tier = member.get("financial_tier", "?")
        icp_tier = member.get("icp_tier", "?")

        print(f"\n  → {name} [{signal_type}] F:{fin_tier}({fin_score}) ICP:{icp_tier}({icp_score})")

        # Draft message first (so draft is included in alert email)
        if messaging_mode != "off":
            print(f"    Drafting message...")
            draft_and_send(member, signal_type, config, dry_run=dry_run)

        # Route alert
        print(f"    Routing alerts...")
        route_alert(signal_type, member, config, dry_run=dry_run)

    return {
        "new_count": len(new_members),
        "churn_count": len(churn_risk),
        "qualified_count": len(qualified),
        "new_qualified": len(new_qualified),
        "churn_qualified": len(churn_qualified),
        "qualified": qualified,
    }


# ============================================================================
# Job B: Post Monitor
# ============================================================================

async def run_job_b_posts(config: dict, state_dir: Path, dry_run: bool = False) -> dict:
    """
    Job B: Post Monitor → Detect Signals → Vectorize → Alert

    Returns summary dict with win/mention counts.
    """
    tenant_id = config["tenant_id"]

    if not config.get("posts", {}).get("enabled", True):
        print(f"\n[Post Monitor] Disabled for {tenant_id} — skipping.")
        return {"wins_count": 0, "mentions_count": 0, "wins": [], "mentions": []}

    print(f"\n{'='*60}")
    print(f"JOB B: POST MONITOR — {tenant_id}")
    print(f"{'='*60}")

    from skool_post_pipeline_v2 import run_post_pipeline
    from skool_alert_router_v2 import route_alert

    monetary_wins, antigravity_mentions = await run_post_pipeline(
        config=config,
        state_dir=state_dir,
        dry_run=dry_run,
    )

    print(f"\n[Post Results] {len(monetary_wins)} wins, {len(antigravity_mentions)} mentions")

    # Route alerts for wins
    for post in monetary_wins:
        print(f"  → Monetary win: '{post.get('title', '')[:60]}...'")
        route_alert("monetary_win", post, config, dry_run=dry_run)

    # Route alerts for anti-gravity mentions
    for post in antigravity_mentions:
        print(f"  → AntiGravity mention: '{post.get('title', '')[:60]}...'")
        route_alert("antigravity_mention", post, config, dry_run=dry_run)

    return {
        "wins_count": len(monetary_wins),
        "mentions_count": len(antigravity_mentions),
        "wins": monetary_wins,
        "mentions": antigravity_mentions,
    }


# ============================================================================
# Run Summary
# ============================================================================

def print_run_summary(tenant_id: str, job_a_result: dict, job_b_result: dict, elapsed_seconds: float):
    """Print a clean summary of the run."""
    print(f"\n{'='*60}")
    print(f"RUN SUMMARY — {tenant_id}")
    print(f"{'='*60}")

    if job_a_result:
        print(f"Member Delta:")
        print(f"  New members:    {job_a_result.get('new_count', 0)}")
        print(f"  Churn risk:     {job_a_result.get('churn_count', 0)}")
        print(f"  Qualified:      {job_a_result.get('qualified_count', 0)} "
              f"(new: {job_a_result.get('new_qualified', 0)}, churn: {job_a_result.get('churn_qualified', 0)})")

    if job_b_result:
        print(f"\nPost Monitor:")
        print(f"  Monetary wins:      {job_b_result.get('wins_count', 0)}")
        print(f"  AntiGravity mentions: {job_b_result.get('mentions_count', 0)}")

    print(f"\nCompleted in {elapsed_seconds:.1f}s at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")


# ============================================================================
# Main
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Skool Intelligence Orchestrator v2 — Multi-tenant community intelligence"
    )
    parser.add_argument("--tenant", required=True, help="Tenant slug (e.g. aiautomationsbyjack)")
    parser.add_argument(
        "--job",
        choices=["members", "posts", "both"],
        default="both",
        help="Which job to run (default: both)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute everything but don't save state or send alerts")
    parser.add_argument("--visible", action="store_true",
                        help="Show Playwright browser window (useful for debugging)")
    parser.add_argument("--init", action="store_true",
                        help="Initialize state only — scrape + save baseline, no alerts")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    mode_label = "INIT (baseline)" if args.init else ("DRY RUN" if args.dry_run else "LIVE")
    print(f"\nSkool Intelligence Orchestrator v2")
    print(f"Tenant: {args.tenant}")
    print(f"Job:    {args.job}")
    print(f"Mode:   {mode_label}")
    print(f"Time:   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Load config
    config = load_tenant_config(args.tenant)
    state_dir = get_state_dir(args.tenant)
    state_dir.mkdir(parents=True, exist_ok=True)

    headless = not args.visible
    start_time = time.time()

    job_a_result = None
    job_b_result = None

    # Run jobs
    if args.job in ("members", "both"):
        job_a_result = await run_job_a_members(
            config=config,
            state_dir=state_dir,
            headless=headless,
            dry_run=args.dry_run,
            init_mode=args.init,
        )

    if args.job in ("posts", "both") and not args.init:
        job_b_result = await run_job_b_posts(
            config=config,
            state_dir=state_dir,
            dry_run=args.dry_run,
        )
    elif args.init and args.job in ("posts", "both"):
        print(f"\n[INIT MODE] Skipping post monitor — init only saves member state.")

    elapsed = time.time() - start_time
    print_run_summary(args.tenant, job_a_result, job_b_result, elapsed)

    # Save run log for daily digest
    run_log = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "tenant": args.tenant,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "mode": "init" if args.init else ("dry_run" if args.dry_run else "live"),
        "job_a": job_a_result or {},
        "job_b": job_b_result or {},
    }
    run_log_dir = state_dir / "run_logs"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = run_log_dir / f"{run_log['run_id']}.json"
    with open(run_log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2, default=str)
    print(f"\nRun log saved: {run_log_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
