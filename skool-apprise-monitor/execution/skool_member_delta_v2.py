"""
skool_member_delta_v2.py — Member Delta Detection (new + churn-risk)

Wraps the scraping logic from skool_apprise_monitor.py without modifying it.
Tracks member appearances over time and surfaces:
  - new_members[]      : members seen for the first time this run
  - churn_risk[]       : members absent for >= churn_threshold_days

State file: {state_dir}/{tenant_id}/member_delta_state.json
Format:
  {
    "handles": {
      "<handle>": {
        "name": str,
        "first_seen": ISO timestamp,
        "last_seen": ISO timestamp,
        "run_count": int,
        "bio": str
      }
    },
    "last_run": ISO timestamp
  }

Usage:
  python execution/skool_member_delta_v2.py --tenant aiautomationsbyjack --dry-run
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

# Add execution dir to path so we can import from skool_apprise_monitor
sys.path.insert(0, str(EXECUTION_DIR))


def load_delta_state(state_dir: Path) -> dict:
    """Load member tracking state. Returns empty state if file not found."""
    path = state_dir / "member_delta_state.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"handles": {}, "last_run": None}


def save_delta_state(state_dir: Path, state: dict):
    """Save state atomically."""
    path = state_dir / "member_delta_state.json"
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


async def scrape_current_members(community: str, max_pages: int = 3, headless: bool = True) -> list:
    """
    Scrape current Skool member list using the apprise monitor's scraper.
    Imports scrape_member_list from skool_apprise_monitor — no modification needed.
    """
    from skool_apprise_monitor import scrape_member_list
    return await scrape_member_list(community, max_pages=max_pages, headless=headless)


def detect_delta(scraped_members: list, state: dict, churn_threshold_days: int = 14) -> tuple:
    """
    Compare scraped members against state.

    Returns:
        (new_members, churn_risk_members, updated_state)
        - new_members: members seen for first time
        - churn_risk_members: members absent >= churn_threshold_days (still tracked in state)
        - updated_state: state dict with this run's data merged in
    """
    now = datetime.now(timezone.utc)
    threshold = timedelta(days=churn_threshold_days)

    scraped_handles = {m["handle"].lower(): m for m in scraped_members if m.get("handle")}

    new_members = []
    handles_state = state.get("handles", {})

    # Update state with current scrape
    for handle, member in scraped_handles.items():
        if handle not in handles_state:
            # New member
            handles_state[handle] = {
                "name": member.get("name", ""),
                "first_seen": now.isoformat(),
                "last_seen": now.isoformat(),
                "run_count": 1,
                "bio": member.get("bio", ""),
            }
            new_members.append(member)
        else:
            # Existing member — update last_seen
            handles_state[handle]["last_seen"] = now.isoformat()
            handles_state[handle]["run_count"] = handles_state[handle].get("run_count", 0) + 1
            handles_state[handle]["bio"] = member.get("bio", handles_state[handle].get("bio", ""))

    # Detect churn risk: in state but not in current scrape AND last_seen > threshold ago
    churn_risk = []
    for handle, info in handles_state.items():
        if handle not in scraped_handles:
            last_seen = datetime.fromisoformat(info["last_seen"])
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            days_absent = (now - last_seen).days
            if days_absent >= churn_threshold_days:
                churn_risk.append({
                    "handle": handle,
                    "name": info.get("name", ""),
                    "bio": info.get("bio", ""),
                    "first_seen": info.get("first_seen"),
                    "last_seen": info.get("last_seen"),
                    "days_absent": days_absent,
                    "profileUrl": f"https://www.skool.com/@{handle}",
                    "community": scraped_members[0].get("community", "") if scraped_members else "",
                    "_churn_risk": True,
                })

    state["handles"] = handles_state
    return new_members, churn_risk, state


async def run_member_delta(config: dict, state_dir: Path, headless: bool = True, dry_run: bool = False) -> tuple:
    """
    Main entry point. Scrapes members, computes delta, saves state.

    Args:
        config: Tenant config dict
        state_dir: Path to state directory for this tenant
        headless: Run browser headlessly
        dry_run: Don't save state, just compute

    Returns:
        (new_members, churn_risk_members)
    """
    community = config["community_slug"]
    max_pages = config["members"].get("max_pages_per_run", 3)
    churn_days = config["members"].get("churn_threshold_days", 14)

    print(f"\n[Member Delta] Scraping {community} (max_pages={max_pages})")
    scraped = await scrape_current_members(community, max_pages=max_pages, headless=headless)
    print(f"  Scraped {len(scraped)} members")

    state = load_delta_state(state_dir)
    previously_known = len(state.get("handles", {}))

    new_members, churn_risk, updated_state = detect_delta(scraped, state, churn_threshold_days=churn_days)

    print(f"  Previously known: {previously_known}")
    print(f"  New members:      {len(new_members)}")
    print(f"  Churn risk:       {len(churn_risk)}")

    if new_members:
        print("  New: " + ", ".join(m.get("name", m.get("handle", "?")) for m in new_members[:5]))
    if churn_risk:
        print("  Churn: " + ", ".join(m.get("name", m.get("handle", "?")) for m in churn_risk[:5]))

    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
        save_delta_state(state_dir, updated_state)
        print(f"  State saved ({len(updated_state['handles'])} total tracked members)")
    else:
        print("  [DRY RUN] State not saved")

    return new_members, churn_risk


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Skool Member Delta Detector v2")
    parser.add_argument("--tenant", required=True, help="Tenant slug (e.g. aiautomationsbyjack)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't save state")
    parser.add_argument("--visible", action="store_true", help="Show browser")
    args = parser.parse_args()

    tenant_dir = EXECUTION_DIR / "tenants" / args.tenant
    config_path = tenant_dir / "config.json"
    if not config_path.exists():
        print(f"ERROR: No config found at {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    state_dir = BASE_DIR / ".tmp" / "intelligence_v2" / args.tenant

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    new_members, churn_risk = await run_member_delta(
        config=config,
        state_dir=state_dir,
        headless=not args.visible,
        dry_run=args.dry_run,
    )

    print(f"\nDone. New: {len(new_members)}, Churn risk: {len(churn_risk)}")
    if new_members:
        print("\nNew members:")
        for m in new_members:
            print(f"  - {m.get('name', m.get('handle'))} | {m.get('bio', '')[:80]}")
    if churn_risk:
        print("\nChurn risk:")
        for m in churn_risk:
            print(f"  - {m.get('name', m.get('handle'))} | absent {m.get('days_absent')}d")


if __name__ == "__main__":
    asyncio.run(main())
