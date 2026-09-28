#!/usr/bin/env python3
"""
Skool Apprise Monitor — Unified community monitor with push notifications.

Monitors Skool communities for:
  1. New ICP members (Tier A/B via keyword scoring)
  2. Financial wins (regex pattern matching on posts)
  3. @mentions of Florian

Sends notifications via Apprise API (self-hosted on Coolify).
Supports single-run (cron) and daemon mode (persistent loop every N seconds).

Usage:
    # Initialize state (first run, no notifications):
    python execution/skool_apprise_monitor.py --init

    # Normal single run:
    python execution/skool_apprise_monitor.py

    # Daemon mode — persistent loop every 3 minutes:
    python execution/skool_apprise_monitor.py --daemon --interval 180 --members-only

    # Dry run:
    python execution/skool_apprise_monitor.py --dry-run

    # Members only / posts only:
    python execution/skool_apprise_monitor.py --members-only
    python execution/skool_apprise_monitor.py --posts-only

    # Show browser for debugging:
    python execution/skool_apprise_monitor.py --visible

Requires:
    pip install playwright requests python-dotenv
    playwright install chromium

Environment (.env):
    SKOOL_AUTH_TOKEN       — Skool session cookie (required)
    APPRISE_URL            — Apprise API base URL (e.g. https://notify.florianrolke.com)
    APPRISE_URLS           — Notification URLs (e.g. ntfy://push.florianrolke.com/skool-alerts)
    APPRISE_EMAIL_TO       — Email recipient for notifications
    SMTP_HOST              — SMTP server (default: smtp.gmail.com)
    SMTP_USER              — SMTP username
    SMTP_PASS              — SMTP password (Gmail app password)
"""

import sys
import os
import re
import json
import asyncio
import argparse
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
# In Docker container, use /app/state; locally use .tmp/apprise_state
STATE_DIR = Path(os.getenv("STATE_DIR", str(BASE_DIR / ".tmp" / "apprise_state")))
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

COMMUNITY = "aiautomationsbyjack"
APPRISE_URL = os.getenv("APPRISE_URL", "https://notify.florianrolke.com")

# Notification URLs for Apprise API
# Format: https://github.com/caronc/apprise/wiki
# Email example: mailto://user:you@example.com?to=recipient@email.com
# Can add more channels later: slack://, tgram://, windows://, etc.
APPRISE_NOTIFY_URLS = []

# SAFETY: Only these email addresses may receive emails via ANY path (Apprise, SMTP, etc.)
ALLOWED_EMAIL_RECIPIENTS = {"you@example.com", "you@example.com"}

def build_apprise_urls():
    """Build Apprise notification URLs from env vars."""
    urls = []

    # Email via SMTP
    email_to = os.getenv("APPRISE_EMAIL_TO", os.getenv("NOTIFY_EMAIL_TO", ""))
    smtp_user = os.getenv("SMTP_USER", os.getenv("NOTIFY_EMAIL_FROM", ""))
    smtp_pass = os.getenv("SMTP_PASS", os.getenv("NOTIFY_EMAIL_PASSWORD", ""))
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")

    if email_to and smtp_user and smtp_pass:
        # WHITELIST CHECK: Block Apprise mailto to non-whitelisted addresses
        if email_to.lower().strip() not in ALLOWED_EMAIL_RECIPIENTS:
            print(f"  [BLOCKED] Apprise mailto to {email_to} — not in allowed list {ALLOWED_EMAIL_RECIPIENTS}")
        else:
            # Apprise mailto URL format
            urls.append(f"mailto://{smtp_user}:{smtp_pass}@{smtp_host}?to={email_to}")

    # Add any custom URLs from env
    custom = os.getenv("APPRISE_URLS", "")
    if custom:
        urls.extend([u.strip() for u in custom.split(",") if u.strip()])

    return urls


# ============================================================================
# PERSISTENT BROWSER SESSION (for daemon mode)
# ============================================================================

