#!/usr/bin/env python3
"""
Skool Post Scraper v2 — Playwright-based post + comment scraper.

Replaces the Chrome extension (SkoolPostCollector) for automated/headless use.
The Chrome extension remains as a manual backup at Resources/tools/SkoolPostCollector/.

Features:
  - Scrape posts from any Skool community (all categories or filtered)
  - Fetch comments for each post (paginated via API)
  - Extract category labels, author profiles, timestamps, levels
  - Cross-reference authors against Supabase leads database
  - Checkpoint/resume for large scrapes
  - Export JSON + CSV
  - Runs headless (no Chrome window needed)

Usage:
    python execution/skool_post_scraper.py --community makerschool --limit 50
    python execution/skool_post_scraper.py --community makerschool --category introductions
    python execution/skool_post_scraper.py --community makerschool --with-comments
    python execution/skool_post_scraper.py --community makerschool --since 24h
    python execution/skool_post_scraper.py --community makerschool --all-pages
    python execution/skool_post_scraper.py --resume

Requires:
    pip install playwright requests python-dotenv
    playwright install chromium

Architecture:
    Uses __NEXT_DATA__ extraction from HTML (same as skool_scraper.py) for posts.
    Uses Playwright fetch() via browser context (same as skool_comment_scraper.py) for comments.
    No WAF token needed for page reads; WAF auto-refreshed for API calls.
"""

import sys
import os
import json
import csv
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
OUTPUT_DIR = BASE_DIR / "data" / "output"

TMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rate limits — keep it calm to avoid detection
PAGE_DELAY = 60        # seconds between page loads
COMMENT_DELAY = 30     # seconds between comment fetches per post
COMMENT_PAGE_DELAY = 10  # seconds between comment pagination requests


