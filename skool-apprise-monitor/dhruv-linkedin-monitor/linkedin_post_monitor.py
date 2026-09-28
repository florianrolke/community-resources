#!/usr/bin/env python3
"""
LinkedIn Post Monitor for Dhruv
================================
Monitors aiautomationsbyjack Skool community for LinkedIn-related posts
and sends desktop push notifications via ntfy.

Standalone daemon — does NOT modify or depend on the main skool_apprise_monitor.

Usage:
    python linkedin_post_monitor.py --daemon --interval 180
    python linkedin_post_monitor.py --dry-run
    python linkedin_post_monitor.py --init
    python linkedin_post_monitor.py --test-notification

Requires:
    SKOOL_AUTH_TOKEN   — Skool session cookie (shared with main monitor)
    DHRUV_NTFY_URL     — e.g. https://push.florianrolke.com/dhruv-linkedin-alerts
"""

import sys
import os
import re
import json
import asyncio
import argparse
import requests
import time
from datetime import datetime, timezone
from pathlib import Path

# Load .env for local testing (Docker injects env vars directly)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

COMMUNITY = os.getenv("DHRUV_COMMUNITY", "aiautomationsbyjack")
SKOOL_AUTH_TOKEN = os.getenv("SKOOL_AUTH_TOKEN", "")
DHRUV_NTFY_URL = os.getenv("DHRUV_NTFY_URL", "https://push.florianrolke.com/dhruv-linkedin-alerts")

# State directory: /app/state in Docker, local fallback
STATE_DIR = os.getenv("STATE_DIR", str(Path(__file__).parent / "state"))

# LinkedIn keywords — match if ANY of these appear in post title or content
LINKEDIN_KEYWORDS = [
    "linkedin", "linked in", "linkedin profile", "linkedin strategy",
    "linkedin content", "linkedin growth", "linkedin post",
    "linkedin engagement", "linkedin outreach", "linkedin leads",
    "linkedin connections", "linkedin algorithm", "linkedin marketing",
    "linkedin brand", "linkedin networking", "linkedin funnel",
    "linkedin dms", "linkedin automation", "personal branding",
    "linkedin creator", "linkedin followers", "linkedin impressions",
    "linkedin carousel", "linkedin newsletter", "linkedin articles",
    "linkedin reach", "linkedin views", "linkedin banner",
    "linkedin headline", "linkedin bio", "linkedin summary",
    "linkedin hook", "linkedin tips",
]

# Exclude posts that are just sharing a LinkedIn URL without discussing LinkedIn
# (e.g. "check out my website" with a LinkedIn link in bio)
MIN_KEYWORD_CONTEXT = 3  # keyword must have at least 3 chars of surrounding context


# ---------------------------------------------------------------------------
# STATE MANAGEMENT
# ---------------------------------------------------------------------------

def _state_path():
    return os.path.join(STATE_DIR, f"linkedin_posts_{COMMUNITY}.json")


def load_state() -> dict:
    path = _state_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}