class BrowserSession:
    """Manages a persistent Playwright browser for repeated scraping cycles."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._cycle_count = 0
        self._restart_every = 50  # restart browser every N cycles to prevent memory leaks

    async def start(self):
        """Launch browser and set up authenticated context."""
        from playwright.async_api import async_playwright

        auth_token = os.getenv("SKOOL_AUTH_TOKEN")
        client_id = os.getenv("SKOOL_CLIENT_ID", "")
        if not auth_token:
            raise ValueError("SKOOL_AUTH_TOKEN not set in .env")

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        cookies = [
            {'name': 'auth_token', 'value': auth_token, 'domain': '.skool.com', 'path': '/'},
        ]
        if client_id:
            cookies.append({'name': 'client_id', 'value': client_id, 'domain': '.skool.com', 'path': '/'})
        await self.context.add_cookies(cookies)

        self.page = await self.context.new_page()
        self.page.set_default_timeout(60000)
        self._cycle_count = 0
        print(f"  Browser session started (headless={self.headless})")

    async def stop(self):
        """Clean up all browser resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        self._playwright = None

    async def maybe_restart(self):
        """Restart browser periodically to prevent memory leaks."""
        self._cycle_count += 1
        if self._cycle_count >= self._restart_every:
            print(f"  Restarting browser (cycle {self._cycle_count})...")
            await self.stop()
            await self.start()

    @property
    def is_alive(self) -> bool:
        return self.page is not None and self.browser is not None


# Mention keywords
MENTION_KEYWORDS = ["@florian", "florian rolke"]

# Money patterns (from wins_monitor.py)
MONEY_PATTERNS = [
    r'\$[\d,]+k?',                                    # $5k, $10,000
    r'(?:closed|signed|landed).{0,20}\$',             # "closed a $15k deal"
    r'(?:revenue|deal|contract).{0,30}\$',            # "revenue hit $50k"
    r'(?:6|7|six|seven)-?figure',                     # "seven-figure deal"
    r'(?:first|biggest).{0,20}(?:client|deal|sale)',  # "first client!"
    r'(?:won|landed|secured).{0,20}(?:client|deal|contract)',
]


# ============================================================================
# ICP SCORING (from skool_new_member_monitor.py)
# ============================================================================

TIER_A_SIGNALS = {
    "position": [
        "agency owner", "founder", "ceo", "owner", "co-founder",
        "managing director", "president", "principal",
    ],
    "industry": [
        "construction", "plumbing", "hvac", "electrical", "roofing",
        "manufacturing", "contractor", "real estate", "insurance",
        "landscaping", "dental", "medical", "legal", "accounting",
    ],
    "revenue": [
        "7 figure", "7-figure", "multiple 6 figure", "million",
        "$1m", "$2m", "$5m", "$10m", "revenue",
    ],
    "pain": [
        "scaling", "leads", "struggling with", "need help",
        "looking for", "want to grow", "automate", "systems",
    ],
}

TIER_B_SIGNALS = {
    "position": [
        "consultant", "freelancer", "coach", "entrepreneur",
        "business owner", "self-employed", "cmo", "vp",
    ],
    "industry": [
        "marketing", "saas", "e-commerce", "ecommerce", "fitness",
        "health", "wellness", "education", "tech", "software",
    ],
}

AI_AGENCY_KEYWORDS = [
    "ai agency", "ai automation", "chatgpt", "claude", "llm",
    "machine learning", "prompt engineer", "ai consultant",
    "ai solutions", "ai services", "ai integration",
]


def quick_score_member(member: dict) -> dict:
    """Keyword-based ICP scoring. Returns member with icp_score, tier, match_reasons."""
    name = (member.get("name", "") or "").lower()
    bio = (member.get("bio", "") or "").lower()
    text = f"{name} {bio}"

    score = 0
    reasons = []

    for kw in AI_AGENCY_KEYWORDS:
        if kw in text:
            member["icp_score"] = 0
            member["tier"] = "D"
            member["match_reasons"] = ["AI agency — not ICP"]
            return member

    for category, keywords in TIER_A_SIGNALS.items():
        for kw in keywords:
            if kw in text:
                weight = {"position": 25, "industry": 15, "revenue": 15, "pain": 10}[category]
                score += weight
                reasons.append(f"{category.title()}: {kw}")
                break

    for category, keywords in TIER_B_SIGNALS.items():
        for kw in keywords:
            if kw in text:
                weight = {"position": 15, "industry": 10}[category]
                score += weight
                reasons.append(f"{category.title()}: {kw}")
                break

    if bio and len(bio) > 20:
        score += 5
        reasons.append("Has detailed bio")

    score = min(score, 100)
    tier = "A" if score >= 60 else "B" if score >= 35 else "C" if score >= 15 else "D"

    member["icp_score"] = score
    member["tier"] = tier
    member["match_reasons"] = reasons
    return member


