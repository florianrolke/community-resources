"""
skool_catchup_baseline.py — ONE-TIME baseline builder

Loads ALL known members from:
  1. Feb 7 export CSV (6,602 handles)
  2. Batch3 enrichment (769 handles)
  3. Apprise monitor state (60 handles)

Then scrapes current newest members from Skool until heavy overlap with
known set, identifying truly new members since the last batch.

Outputs:
  - .tmp/intelligence_v2/aiautomationsbyjack/master_members.csv (all members)
  - .tmp/intelligence_v2/aiautomationsbyjack/new_since_feb10.csv (truly new)
  - .tmp/intelligence_v2/aiautomationsbyjack/member_delta_state.json (orchestrator state)

Usage:
  python execution/skool_catchup_baseline.py --max-pages 30
  python execution/skool_catchup_baseline.py --max-pages 30 --dry-run
"""

import asyncio
import argparse
import csv
import json
import re
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent
sys.path.insert(0, str(EXECUTION_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")


def load_feb7_handles() -> dict:
    """Load all handles from the Feb 7 export CSV. Returns {handle: {name, bio, ...}}."""
    csv_path = BASE_DIR / "data" / "exports" / "feb7_2026_all_members_7000.csv"
    members = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            handle = row.get("handle", "").strip().lstrip("@").lower()
            if handle:
                members[handle] = {
                    "name": row.get("name", ""),
                    "handle": handle,
                    "bio": row.get("bio", ""),
                    "location": row.get("location", ""),
                    "joinDate": row.get("joinDate", ""),
                    "lastActive": row.get("lastActive", ""),
                    "profileUrl": row.get("profileUrl", ""),
                    "source": "feb7_export",
                }
    return members


def load_batch3_handles() -> dict:
    """Load handles from the batch3 enrichment (Feb 10). Returns {handle: {name, ...}}."""
    batch3_path = BASE_DIR / ".tmp" / "batch3_new_members.json"
    if not batch3_path.exists():
        return {}
    with open(batch3_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    leads = data.get("leads", data) if isinstance(data, dict) else data
    if not isinstance(leads, list):
        return {}

    members = {}
    for m in leads:
        url = m.get("skool", "") or m.get("profileUrl", "") or ""
        match = re.search(r"@([a-z0-9-]+)", url.lower())
        handle = match.group(1) if match else ""
        if not handle:
            handle = m.get("handle", "").strip().lstrip("@").lower()
        if handle:
            members[handle] = {
                "name": m.get("name", ""),
                "handle": handle,
                "bio": m.get("bio", ""),
                "location": f"{m.get('city', '')} ({m.get('country', '')})".strip(" ()"),
                "linkedin": m.get("linkedin", ""),
                "email": m.get("email", ""),
                "website": m.get("website", ""),
                "semantic_summary": m.get("semantic_summary", ""),
                "source": "batch3_feb10",
            }
    return members


def load_apprise_handles() -> set:
    """Load tracked handles from the apprise monitor state."""
    state_path = BASE_DIR / ".tmp" / "apprise_state" / "members_aiautomationsbyjack.json"
    if not state_path.exists():
        return set()
    with open(state_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(s.lower() for s in data.get("seen_ids", []))


async def scrape_newest_members(community: str, max_pages: int = 30) -> list:
    """Scrape newest members from Skool using Playwright. Returns list of member dicts."""
    from skool_apprise_monitor import scrape_member_list

    print(f"\n[Scraping] {community} — up to {max_pages} pages ({max_pages * 30} members)")
    members = await scrape_member_list(
        community=community,
        max_pages=max_pages,
        headless=True,
    )
    return members


def save_master_csv(all_members: dict, output_path: Path):
    """Save all members to a master CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "handle", "name", "bio", "location", "joinDate", "lastActive",
        "profileUrl", "linkedin", "email", "website", "semantic_summary",
        "source", "first_seen", "last_seen", "status",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for handle in sorted(all_members.keys()):
            row = all_members[handle]
            row.setdefault("status", "active")
            writer.writerow(row)
    print(f"  Master CSV: {output_path} ({len(all_members)} members)")


def save_new_members_csv(new_members: list, output_path: Path):
    """Save truly new members to a separate CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not new_members:
        print("  No truly new members found.")
        return
    fieldnames = [
        "handle", "name", "bio", "location", "profileUrl",
        "joinDate", "first_seen",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in new_members:
            writer.writerow(m)
    print(f"  New members CSV: {output_path} ({len(new_members)} members)")


def save_orchestrator_state(all_handles: dict, state_path: Path):
    """Save orchestrator state file so future runs only detect deltas."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "handles": {},
        "last_run": now,
    }
    for handle, info in all_handles.items():
        state["handles"][handle] = {
            "name": info.get("name", ""),
            "first_seen": info.get("first_seen", now),
            "last_seen": info.get("last_seen", now),
            "run_count": 1,
            "bio": info.get("bio", ""),
        }
    tmp = state_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    tmp.replace(state_path)
    print(f"  Orchestrator state: {state_path} ({len(state['handles'])} handles)")


async def main():
    parser = argparse.ArgumentParser(description="One-time baseline builder")
    parser.add_argument("--max-pages", type=int, default=30, help="Pages to scrape (default 30)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save files")
    args = parser.parse_args()

    community = "aiautomationsbyjack"
    state_dir = BASE_DIR / ".tmp" / "intelligence_v2" / community

    print("=" * 60)
    print("SKOOL BASELINE BUILDER — One-time catch-up")
    print("=" * 60)

    # Step 1: Load all known sources
    print("\n[1/5] Loading Feb 7 export...")
    feb7 = load_feb7_handles()
    print(f"  Found {len(feb7)} handles")

    print("\n[2/5] Loading batch3 enrichment (Feb 10)...")
    batch3 = load_batch3_handles()
    print(f"  Found {len(batch3)} handles")

    print("\n[3/5] Loading apprise monitor state...")
    apprise_handles = load_apprise_handles()
    print(f"  Found {len(apprise_handles)} handles")

    # Merge all known handles
    all_known = {}
    for h, info in feb7.items():
        info["first_seen"] = info.get("joinDate", "2026-02-07")
        info["last_seen"] = "2026-02-07"
        all_known[h] = info

    # Overlay batch3 data (richer — has enrichment)
    for h, info in batch3.items():
        if h in all_known:
            # Keep existing, but add enrichment fields
            all_known[h].update({
                k: v for k, v in info.items()
                if v and k in ("linkedin", "email", "website", "semantic_summary")
            })
            all_known[h]["source"] = "feb7_export+batch3"
        else:
            info["first_seen"] = "2026-02-10"
            info["last_seen"] = "2026-02-10"
            all_known[h] = info

    # Add any apprise-only handles
    for h in apprise_handles:
        if h not in all_known:
            all_known[h] = {
                "handle": h, "name": "", "bio": "", "source": "apprise_monitor",
                "first_seen": "2026-02-21", "last_seen": "2026-02-21",
            }

    known_set = set(all_known.keys())
    print(f"\n  Total known handles (merged): {len(known_set)}")

    # Step 2: Scrape current newest members
    print(f"\n[4/5] Scraping current members (newest first, {args.max_pages} pages)...")
    scraped = await scrape_newest_members(community, max_pages=args.max_pages)
    print(f"  Scraped {len(scraped)} members from Skool")

    # Normalize scraped handles
    now = datetime.now(timezone.utc).isoformat()
    scraped_handles = {}
    for m in scraped:
        handle = m.get("handle", "").strip().lstrip("@").lower()
        if not handle:
            url = m.get("profileUrl", "")
            match = re.search(r"@([a-z0-9-]+)", url.lower())
            if match:
                handle = match.group(1)
        if handle:
            scraped_handles[handle] = {
                "handle": handle,
                "name": m.get("name", ""),
                "bio": m.get("bio", ""),
                "location": m.get("location", ""),
                "profileUrl": m.get("profileUrl", ""),
                "joinDate": m.get("joinedAt", ""),
                "first_seen": now,
                "last_seen": now,
                "source": "live_scrape_feb21",
            }

    # Step 3: Find truly new members
    truly_new_handles = set(scraped_handles.keys()) - known_set
    truly_new = [scraped_handles[h] for h in sorted(truly_new_handles)]

    print(f"\n  Scraped: {len(scraped_handles)} unique handles")
    print(f"  Already known: {len(scraped_handles) - len(truly_new_handles)}")
    print(f"  TRULY NEW since Feb 10: {len(truly_new_handles)}")

    if truly_new:
        print(f"\n  First 10 truly new members:")
        for m in truly_new[:10]:
            print(f"    - {m['name']} ({m['handle']}) — joined {m.get('joinDate', '?')[:10]}")

    # Merge scraped data into master (update last_seen for existing, add new)
    for h, info in scraped_handles.items():
        if h in all_known:
            all_known[h]["last_seen"] = now
            all_known[h]["status"] = "active"
            # Update bio if richer
            if info.get("bio") and not all_known[h].get("bio"):
                all_known[h]["bio"] = info["bio"]
        else:
            all_known[h] = info

    print(f"\n  Total master members after merge: {len(all_known)}")

    # Step 4: Save everything
    if args.dry_run:
        print("\n[DRY RUN] Would save:")
        print(f"  - Master CSV: {len(all_known)} rows")
        print(f"  - New members CSV: {len(truly_new)} rows")
        print(f"  - Orchestrator state: {len(all_known)} handles")
    else:
        print("\n[5/5] Saving files...")
        save_master_csv(all_known, state_dir / "master_members.csv")
        save_new_members_csv(truly_new, state_dir / f"new_since_feb10_{datetime.now().strftime('%Y%m%d')}.csv")
        save_orchestrator_state(all_known, state_dir / "member_delta_state.json")

    print(f"\n{'=' * 60}")
    print(f"BASELINE COMPLETE")
    print(f"  Known members: {len(all_known)}")
    print(f"  Truly new since Feb 10: {len(truly_new)}")
    print(f"  State initialized: {'NO (dry-run)' if args.dry_run else 'YES'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