class SkoolPostScraper:
    """
    Playwright-based Skool post + comment scraper.

    Combines the post-reading approach of skool_scraper.py (__NEXT_DATA__)
    with the comment-fetching approach of skool_comment_scraper.py (Playwright fetch).
    """

    def __init__(self, community_slug: str, headless: bool = True):
        self.community_slug = community_slug
        self.headless = headless
        self.base_url = "https://www.skool.com"
        self.api_url = "https://api2.skool.com"

        self.auth_token = os.getenv('SKOOL_AUTH_TOKEN')
        self.client_id = os.getenv('SKOOL_CLIENT_ID', '')

        if not self.auth_token:
            raise ValueError(
                "SKOOL_AUTH_TOKEN not set in .env\n"
                "Get it from browser: DevTools → Network tab → any request → Cookie header → auth_token=..."
            )

        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.group_id = None
        self.labels = {}  # label_id → display name mapping
        self._waf_uses = 0
        self._max_waf_uses = 50

    async def start(self):
        """Launch browser and authenticate."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Set auth cookies
        cookies = [
            {'name': 'auth_token', 'value': self.auth_token, 'domain': '.skool.com', 'path': '/'},
        ]
        if self.client_id:
            cookies.append({'name': 'client_id', 'value': self.client_id, 'domain': '.skool.com', 'path': '/'})
        await self.context.add_cookies(cookies)

        self.page = await self.context.new_page()

        # Load community to establish session + extract metadata
        print(f"  Loading {self.base_url}/{self.community_slug}...")
        self.page.set_default_timeout(60000)
        await self.page.goto(f"{self.base_url}/{self.community_slug}", wait_until="domcontentloaded")
        # Wait for __NEXT_DATA__ to be available
        await self.page.wait_for_selector('#__NEXT_DATA__', state='attached', timeout=15000)

        # Extract group_id and label mapping from __NEXT_DATA__
        next_data = await self._extract_next_data()
        if next_data:
            page_props = next_data.get('props', {}).get('pageProps', {})
            current_group = page_props.get('currentGroup', {})
            self.group_id = current_group.get('id')

            # Build label (category) mapping
            for label in current_group.get('labels', []):
                label_id = label.get('id', '')
                display = label.get('metadata', {}).get('displayName', '')
                if label_id and display:
                    self.labels[label_id] = display

        print(f"  Group ID: {self.group_id}")
        print(f"  Categories: {list(self.labels.values())}")

    async def stop(self):
        """Clean up browser."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _extract_next_data(self) -> dict:
        """Extract __NEXT_DATA__ from current page."""
        try:
            return await self.page.evaluate("""
                () => {
                    const el = document.getElementById('__NEXT_DATA__');
                    return el ? JSON.parse(el.textContent) : null;
                }
            """)
        except Exception:
            return None

    async def _get_waf_token(self) -> str:
        """Get fresh WAF token, refreshing if needed."""
        self._waf_uses += 1
        if self._waf_uses > self._max_waf_uses:
            await self.page.reload(wait_until="domcontentloaded")
            self._waf_uses = 0

        cookies = await self.context.cookies()
        for c in cookies:
            if c['name'] == 'aws-waf-token':
                return c['value']
        return ''

    # ========================================================================
    # POST SCRAPING (via __NEXT_DATA__)
    # ========================================================================

    async def scrape_posts(self, max_posts: int = 100, category_filter: str = None,
                           since_hours: int = None, start_page: int = 1) -> list[dict]:
        """
        Scrape posts from the community feed.

        Args:
            max_posts: Max posts to collect
            category_filter: Filter by category name (e.g., "introductions", "wins")
            since_hours: Only posts from the last N hours
            start_page: Page to start from (for resume)

        Returns:
            List of post dicts
        """
        posts = []
        seen_ids = set()
        page_num = start_page
        since_cutoff = None

        if since_hours:
            since_cutoff = datetime.utcnow() - timedelta(hours=since_hours)

        # Find category label_id if filtering
        category_id = None
        if category_filter:
            cat_lower = category_filter.lower()
            for lid, name in self.labels.items():
                if cat_lower in name.lower():
                    category_id = lid
                    print(f"  Filtering by category: {name} (id: {lid})")
                    break
            if not category_id:
                print(f"  Warning: Category '{category_filter}' not found in {list(self.labels.values())}")

        while len(posts) < max_posts:
            # Build URL
            url = f"{self.base_url}/{self.community_slug}"
            params = []
            if page_num > 1:
                params.append(f"p={page_num}")
            if category_id:
                params.append(f"c={category_id}")
            if params:
                url += "?" + "&".join(params)

            print(f"  Page {page_num}: {url} ({len(posts)} posts so far)")

            try:
                await self.page.goto(url, wait_until="domcontentloaded")
                await self.page.wait_for_selector('#__NEXT_DATA__', state='attached', timeout=15000)
            except Exception as e:
                print(f"  Error loading page {page_num}: {e}")
                break

            next_data = await self._extract_next_data()
            if not next_data:
                print(f"  Could not extract __NEXT_DATA__ on page {page_num}")
                break

            page_props = next_data.get('props', {}).get('pageProps', {})
            post_trees = page_props.get('postTrees', [])

            if not post_trees:
                print(f"  No more posts on page {page_num}")
                break

            new_this_page = 0
            for tree in post_trees:
                if len(posts) >= max_posts:
                    break

                post = tree.get('post', {})
                post_id = post.get('id')

                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)

                metadata = post.get('metadata', {})
                user = post.get('user', {})
                created_at = post.get('createdAt', '')

                # Time filter
                if since_cutoff and created_at:
                    try:
                        post_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        if post_time.replace(tzinfo=None) < since_cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

                # Category name
                label_id = post.get('labelId', '')
                category_name = self.labels.get(label_id, '')

                slug = post.get('name', '')

                posts.append({
                    'id': post_id,
                    'title': metadata.get('title', ''),
                    'slug': slug,
                    'content': metadata.get('content', ''),
                    'authorName': user.get('name', ''),
                    'authorId': user.get('id', ''),
                    'authorProfileUrl': f"/@{user.get('name', '').replace(' ', '-').lower()}" if user.get('name') else '',
                    'createdAt': created_at,
                    'likes': metadata.get('upvotes', 0),
                    'commentCount': metadata.get('comments', 0),
                    'pinned': metadata.get('pinned', False),
                    'category': category_name,
                    'categoryId': label_id,
                    'postUrl': f"{self.base_url}/{self.community_slug}/{slug}",
                    'comments': [],  # Populated later if --with-comments
                })
                new_this_page += 1

            if new_this_page == 0:
                print(f"  No new posts on page {page_num} — stopping")
                break

            page_num += 1
            print(f"  Waiting {PAGE_DELAY}s before next page...")
            time.sleep(PAGE_DELAY)

        return posts

    # ========================================================================
    # COMMENT FETCHING (via Playwright fetch)
    # ========================================================================

    async def fetch_comments_for_post(self, post_id: str) -> list[dict]:
        """Fetch all comments for a single post using the Skool API."""
        if not self.group_id:
            return []

        all_comments = []
        cursor = None

        while True:
            url = f"{self.api_url}/posts/{post_id}/comments?group-id={self.group_id}&limit=20"
            if cursor:
                url += f"&last={cursor}"

            try:
                result = await self.page.evaluate(f"""
                    async () => {{
                        const response = await fetch("{url}", {{
                            method: "GET",
                            headers: {{ "accept": "application/json" }},
                            credentials: "include"
                        }});
                        if (!response.ok) return {{ error: response.status }};
                        return await response.json();
                    }}
                """)

                if isinstance(result, dict) and 'error' in result:
                    if result['error'] == 403:
                        # WAF expired, refresh
                        await self.page.reload(wait_until="domcontentloaded")
                        continue
                    break

                post_tree = result.get('post_tree', {})
                children = post_tree.get('children', [])

                if not children:
                    break

                for child in children:
                    comment = self._parse_comment(child, post_id)
                    if comment:
                        all_comments.append(comment)
                    # Nested replies
                    for reply in child.get('children', []):
                        reply_comment = self._parse_comment(reply, post_id, parent_id=comment['id'] if comment else None)
                        if reply_comment:
                            all_comments.append(reply_comment)

                next_cursor = result.get('last')
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                time.sleep(COMMENT_PAGE_DELAY)

            except Exception as e:
                print(f"    Comment error for {post_id}: {e}")
                break

        return all_comments

    def _parse_comment(self, raw: dict, post_id: str, parent_id: str = None) -> dict:
        """Parse a single comment from API response."""
        post_data = raw.get('post', raw)
        meta = post_data.get('metadata', {})
        user = post_data.get('user', {})

        return {
            'id': post_data.get('id', ''),
            'postId': post_id,
            'parentId': parent_id,
            'content': meta.get('content', ''),
            'authorName': user.get('name', ''),
            'authorId': user.get('id', ''),
            'createdAt': post_data.get('createdAt', ''),
            'likes': meta.get('upvotes', 0),
        }

    async def fetch_all_comments(self, posts: list[dict], checkpoint_file: Path = None) -> list[dict]:
        """
        Fetch comments for all posts that have comments.

        Args:
            posts: List of post dicts (must have 'id' and 'commentCount')
            checkpoint_file: Optional path to save progress

        Returns:
            posts list with 'comments' field populated
        """
        posts_with_comments = [p for p in posts if p.get('commentCount', 0) > 0]
        print(f"\n  Fetching comments for {len(posts_with_comments)} posts...")

        # Load checkpoint if exists
        done_ids = set()
        if checkpoint_file and checkpoint_file.exists():
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                cp = json.load(f)
            done_ids = set(cp.get('done_ids', []))
            print(f"  Resuming: {len(done_ids)} posts already done")

        for i, post in enumerate(posts_with_comments):
            post_id = post['id']
            if post_id in done_ids:
                continue

            expected = post.get('commentCount', 0)
            print(f"  [{i+1}/{len(posts_with_comments)}] {post.get('title', '')[:50]}... ({expected} comments)")

            comments = await self.fetch_comments_for_post(post_id)
            post['comments'] = comments
            done_ids.add(post_id)

            print(f"    Got {len(comments)} comments")

            # Checkpoint every 10 posts
            if checkpoint_file and (i + 1) % 10 == 0:
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump({'done_ids': list(done_ids)}, f)

            time.sleep(COMMENT_DELAY)  # Calm delay between posts

        # Clean up checkpoint
        if checkpoint_file and checkpoint_file.exists():
            checkpoint_file.unlink()

        return posts