# ============================================================================
# DETECTION: WINS + MENTIONS
# ============================================================================

def detect_money_pattern(text: str):
    """Detect monetary win patterns in text. Returns match string or None."""
    text_lower = text.lower()
    for pattern in MONEY_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def detect_mentions(posts: list) -> list:
    """Detect @mentions and name mentions of Florian in posts."""
    mentions = []
    for post in posts:
        content = post.get('content', '') or post.get('title', '')
        content_lower = content.lower()

        for keyword in MENTION_KEYWORDS:
            if keyword.lower() in content_lower:
                # Extract context around mention
                pos = content_lower.find(keyword.lower())
                start = max(0, pos - 80)
                end = min(len(content), pos + len(keyword) + 80)
                context = content[start:end].strip()
                if start > 0:
                    context = '...' + context
                if end < len(content):
                    context = context + '...'

                mentions.append({
                    'post_id': post.get('id') or post.get('postId'),
                    'type': '@mention' if keyword.startswith('@') else 'name_mention',
                    'keyword': keyword,
                    'author_name': post.get('authorName') or post.get('author', {}).get('name', 'Unknown'),
                    'post_title': post.get('title', ''),
                    'post_url': post.get('url') or post.get('postUrl', ''),
                    'context': context,
                    'likes_count': post.get('likesCount', 0),
                    'comments_count': post.get('commentsCount', 0),
                })
                break  # One match per post is enough
    return mentions


def detect_wins(posts: list) -> list:
    """Detect financial wins in posts."""
    wins = []
    for post in posts:
        content = post.get('content', '') or post.get('title', '')
        money_match = detect_money_pattern(content)
        if money_match:
            wins.append({
                'post_id': post.get('id') or post.get('postId'),
                'title': post.get('title', ''),
                'author_name': post.get('authorName') or post.get('author', {}).get('name', 'Unknown'),
                'money_pattern': money_match,
                'post_url': post.get('url') or post.get('postUrl', ''),
                'likes_count': post.get('likesCount', 0),
                'comments_count': post.get('commentsCount', 0),
            })
    return wins


# ============================================================================
# MEMBER SCRAPING (from skool_new_member_monitor.py)
# ============================================================================

def _parse_members_from_next_data(next_data: dict, community: str, seen_handles: set) -> list:
    """Extract member dicts from __NEXT_DATA__ JSON. Shared by all scrape paths.

    Handles two Skool data formats:
    - /-/members format: firstName, lastName, name=slug, metadata.bio
    - /members format: user.name, user.username, user.bio (nested)
    """
    members = []
    page_props = next_data.get('props', {}).get('pageProps', {}) or {}
    member_list = (
        page_props.get('members', []) or
        page_props.get('groupMembers', []) or
        page_props.get('users', []) or []
    )

    # Check dehydratedState as fallback (React Query cache)
    if not member_list:
        dehydrated = page_props.get('dehydratedState', {})
        if dehydrated:
            for q in dehydrated.get('queries', []):
                data = q.get('state', {}).get('data', {})
                if isinstance(data, dict):
                    items = data.get('items', []) or data.get('members', []) or data.get('data', [])
                    if items and isinstance(items, list) and len(items) > 0:
                        first = items[0]
                        if isinstance(first, dict) and ('name' in first or 'user' in first):
                            member_list = items
                            break
                elif isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, dict) and ('name' in first or 'user' in first):
                        member_list = data
                        break

    for m in member_list:
        # /-/members format: firstName, lastName, name=slug, metadata.bio
        if m.get('firstName') or m.get('lastName'):
            first = m.get("firstName", "")
            last = m.get("lastName", "")
            full_name = f"{first} {last}".strip() or m.get("name", "")
            handle = m.get("name", "")  # slug is the handle on /-/members
            meta = m.get("metadata", {}) or {}
            bio = meta.get("bio", "") or ""
            member_data = {
                "name": full_name,
                "handle": handle,
                "bio": bio,
                "profileUrl": f"https://www.skool.com/@{handle}",
                "joinedAt": m.get("createdAt", "") or m.get("joinedAt", ""),
            }
        # Nested user format
        elif 'user' in m and isinstance(m['user'], dict):
            user = m['user']
            member_data = {
                "name": user.get("name", ""),
                "handle": user.get("username", "") or user.get("handle", ""),
                "bio": user.get("bio", "") or m.get("bio", ""),
                "profileUrl": f"https://www.skool.com/@{user.get('username', '')}",
                "joinedAt": m.get("createdAt", "") or m.get("joinedAt", ""),
            }
        # Flat format fallback
        else:
            member_data = {
                "name": m.get("name", ""),
                "handle": m.get("username", "") or m.get("handle", "") or m.get("name", ""),
                "bio": m.get("bio", ""),
                "profileUrl": f"https://www.skool.com/@{m.get('username', m.get('handle', m.get('name', '')))}",
                "joinedAt": m.get("createdAt", "") or m.get("joinedAt", ""),
            }

        handle = member_data["handle"].lower()
        if handle and handle not in seen_handles:
            seen_handles.add(handle)
            member_data["community"] = community
            members.append(member_data)

    return members