def save_state(state: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    path = _state_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# LINKEDIN KEYWORD DETECTION
# ---------------------------------------------------------------------------

def detect_linkedin_posts(posts: list) -> list:
    """Find posts that discuss LinkedIn topics."""
    matches = []
    for post in posts:
        title = post.get("title", "") or ""
        content = post.get("content", "") or ""
        text = f"{title} {content}".lower()

        matched_keywords = []
        for kw in LINKEDIN_KEYWORDS:
            if kw in text:
                matched_keywords.append(kw)

        if not matched_keywords:
            continue

        # Extract context around first keyword match
        first_kw = matched_keywords[0]
        pos = text.find(first_kw)
        start = max(0, pos - 80)
        end = min(len(text), pos + len(first_kw) + 120)
        context = text[start:end].strip()

        # Get author name
        author = (
            post.get("authorName")
            or (post.get("author", {}) or {}).get("name", "")
            or "Unknown"
        )

        matches.append({
            "post_id": post.get("id") or post.get("postId"),
            "author_name": author,
            "author_handle": (post.get("author", {}) or {}).get("username", ""),
            "post_title": title[:200],
            "post_url": post.get("url") or post.get("postUrl", ""),
            "keywords": matched_keywords,
            "context": context,
            "category": post.get("categoryName", ""),
            "likes": post.get("likesCount", 0),
            "comments": post.get("commentsCount", 0),
        })

    return matches


# ---------------------------------------------------------------------------
# NTFY NOTIFICATION (direct HTTP POST — no Apprise needed)
# ---------------------------------------------------------------------------

def send_ntfy(title: str, body: str, priority: str = "default",
              tags: str = "linkedin", dry_run: bool = False) -> bool:
    """Send push notification directly to ntfy topic."""
    if dry_run:
        print(f"\n  [DRY RUN] ntfy notification:")
        print(f"    Title: {title}")
        print(f"    Body: {body[:300]}")
        print(f"    URL: {DHRUV_NTFY_URL}")
        return True

    if not DHRUV_NTFY_URL:
        print("  WARNING: DHRUV_NTFY_URL not set — skipping notification")
        return False

    try:
        resp = requests.post(
            DHRUV_NTFY_URL,
            data=body.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": tags,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"  ntfy sent: {title}")
            return True
        else:
            print(f"  ntfy failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ntfy error: {e}")
        return False


def format_and_send(matches: list, dry_run: bool = False) -> int:
    """Format and send notifications for LinkedIn post matches."""
    sent = 0
    for m in matches:
        title = f"LinkedIn Post: {m['author_name']}"
        lines = []
        if m.get("post_title"):
            lines.append(f'"{m["post_title"][:100]}"')
        if m.get("context"):
            lines.append(f"...{m['context'][:200]}...")
        lines.append(f"Keywords: {', '.join(m['keywords'][:5])}")
        if m.get("post_url"):
            lines.append(f"\n{m['post_url']}")
        if m.get("likes") or m.get("comments"):
            lines.append(f"{m['likes']} likes | {m['comments']} comments")

        body = "\n".join(lines)
        if send_ntfy(title, body, priority="default", dry_run=dry_run):
            sent += 1
    return sent


# ---------------------------------------------------------------------------
# POST SCRAPING (Playwright, reuses SKOOL_AUTH_TOKEN)
# ---------------------------------------------------------------------------

async def scrape_posts(max_pages: int = 2) -> list:
    """Scrape recent posts from community feed using Playwright."""
    from playwright.async_api import async_playwright

    posts = []
    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Inject auth cookie
        if SKOOL_AUTH_TOKEN:
            await context.add_cookies([{
                "name": "auth_token",
                "value": SKOOL_AUTH_TOKEN,
                "domain": ".skool.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }])

        page = await context.new_page()

        seen_ids = set()

        for page_num in range(1, max_pages + 1):
            url = f"https://www.skool.com/{COMMUNITY}?p={page_num}"
            print(f"  Scraping page {page_num}: {url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector("#__NEXT_DATA__", state="attached", timeout=15000)
                await asyncio.sleep(2)  # let hydration settle

                next_data = await page.evaluate("""
                    () => {
                        const el = document.getElementById('__NEXT_DATA__');
                        return el ? JSON.parse(el.textContent) : null;
                    }
                """)

                if not next_data:
                    print(f"    No __NEXT_DATA__ found")
                    continue

                page_props = next_data.get("props", {}).get("pageProps", {}) or {}
                page_posts_found = 0

                # Current Skool format: postTrees[].post.metadata.{title,content}
                post_trees = page_props.get("postTrees", []) or []
                if post_trees:
                    for tree in post_trees:
                        raw = tree.get("post", {}) or {}
                        post_id = str(raw.get("id", ""))
                        if not post_id or post_id in seen_ids:
                            continue
                        seen_ids.add(post_id)

                        meta = raw.get("metadata", {}) or {}
                        user = raw.get("user", {}) or {}
                        slug = raw.get("name", "")
                        first_name = user.get("firstName", "")
                        last_name = user.get("lastName", "")
                        author_name = f"{first_name} {last_name}".strip() or user.get("name", "")

                        post_url = (
                            f"https://www.skool.com/{COMMUNITY}/{slug}"
                            if slug else f"https://www.skool.com/{COMMUNITY}/{post_id}"
                        )

                        posts.append({
                            "id": post_id,
                            "title": meta.get("title", "") or "",
                            "content": meta.get("content", "") or "",
                            "authorName": author_name,
                            "author": {"name": author_name, "username": user.get("name", "")},
                            "url": post_url,
                            "likesCount": meta.get("upvotes", 0) or 0,
                            "commentsCount": meta.get("comments", 0) or 0,
                            "createdAt": raw.get("createdAt", ""),
                            "categoryName": "",
                        })
                        page_posts_found += 1

                else:
                    # Legacy format fallback: pageProps.posts[]
                    post_list = page_props.get("posts", []) or []
                    for post in post_list:
                        post_id = str(post.get("id") or post.get("postId") or "")
                        if not post_id or post_id in seen_ids:
                            continue
                        seen_ids.add(post_id)

                        author = post.get("author", {}) or {}
                        slug = post.get("slug", "")
                        post_url = (
                            post.get("url") or post.get("postUrl", "")
                            or (f"https://www.skool.com/{COMMUNITY}/{slug}" if slug else "")
                        )

                        posts.append({
                            "id": post_id,
                            "title": post.get("title", ""),
                            "content": post.get("content", "") or post.get("body", ""),
                            "authorName": post.get("authorName") or author.get("name", ""),
                            "author": author,
                            "url": post_url,
                            "likesCount": post.get("likesCount", 0),
                            "commentsCount": post.get("commentsCount", 0),
                            "createdAt": post.get("createdAt", ""),
                            "categoryName": post.get("categoryName", ""),
                        })
                        page_posts_found += 1

                print(f"    Found {page_posts_found} posts on page {page_num}")

            except Exception as e:
                print(f"    Error on page {page_num}: {e}")

            # Rate limit between pages
            if page_num < max_pages:
                await asyncio.sleep(5)

        await browser.close()
    finally:
        await p.stop()

    return posts


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

async def run_cycle(dry_run: bool = False, init: bool = False) -> dict:
    """Run one monitoring cycle."""
    results = {"posts_scraped": 0, "matches": 0, "notifications": 0}

    print(f"\n{'='*60}")
    print(f"LinkedIn Monitor — {datetime.now(timezone.utc).isoformat()}")
    print(f"Community: {COMMUNITY}")
    print(f"ntfy: {DHRUV_NTFY_URL}")
    print(f"{'='*60}")

    # Load state
    state = load_state()
    seen_ids = set(state.get("seen_ids", []))

    # Scrape posts
    try:
        posts = await scrape_posts(max_pages=2)
        results["posts_scraped"] = len(posts)
        print(f"  Scraped {len(posts)} posts")
    except Exception as e:
        print(f"  ERROR scraping posts: {e}")
        import traceback
        traceback.print_exc()
        return results

    # Filter to new posts
    new_posts = [p for p in posts if str(p.get("id", "")) not in seen_ids]
    print(f"  New posts: {len(new_posts)}")

    if init and not seen_ids:
        # First run — seed state, don't notify
        all_ids = [str(p["id"]) for p in posts if p.get("id")]
        state["seen_ids"] = all_ids
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        print(f"  Initialized with {len(all_ids)} post IDs (no notifications)")
        return results

    if new_posts:
        # Detect LinkedIn mentions
        matches = detect_linkedin_posts(new_posts)
        results["matches"] = len(matches)

        if matches:
            print(f"  LinkedIn matches: {len(matches)}")
            for m in matches:
                print(f"    - {m['author_name']}: {m['keywords'][:3]}")
            sent = format_and_send(matches, dry_run=dry_run)
            results["notifications"] = sent

        # Update seen IDs (all posts, not just matches)
        all_ids = [str(p["id"]) for p in posts if p.get("id")]
        state["seen_ids"] = list(set(state.get("seen_ids", []) + all_ids))

        # Keep state manageable (last 5000 IDs)
        if len(state["seen_ids"]) > 5000:
            state["seen_ids"] = state["seen_ids"][-5000:]

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    print(f"\n  Results: {results['posts_scraped']} posts, {results['matches']} matches, {results['notifications']} sent")
    return results


async def daemon_loop(interval: int, dry_run: bool):
    """Run monitoring in a continuous loop."""
    print(f"Starting LinkedIn monitor daemon (interval: {interval}s)")
    print(f"Community: {COMMUNITY}")
    print(f"ntfy: {DHRUV_NTFY_URL}")
    print(f"Keywords: {len(LINKEDIN_KEYWORDS)}")

    cycle = 0
    while True:
        cycle += 1
        try:
            print(f"\n--- Cycle {cycle} ---")
            await run_cycle(dry_run=dry_run)
        except Exception as e:
            print(f"  CYCLE ERROR: {e}")
            import traceback
            traceback.print_exc()

        print(f"  Sleeping {interval}s...")
        await asyncio.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Post Monitor for Dhruv")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--interval", type=int, default=180, help="Seconds between cycles")
    parser.add_argument("--dry-run", action="store_true", help="Don't send notifications")
    parser.add_argument("--init", action="store_true", help="Initialize state (no alerts)")
    parser.add_argument("--test-notification", action="store_true", help="Send test ntfy push")
    args = parser.parse_args()

    if not SKOOL_AUTH_TOKEN:
        print("ERROR: SKOOL_AUTH_TOKEN not set")
        sys.exit(1)

    if args.test_notification:
        print("Sending test notification...")
        send_ntfy(
            title="LinkedIn Monitor Test",
            body="If you see this, Dhruv's LinkedIn post alerts are working!",
            priority="high",
            tags="white_check_mark,linkedin",
        )
        return

    if args.daemon:
        asyncio.run(daemon_loop(args.interval, dry_run=args.dry_run))
    elif args.init:
        asyncio.run(run_cycle(dry_run=True, init=True))
    else:
        asyncio.run(run_cycle(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