# ============================================================================
# SUPABASE CROSS-REFERENCE
# ============================================================================

def cross_reference_authors(posts: list[dict]) -> list[dict]:
    """
    Cross-reference post authors against Supabase leads database.
    Adds 'icp_tier', 'icp_score', 'in_database' fields to each post.
    """
    print("\n  Cross-referencing authors against Supabase leads...")

    try:
        from supabase import create_client
        supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

        # Build lookup of all lead names
        lead_lookup = {}  # lowercase name → lead data
        for table in ['leads', 'leads_batch2', 'leads_batch3']:
            offset = 0
            while True:
                try:
                    result = supabase.table(table).select('name, skool, services, industries, semantic_summary').range(offset, offset + 999).execute()
                    if not result.data:
                        break
                    for row in result.data:
                        name = (row.get('name') or '').strip().lower()
                        if name:
                            lead_lookup[name] = row
                    offset += 1000
                    if len(result.data) < 1000:
                        break
                except Exception:
                    break

        print(f"  Loaded {len(lead_lookup)} leads from Supabase")

        # Cross-reference
        matched = 0
        for post in posts:
            author = (post.get('authorName') or '').strip().lower()
            if author in lead_lookup:
                lead = lead_lookup[author]
                post['in_database'] = True
                post['lead_services'] = lead.get('services', '')
                post['lead_industries'] = lead.get('industries', '')
                post['lead_summary'] = (lead.get('semantic_summary') or '')[:200]
                matched += 1
            else:
                post['in_database'] = False

        print(f"  Matched {matched}/{len(posts)} posts to known leads")

    except Exception as e:
        print(f"  Supabase cross-reference failed: {e}")
        for post in posts:
            post['in_database'] = False

    return posts