async def scrape_members_with_page(page, community: str, max_pages: int = 1) -> list:
    """Scrape newest members using an existing Playwright page (for daemon mode)."""
    members = []
    seen_handles = set()

    for page_num in range(1, max_pages + 1):
        url = f"https://www.skool.com/{community}/-/members?sort=newest"
        if page_num > 1:
            url += f"&p={page_num}"

        print(f"  [{page_num}/{max_pages}] Loading members page...")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_selector('#__NEXT_DATA__', state='attached', timeout=15000)
        await page.wait_for_timeout(2000)

        next_data = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }
        """)

        if next_data:
            page_members = _parse_members_from_next_data(next_data, community, seen_handles)
            members.extend(page_members)
            print(f"    Found {len(page_members)} on page ({len(members)} total unique)")

        if page_num < max_pages:
            await asyncio.sleep(5)

    return members


async def scrape_member_list(community: str, max_pages: int = 2,
                              headless: bool = True) -> list:
    """Scrape newest members (standalone — creates and closes its own browser)."""
    session = BrowserSession(headless=headless)
    await session.start()
    try:
        return await scrape_members_with_page(session.page, community, max_pages)
    finally:
        await session.stop()


# ============================================================================
# POST SCRAPING (lightweight — recent posts only)
# ============================================================================

async def scrape_posts_with_page(page, community: str, max_pages: int = 2) -> list:
    """Scrape recent posts using an existing Playwright page (for daemon mode)."""
    posts = []
    seen_ids = set()

    for page_num in range(1, max_pages + 1):
        url = f"https://www.skool.com/{community}?p={page_num}"

        print(f"  [{page_num}/{max_pages}] Loading posts page...")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_selector('#__NEXT_DATA__', state='attached', timeout=15000)
        await page.wait_for_timeout(2000)

        next_data = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }
        """)

        if next_data:
            page_props = next_data.get('props', {}).get('pageProps', {}) or {}
            post_list = page_props.get('posts', []) or []

            if not post_list:
                dehydrated = page_props.get('dehydratedState', {})
                if dehydrated:
                    for q in dehydrated.get('queries', []):
                        data = q.get('state', {}).get('data', {})
                        if isinstance(data, dict):
                            items = data.get('items', []) or data.get('posts', []) or data.get('data', [])
                            if items and isinstance(items, list) and len(items) > 0:
                                first = items[0]
                                if isinstance(first, dict) and ('title' in first or 'content' in first):
                                    post_list = items
                                    break
                        elif isinstance(data, list) and len(data) > 0:
                            first = data[0]
                            if isinstance(first, dict) and ('title' in first or 'content' in first):
                                post_list = data
                                break

            for post in post_list:
                post_id = post.get('id') or post.get('postId')
                if post_id and post_id not in seen_ids:
                    seen_ids.add(post_id)
                    author = post.get('author', {}) or {}
                    author_name = post.get('authorName') or author.get('name', '')
                    posts.append({
                        'id': post_id,
                        'title': post.get('title', ''),
                        'content': post.get('content', '') or post.get('body', ''),
                        'authorName': author_name,
                        'author': author,
                        'url': post.get('url') or post.get('postUrl') or f"https://www.skool.com/{community}/{post_id}",
                        'postUrl': post.get('url') or post.get('postUrl') or f"https://www.skool.com/{community}/{post_id}",
                        'likesCount': post.get('likesCount', 0),
                        'commentsCount': post.get('commentsCount', 0),
                        'createdAt': post.get('createdAt', ''),
                        'categoryName': post.get('categoryName', ''),
                    })

            print(f"    Found {len(post_list)} posts ({len(posts)} total unique)")

        if page_num < max_pages:
            await asyncio.sleep(5)

    return posts


