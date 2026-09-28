"""
skool_post_pipeline_v2.py — Post Monitoring + Vectorization

Wraps skool_post_scraper.py and vectorize_posts_to_supabase.py.

Jobs:
  1. Scrape posts since last watermark
  2. Detect monetary win posts → return list
  3. Detect anti-gravity mention posts → return list
  4. Vectorize new posts to Supabase (configurable per tenant)
  5. Update post watermark

State: {state_dir}/post_watermark.json
  {"last_post_id": str, "last_run": ISO timestamp}

Usage:
  python execution/skool_post_pipeline_v2.py --tenant aiautomationsbyjack --dry-run
"""

import re
import json
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


def load_post_watermark(state_dir: Path) -> dict:
    path = state_dir / "post_watermark.json"
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"last_post_id": None, "last_run": None}


def save_post_watermark(state_dir: Path, last_post_id: str):
    path = state_dir / "post_watermark.json"
    tmp = path.with_suffix(".tmp")
    data = {
        "last_post_id": last_post_id,
        "last_run": datetime.now(timezone.utc).isoformat(),
    }
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def detect_post_signals(posts: list, config: dict) -> tuple:
    """
    Scan posts for monetary wins and anti-gravity mentions.

    Returns:
        (monetary_wins, antigravity_mentions)
    """
    win_keywords = config["posts"].get("monetary_win_keywords", [])
    ag_keywords = config["posts"].get("antigravity_keywords", [])

    # Build regex patterns (case-insensitive, word boundaries where sensible)
    win_pattern = re.compile(
        "|".join(re.escape(kw) for kw in win_keywords),
        re.IGNORECASE
    ) if win_keywords else None

    ag_pattern = re.compile(
        "|".join(re.escape(kw) for kw in ag_keywords),
        re.IGNORECASE
    ) if ag_keywords else None

    monetary_wins = []
    antigravity_mentions = []

    for post in posts:
        text = f"{post.get('title', '')} {post.get('content', '')}".strip()

        if win_pattern and win_pattern.search(text):
            matches = win_pattern.findall(text)
            monetary_wins.append({
                **post,
                "_signal_type": "monetary_win",
                "_matched_keywords": list(set(m.lower() for m in matches)),
            })

        if ag_pattern and ag_pattern.search(text):
            matches = ag_pattern.findall(text)
            antigravity_mentions.append({
                **post,
                "_signal_type": "antigravity_mention",
                "_matched_keywords": list(set(m.lower() for m in matches)),
            })

    return monetary_wins, antigravity_mentions


async def scrape_new_posts(community: str, lookback_hours: int = 8, max_posts: int = 200) -> list:
    """
    Scrape posts from the community since lookback_hours ago.
    Uses SkoolPostScraper from skool_post_scraper.py.
    """
    try:
        from skool_post_scraper import SkoolPostScraper

        scraper = SkoolPostScraper(community, headless=True)
        try:
            await scraper.start()
            posts = await scraper.scrape_posts(
                max_posts=max_posts,
                since_hours=lookback_hours,
            )
        finally:
            await scraper.stop()
        return posts
    except Exception as e:
        print(f"  Post scraping error: {e}")
        return []


def _dedupe_posts(posts: list, seen_ids: set) -> tuple:
    """Filter posts to only those not yet seen. Returns (new_posts, updated_seen_ids)."""
    new_posts = []
    for post in posts:
        post_id = str(post.get("id", post.get("slug", "")))
        if post_id and post_id not in seen_ids:
            new_posts.append(post)
            seen_ids.add(post_id)
    return new_posts, seen_ids


def vectorize_posts(posts: list, config: dict, dry_run: bool = False) -> int:
    """
    Vectorize posts to Supabase. Returns count of vectorized posts.
    Wraps vectorize_posts_to_supabase.py.
    """
    if not config.get("vectorization", {}).get("enabled", False):
        return 0
    if not posts:
        return 0
    if dry_run:
        print(f"  [DRY RUN] Would vectorize {len(posts)} posts")
        return 0

    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")

        from vectorize_posts_to_supabase import vectorize_posts_batch
        table = config["vectorization"].get("supabase_table", "skool_posts")
        count = vectorize_posts_batch(posts, table_name=table)
        return count
    except (ImportError, Exception) as e:
        print(f"  Vectorization error: {e}")
        return 0


async def run_post_pipeline(config: dict, state_dir: Path, dry_run: bool = False) -> tuple:
    """
    Main entry point for post monitoring.

    Returns:
        (monetary_wins, antigravity_mentions)
    """
    if not config.get("posts", {}).get("enabled", True):
        print("[Post Pipeline] Disabled in config")
        return [], []

    community = config["community_slug"]
    lookback_hours = config["posts"].get("lookback_hours", 8)

    print(f"\n[Post Pipeline] Scraping {community} (lookback={lookback_hours}h)")
    posts = await scrape_new_posts(community, lookback_hours=lookback_hours)
    print(f"  Scraped {len(posts)} posts")

    if not posts:
        return [], []

    # Load seen post IDs to deduplicate
    watermark = load_post_watermark(state_dir)
    seen_ids = set()  # Could load from a seen_posts file if needed
    new_posts, _ = _dedupe_posts(posts, seen_ids)
    print(f"  New posts: {len(new_posts)}")

    # Detect signals
    wins, mentions = detect_post_signals(new_posts, config)
    print(f"  Monetary wins: {len(wins)}")
    print(f"  Anti-gravity mentions: {len(mentions)}")

    if wins:
        for w in wins[:3]:
            print(f"    WIN: {w.get('authorName', '?')} — {w.get('title', '')[:60]}")
    if mentions:
        for m in mentions[:3]:
            print(f"    MENTION: {m.get('authorName', '?')} — {m.get('title', '')[:60]}")

    # Vectorize new posts
    if new_posts:
        vec_count = vectorize_posts(new_posts, config, dry_run=dry_run)
        if vec_count:
            print(f"  Vectorized {vec_count} posts")

    # Update watermark
    if new_posts and not dry_run:
        latest_id = str(new_posts[0].get("id", new_posts[0].get("slug", "")))
        if latest_id:
            state_dir.mkdir(parents=True, exist_ok=True)
            save_post_watermark(state_dir, latest_id)

    return wins, mentions


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Skool Post Pipeline v2")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    tenant_dir = EXECUTION_DIR / "tenants" / args.tenant
    with open(tenant_dir / "config.json", "r") as f:
        config = json.load(f)

    state_dir = BASE_DIR / ".tmp" / "intelligence_v2" / args.tenant

    wins, mentions = await run_post_pipeline(config, state_dir, dry_run=args.dry_run)
    print(f"\nDone. Wins: {len(wins)}, Mentions: {len(mentions)}")


if __name__ == "__main__":
    asyncio.run(main())