# ============================================================================
# EXPORT
# ============================================================================

def export_json(posts: list[dict], output_path: Path):
    """Export posts to JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'total_posts': len(posts),
            'posts': posts,
        }, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {output_path} ({len(posts)} posts)")


def export_csv(posts: list[dict], output_path: Path):
    """Export posts to CSV (without comments)."""
    fieldnames = [
        'authorName', 'title', 'content', 'createdAt', 'likes',
        'commentCount', 'category', 'postUrl', 'in_database',
        'lead_services', 'lead_industries',
    ]
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(posts)
    print(f"  CSV: {output_path} ({len(posts)} posts)")


# ============================================================================
# MAIN
# ============================================================================

async def run_scraper(args):
    """Main async entry point."""
    community = args.community
    out_dir = Path(args.output_dir) if args.output_dir else TMP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # State file for resume
    state_file = TMP_DIR / f"scraper_state_{community}.json"

    print("=" * 60)
    print("SKOOL POST SCRAPER v2 (Playwright)")
    print("=" * 60)
    print(f"  Community: {community}")
    print(f"  Limit: {'all pages' if args.limit >= 999999 else args.limit}")
    print(f"  Category: {args.category or 'all'}")
    print(f"  Comments: {args.with_comments}")
    print(f"  Since: {args.since or 'all time'}")
    print(f"  Resume: {args.resume}")
    print()

    # Load previous state if resuming
    existing_posts = []
    start_page = args.start_page
    if args.resume and state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        existing_posts = state.get('posts', [])
        start_page = state.get('next_page', 1)
        print(f"  Resuming: {len(existing_posts)} posts loaded, starting page {start_page}")

    scraper = SkoolPostScraper(community, headless=not args.visible)

    try:
        await scraper.start()

        # Parse --since into hours
        since_hours = None
        if args.since:
            if args.since.endswith('h'):
                since_hours = int(args.since[:-1])
            elif args.since.endswith('d'):
                since_hours = int(args.since[:-1]) * 24
            else:
                since_hours = int(args.since)

        # Scrape posts
        posts = await scraper.scrape_posts(
            max_posts=args.limit,
            category_filter=args.category,
            since_hours=since_hours,
            start_page=start_page,
        )

        # Merge with existing posts (dedup by id)
        if existing_posts:
            seen_ids = {p['id'] for p in posts}
            for ep in existing_posts:
                if ep['id'] not in seen_ids:
                    posts.append(ep)
                    seen_ids.add(ep['id'])
            print(f"\n  Total after merge: {len(posts)} posts ({len(posts) - len(existing_posts)} new)")
        else:
            print(f"\n  Scraped {len(posts)} posts")

        # Save state for potential resume
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({
                'posts': posts,
                'next_page': start_page + (len(posts) // 20) + 1,
                'saved_at': datetime.now().isoformat(),
            }, f, ensure_ascii=False)

        # Fetch comments if requested
        if args.with_comments and posts:
            checkpoint = TMP_DIR / f"comment_checkpoint_{community}.json"
            posts = await scraper.fetch_all_comments(posts, checkpoint_file=checkpoint)

        # Cross-reference with Supabase
        if not args.no_xref:
            posts = cross_reference_authors(posts)

        # Export
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        cat_suffix = f"_{args.category}" if args.category else ""

        json_path = out_dir / f"skool_posts_{community}{cat_suffix}_{timestamp}.json"
        csv_path = out_dir / f"skool_posts_{community}{cat_suffix}_{timestamp}.csv"

        export_json(posts, json_path)
        export_csv(posts, csv_path)

        # Also save a "latest" symlink-style copy for downstream tools
        latest_json = out_dir / f"skool_posts_{community}_latest.json"
        export_json(posts, latest_json)

        # Clean up state file on success
        if state_file.exists():
            state_file.unlink()

        # Summary
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        categories = {}
        for p in posts:
            cat = p.get('category', 'Uncategorized') or 'Uncategorized'
            categories[cat] = categories.get(cat, 0) + 1

        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count} posts")

        in_db = sum(1 for p in posts if p.get('in_database'))
        total_comments = sum(p.get('commentCount', 0) for p in posts)
        print(f"\n  Total posts: {len(posts)}")
        print(f"  Total comments: {total_comments}")
        if not args.no_xref:
            print(f"  Authors in lead database: {in_db}")
        print(f"\n  Output: {json_path}")

        return posts

    finally:
        await scraper.stop()


def main():
    parser = argparse.ArgumentParser(description="Skool Post Scraper v2 (Playwright)")
    parser.add_argument("--community", type=str, default="makerschool", help="Community slug")
    parser.add_argument("--limit", type=int, default=100, help="Max posts to scrape (default: 100)")
    parser.add_argument("--all-pages", action="store_true", help="Scrape ALL pages (overrides --limit)")
    parser.add_argument("--category", type=str, help="Filter by category name (e.g., introductions, wins)")
    parser.add_argument("--with-comments", action="store_true", help="Also fetch comments for each post")
    parser.add_argument("--since", type=str, help="Only posts from last N hours/days (e.g., 24h, 7d)")
    parser.add_argument("--start-page", type=int, default=1, help="Start from page N")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--no-xref", action="store_true", help="Skip Supabase cross-reference")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("--output-dir", type=str, help="Custom output directory (default: .tmp/)")
    args = parser.parse_args()

    # --all-pages overrides --limit
    if args.all_pages:
        args.limit = 999999

    import asyncio
    asyncio.run(run_scraper(args))


if __name__ == "__main__":
    main()