async def scrape_recent_posts(community: str, max_pages: int = 2,
                               headless: bool = True) -> list:
    """Scrape recent posts (standalone — creates and closes its own browser)."""
    session = BrowserSession(headless=headless)
    await session.start()
    try:
        return await scrape_posts_with_page(session.page, community, max_pages)
    finally:
        await session.stop()


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state(state_type: str, community: str) -> dict:
    """Load state file. Returns dict with 'seen_ids' set."""
    path = STATE_DIR / f"{state_type}_{community}.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}


def save_state(state_type: str, community: str, state: dict):
    """Save state file atomically."""
    path = STATE_DIR / f"{state_type}_{community}.json"
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def filter_new_ids(items: list, state: dict, id_key: str = "handle") -> list:
    """Filter items to only those not in state's seen_ids."""
    seen = set(state.get("seen_ids", []))
    new_items = []
    for item in items:
        item_id = item.get(id_key, "").lower() if id_key == "handle" else str(item.get(id_key, ""))
        if item_id and item_id not in seen:
            new_items.append(item)
    return new_items


def add_to_state(state: dict, ids: list):
    """Add IDs to state's seen list."""
    seen = set(state.get("seen_ids", []))
    seen.update(ids)
    state["seen_ids"] = list(seen)


# ============================================================================
# APPRISE NOTIFICATIONS
# ============================================================================

def send_apprise_notification(title: str, body: str, notify_type: str = "info",
                               tag: str = None, dry_run: bool = False) -> bool:
    """
    Send notification via Apprise API.

    Args:
        title: Notification title
        body: Notification body (supports markdown for some channels)
        notify_type: "info", "success", "warning", or "failure"
        tag: Optional tag to filter notification channels
        dry_run: Print instead of sending

    Returns:
        True if sent successfully
    """
    if dry_run:
        print(f"\n  [DRY RUN] Notification ({notify_type}):")
        print(f"    Title: {title}")
        print(f"    Body: {body[:200]}...")
        return True

    urls = build_apprise_urls()
    if not urls:
        print("  WARNING: No Apprise notification URLs configured. Set SMTP_USER + SMTP_PASS + APPRISE_EMAIL_TO in .env")
        return False

    payload = {
        "urls": ",".join(urls),
        "title": title,
        "body": body,
        "type": notify_type,
    }
    if tag:
        payload["tag"] = tag

    try:
        resp = requests.post(
            f"{APPRISE_URL}/notify",
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            print(f"  Notification sent: {title}")
            return True
        else:
            print(f"  Notification failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        print(f"  Notification error: {e}")
        return False


def format_member_notification(members: list) -> tuple:
    """Format new ICP members into notification title + body."""
    count = len(members)
    tier_a = [m for m in members if m.get("tier") == "A"]

    title = f"Skool: {count} new qualified member{'s' if count != 1 else ''}"
    if tier_a:
        title = f"Skool: {len(tier_a)} Tier A lead{'s' if len(tier_a) != 1 else ''}!"

    lines = []
    for m in sorted(members, key=lambda x: x.get("icp_score", 0), reverse=True):
        tier = m.get("tier", "?")
        score = m.get("icp_score", 0)
        reasons = ", ".join(m.get("match_reasons", []))
        lines.append(f"[{tier}] {m['name']} (Score: {score})")
        if reasons:
            lines.append(f"    Signals: {reasons}")
        if m.get("bio"):
            lines.append(f"    Bio: {m['bio'][:120]}")
        lines.append(f"    Profile: {m.get('profileUrl', '')}")
        lines.append("")

    body = "\n".join(lines)
    return title, body


def format_wins_notification(wins: list) -> tuple:
    """Format financial wins into notification title + body."""
    count = len(wins)
    title = f"Skool: {count} financial win{'s' if count != 1 else ''} posted"

    lines = []
    for w in wins:
        lines.append(f"{w['money_pattern'].upper()} — {w['author_name']}")
        if w.get('title'):
            lines.append(f"    \"{w['title'][:100]}\"")
        lines.append(f"    {w.get('post_url', '')}")
        lines.append(f"    {w['likes_count']} likes | {w['comments_count']} comments")
        lines.append("")

    body = "\n".join(lines)
    return title, body


def format_mentions_notification(mentions: list) -> tuple:
    """Format mentions into notification title + body."""
    count = len(mentions)
    title = f"Skool: {count} mention{'s' if count != 1 else ''} of you"

    lines = []
    for m in mentions:
        mtype = m.get('type', 'mention')
        lines.append(f"[{mtype}] {m['author_name']}")
        if m.get('context'):
            lines.append(f"    \"{m['context'][:150]}\"")
        lines.append(f"    {m.get('post_url', '')}")
        lines.append("")

    body = "\n".join(lines)
    return title, body


# ============================================================================
# MAIN MONITOR
# ============================================================================

async def run_monitor(community: str, headless: bool = True,
                       dry_run: bool = False, init: bool = False,
                       members_only: bool = False, posts_only: bool = False,
                       session: BrowserSession = None):
    """
    Run the unified Skool monitor (single cycle).

    1. Scrape newest members → detect new ICPs → notify
    2. Scrape recent posts → detect wins + mentions → notify

    If session is provided, reuses its browser page. Otherwise creates standalone browsers.
    """
    print(f"\n{'='*60}")
    print(f"SKOOL APPRISE MONITOR — {community}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = {"members": 0, "wins": 0, "mentions": 0, "notifications_sent": 0}

    # --- MEMBER MONITORING ---
    if not posts_only:
        print(f"\n[1/2] MEMBER MONITORING")
        member_state = load_state("members", community)

        try:
            if session and session.is_alive:
                scraped = await scrape_members_with_page(session.page, community, max_pages=1)
            else:
                scraped = await scrape_member_list(community, max_pages=2, headless=headless)
            print(f"  Scraped {len(scraped)} members")

            if init and not member_state.get("seen_ids"):
                handles = [m["handle"].lower() for m in scraped if m.get("handle")]
                add_to_state(member_state, handles)
                save_state("members", community, member_state)
                print(f"  Initialized state with {len(handles)} members. Next run will detect new ones.")
            else:
                new_members = filter_new_ids(scraped, member_state, id_key="handle")
                print(f"  New members: {len(new_members)}")

                if new_members:
                    scored = [quick_score_member(m) for m in new_members]
                    qualified = [m for m in scored if m.get("tier") in ("A", "B")]

                    tier_counts = {}
                    for m in scored:
                        t = m.get("tier", "?")
                        tier_counts[t] = tier_counts.get(t, 0) + 1
                    print(f"  Tiers: {tier_counts}")

                    if qualified:
                        results["members"] = len(qualified)
                        title, body = format_member_notification(qualified)
                        notify_type = "warning" if any(m["tier"] == "A" for m in qualified) else "info"
                        if send_apprise_notification(title, body, notify_type=notify_type, dry_run=dry_run):
                            results["notifications_sent"] += 1

                    handles = [m["handle"].lower() for m in scraped if m.get("handle")]
                    add_to_state(member_state, handles)

                save_state("members", community, member_state)

        except Exception as e:
            print(f"  ERROR in member monitoring: {e}")

    # --- POST MONITORING (wins + mentions) ---
    if not members_only:
        print(f"\n[2/2] POST MONITORING (wins + mentions)")
        post_state = load_state("posts", community)

        try:
            if session and session.is_alive:
                posts = await scrape_posts_with_page(session.page, community, max_pages=2)
            else:
                posts = await scrape_recent_posts(community, max_pages=2, headless=headless)
            print(f"  Scraped {len(posts)} posts")

            new_posts = filter_new_ids(posts, post_state, id_key="id")
            print(f"  New posts: {len(new_posts)}")

            if init and not post_state.get("seen_ids"):
                post_ids = [str(p.get("id", "")) for p in posts if p.get("id")]
                add_to_state(post_state, post_ids)
                save_state("posts", community, post_state)
                print(f"  Initialized state with {len(post_ids)} posts.")
            elif new_posts:
                wins = detect_wins(new_posts)
                if wins:
                    results["wins"] = len(wins)
                    title, body = format_wins_notification(wins)
                    if send_apprise_notification(title, body, notify_type="success", dry_run=dry_run):
                        results["notifications_sent"] += 1
                    print(f"  Financial wins detected: {len(wins)}")

                mentions = detect_mentions(new_posts)
                if mentions:
                    results["mentions"] = len(mentions)
                    title, body = format_mentions_notification(mentions)
                    if send_apprise_notification(title, body, notify_type="warning", dry_run=dry_run):
                        results["notifications_sent"] += 1
                    print(f"  Mentions detected: {len(mentions)}")

                post_ids = [str(p.get("id", "")) for p in posts if p.get("id")]
                add_to_state(post_state, post_ids)

            save_state("posts", community, post_state)

        except Exception as e:
            print(f"  ERROR in post monitoring: {e}")

    # --- SUMMARY ---
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  New ICP members: {results['members']}")
    print(f"  Financial wins:  {results['wins']}")
    print(f"  Mentions:        {results['mentions']}")
    print(f"  Notifications:   {results['notifications_sent']}")
    print(f"{'='*60}\n")

    return results


# ============================================================================
# DAEMON MODE — persistent loop with shared browser
# ============================================================================

async def run_daemon(community: str, interval: int = 180, headless: bool = True,
                      dry_run: bool = False, members_only: bool = False,
                      posts_only: bool = False):
    """
    Run the monitor in a persistent loop (daemon mode).

    Keeps a single Playwright browser alive across cycles to avoid
    cold-start overhead. Restarts the browser every 50 cycles to
    prevent memory leaks.

    Args:
        community: Skool community slug
        interval: Seconds between check cycles (default: 180 = 3 min)
        headless: Run browser headlessly
        dry_run: Print notifications but don't send
        members_only: Only check members (skip posts — faster)
        posts_only: Only check posts (skip members)
    """
    print(f"\n{'='*60}")
    print(f"SKOOL APPRISE MONITOR — DAEMON MODE")
    print(f"Community: {community}")
    print(f"Interval: {interval}s ({interval/60:.1f} min)")
    print(f"Members only: {members_only}")
    print(f"Dry run: {dry_run}")
    print(f"{'='*60}\n")

    session = BrowserSession(headless=headless)
    cycle = 0

    # Auto-init: if no state file exists, first cycle initializes state
    member_state_path = STATE_DIR / f"members_{community}.json"
    needs_init = not member_state_path.exists()
    if needs_init:
        print("  No state file found — first cycle will initialize (no notifications).")

    try:
        await session.start()

        while True:
            cycle += 1
            start_time = datetime.now()
            print(f"\n--- Cycle {cycle} | {start_time.strftime('%H:%M:%S')} ---")

            try:
                await run_monitor(
                    community=community,
                    headless=headless,
                    dry_run=dry_run,
                    members_only=members_only,
                    posts_only=posts_only,
                    session=session,
                    init=needs_init,
                )
                if needs_init:
                    needs_init = False
                    print("  State initialized. Next cycles will detect new members.")
            except Exception as e:
                print(f"  CYCLE ERROR: {e}")
                # Try to recover by restarting browser
                try:
                    await session.stop()
                except Exception:
                    pass
                await asyncio.sleep(10)
                await session.start()

            # Periodic browser restart to prevent memory leaks
            await session.maybe_restart()

            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                print(f"  Sleeping {sleep_time:.0f}s until next cycle...")
                await asyncio.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nDaemon stopped by user (Ctrl+C)")
    finally:
        await session.stop()
        print("Browser closed. Daemon exited.")


async def main():
    parser = argparse.ArgumentParser(description="Skool Apprise Monitor")
    parser.add_argument("--community", default=COMMUNITY,
                        help=f"Community slug (default: {COMMUNITY})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print notifications but don't send")
    parser.add_argument("--init", action="store_true",
                        help="Initialize state files (first run, no notifications)")
    parser.add_argument("--visible", action="store_true",
                        help="Show browser window for debugging")
    parser.add_argument("--members-only", action="store_true",
                        help="Only monitor members, skip posts")
    parser.add_argument("--posts-only", action="store_true",
                        help="Only monitor posts, skip members")
    parser.add_argument("--daemon", action="store_true",
                        help="Run in persistent loop (daemon mode)")
    parser.add_argument("--interval", type=int, default=180,
                        help="Seconds between checks in daemon mode (default: 180)")
    args = parser.parse_args()

    if args.daemon:
        await run_daemon(
            community=args.community,
            interval=args.interval,
            headless=not args.visible,
            dry_run=args.dry_run,
            members_only=args.members_only,
            posts_only=args.posts_only,
        )
    else:
        await run_monitor(
            community=args.community,
            headless=not args.visible,
            dry_run=args.dry_run,
            init=args.init,
            members_only=args.members_only,
            posts_only=args.posts_only,
        )


if __name__ == "__main__":
    asyncio.run(main())
