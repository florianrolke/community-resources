#!/usr/bin/env python3
"""
Skool Apprise Monitor v2 — Enrichment-before-alert community intelligence.

Monitors Skool communities for:
  1. New ICP members → enrich (Perplexity + Tavily LinkedIn) → notify with links
  2. Cancelled members (churn) → alert if they were ICP qualified
  3. Financial wins (regex pattern matching on posts)
  4. Anti-gravity mentions (brand mentions in posts)
  5. Meaningful @florian tags (filters out "thanks" noise)

Every event is logged to daily JSONL for the nightly digest.

Usage:
    # Daemon mode — full monitoring every 3 minutes:
    python execution/skool_apprise_monitor.py --daemon --interval 180

    # Single run:
    python execution/skool_apprise_monitor.py

    # Dry run (no notifications sent):
    python execution/skool_apprise_monitor.py --dry-run

    # Initialize state (first run, no notifications):
    python execution/skool_apprise_monitor.py --init

    # Show browser for debugging:
    python execution/skool_apprise_monitor.py --visible

Requires:
    pip install playwright requests python-dotenv
    playwright install chromium

Environment (.env):
    SKOOL_AUTH_TOKEN       — Skool session cookie (required)
    NTFY_URL               — Primary ntfy topic URL (e.g. https://push.florianrolke.com/skool-alerts)
    APPRISE_URL            — Apprise API base URL (e.g. https://notify.florianrolke.com)
    APPRISE_URLS           — Notification URLs (e.g. ntfy://ntfy.sh/skool-icp-cb311748)
    PERPLEXITY_API_KEY     — For member enrichment
    TAVILY_API_KEY_5       — For LinkedIn finder (keys 1-4 exhausted)
    TAVILY_API_KEY_6       — Fallback LinkedIn finder key
    OPENAI_API_KEY         — For post vectorization (text-embedding-3-small)
    SUPABASE_URL           — Supabase project URL
    SUPABASE_KEY           — Supabase service role key
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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Docker may not have dotenv, env vars set directly

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
# In Docker container, use /app/state; locally use .tmp/apprise_state
STATE_DIR = Path(os.getenv("STATE_DIR", str(BASE_DIR / ".tmp" / "apprise_state")))
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Event log directory
EVENTS_DIR = Path(os.getenv("EVENTS_DIR", str(STATE_DIR / "events")))
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

COMMUNITY = os.getenv("COMMUNITY", "aiautomationsbyjack")
APPRISE_URL = os.getenv("APPRISE_URL", "https://notify.florianrolke.com")
NTFY_URL = os.getenv("NTFY_URL", os.getenv("FLORIAN_NTFY_URL", "")).strip()
COMMENT_PAGE_DELAY_SECONDS = float(os.getenv("COMMENT_PAGE_DELAY_SECONDS", "1"))
COMMENT_SCAN_POST_LIMIT = int(os.getenv("COMMENT_SCAN_POST_LIMIT", "20"))
ALL_NEW_POSTS_NOTIFY_LIMIT = int(os.getenv("ALL_NEW_POSTS_NOTIFY_LIMIT", "10"))
MENTION_PREVIEW_CHARS = int(os.getenv("MENTION_PREVIEW_CHARS", "30"))


def _derive_ntfy_topic_url(base_url: str, topic: str) -> str:
    """Derive a sibling ntfy topic URL from the primary topic URL."""
    if not base_url:
        return ""
    base = base_url.rstrip("/")
    if "/" not in base:
        return ""
    return f"{base.rsplit('/', 1)[0]}/{topic}"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Default alert policy: member joins, intros, and Florian mentions only.
ALERT_MEMBER_JOINS = _env_bool("ALERT_MEMBER_JOINS", True)
ALERT_INTRO_POSTS = _env_bool("ALERT_INTRO_POSTS", True)
ALERT_MENTIONS = _env_bool("ALERT_MENTIONS", True)
NOTIFY_ALL_NEW_POSTS = _env_bool("NOTIFY_ALL_NEW_POSTS", False)
ALERT_ICP_MEMBERS = _env_bool("ALERT_ICP_MEMBERS", False)
ALERT_CHURN = _env_bool("ALERT_CHURN", False)
ALERT_WINS = _env_bool("ALERT_WINS", False)
ALERT_ANTIGRAVITY = _env_bool("ALERT_ANTIGRAVITY", False)
ALERT_REAL_ESTATE_US = _env_bool("ALERT_REAL_ESTATE_US", False)
ALERT_DAILY_DIGEST = _env_bool("ALERT_DAILY_DIGEST", False)
NTFY_ALL_POSTS_URL = (
    os.getenv("NTFY_ALL_POSTS_URL", "").strip()
    or _derive_ntfy_topic_url(NTFY_URL, "skool-all-posts")
)

# API keys for enrichment
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY", "")

# Tavily keys — start with key 5 (1-4 exhausted as of Feb 2026)
TAVILY_KEYS = []
for suffix in ["_5", "_6", "", "_2", "_3", "_4"]:
    key = os.getenv(f"TAVILY_API_KEY{suffix}", "")
    if key:
        TAVILY_KEYS.append(key)
_tavily_idx = 0
_tavily_exhausted = set()

# Mention keywords. Exact @handles always notify; name-only matches still use
# the meaningful-mention filter to suppress low-value gratitude noise.
_mention_keywords_env = os.getenv("MENTION_KEYWORDS", "")
MENTION_KEYWORDS = [
    k.strip()
    for k in (_mention_keywords_env.split(",") if _mention_keywords_env else [
        "@florianrolke",
        "@florian",
        "florianrolke",
        "florian rolke",
    ])
    if k.strip()
]

_intro_keywords_env = os.getenv("INTRO_CATEGORY_KEYWORDS", "")
INTRO_CATEGORY_KEYWORDS = [
    k.strip().lower()
    for k in (_intro_keywords_env.split(",") if _intro_keywords_env else [
        "intro",
        "introduction",
        "introductions",
        "start here",
    ])
    if k.strip()
]

# Anti-gravity / brand keywords
ANTIGRAVITY_KEYWORDS = [
    "anti-gravity", "antigravity", "anti gravity",
    "florianrolke", "florian rolke",
]

# Money patterns
MONEY_PATTERNS = [
    r'\$[\d,]+k?',
    r'(?:closed|signed|landed).{0,20}\$',
    r'(?:revenue|deal|contract).{0,30}\$',
    r'(?:6|7|six|seven)-?figure',
    r'(?:first|biggest).{0,20}(?:client|deal|sale)',
    r'(?:won|landed|secured).{0,20}(?:client|deal|contract)',
]

# Gratitude words for tag filtering
GRATITUDE_WORDS = {
    "thanks", "thank you", "thx", "ty", "appreciate", "appreciated",
    "grateful", "kudos", "cheers", "shoutout", "shout out",
}

# Discussion indicators for meaningful tag detection
DISCUSSION_INDICATORS = {
    "how", "what", "why", "when", "where", "which", "who",
    "anyone", "question", "help", "advice", "thoughts",
    "opinion", "recommend", "suggestion", "idea", "strategy",
    "struggling", "issue", "problem", "challenge",
}


# SAFETY: Only these email addresses may receive emails via ANY path
ALLOWED_EMAIL_RECIPIENTS = {"you@example.com", "you@example.com"}


def build_apprise_urls():
    """Build Apprise notification URLs from env vars."""
    urls = []
    email_to = os.getenv("APPRISE_EMAIL_TO", os.getenv("NOTIFY_EMAIL_TO", ""))
    smtp_user = os.getenv("SMTP_USER", os.getenv("NOTIFY_EMAIL_FROM", ""))
    smtp_pass = os.getenv("SMTP_PASS", os.getenv("NOTIFY_EMAIL_PASSWORD", ""))
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    if email_to and smtp_user and smtp_pass:
        if email_to.lower().strip() not in ALLOWED_EMAIL_RECIPIENTS:
            print(f"  [BLOCKED] Apprise mailto to {email_to} — not in allowed list {ALLOWED_EMAIL_RECIPIENTS}")
        else:
            urls.append(f"mailto://{smtp_user}:{smtp_pass}@{smtp_host}?to={email_to}")
    custom = os.getenv("APPRISE_URLS", "")
    if custom:
        urls.extend([u.strip() for u in custom.split(",") if u.strip()])
    return urls


# ============================================================================
# POST VECTORIZATION (Supabase pgvector) — uses raw requests, no extra packages
# ============================================================================

_vectorize_enabled = None

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
POSTS_TABLE = "skool_posts"


def _init_vectorize():
    """Check if vectorization env vars are set. Returns True if ready."""
    global _vectorize_enabled

    if _vectorize_enabled is not None:
        return _vectorize_enabled

    if not SUPABASE_URL or not SUPABASE_KEY or not OPENAI_API_KEY:
        print("  [vectorize] Disabled — missing SUPABASE_URL, SUPABASE_KEY, or OPENAI_API_KEY")
        _vectorize_enabled = False
        return False

    # Quick table check via REST
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{POSTS_TABLE}?select=id&limit=1",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10,
        )
        if r.status_code == 200:
            _vectorize_enabled = True
            print("  [vectorize] Enabled — Supabase + OpenAI connected")
            return True
        else:
            print(f"  [vectorize] Disabled — table check returned {r.status_code}: {r.text[:100]}")
            _vectorize_enabled = False
            return False
    except Exception as e:
        print(f"  [vectorize] Disabled — init error: {e}")
        _vectorize_enabled = False
        return False


def _build_post_embedding_text(post: dict) -> str:
    """Build embedding text from post dict (monitor format)."""
    parts = []
    title = post.get("title") or ""
    if title:
        parts.append(f"Title: {title}")
    author = post.get("authorName") or ""
    if author:
        parts.append(f"Author: {author}")
    category = post.get("categoryName") or ""
    if category:
        parts.append(f"Category: {category}")
    content = (post.get("content") or "")[:2000]
    if content:
        parts.append(f"Content: {content}")
    return "\n".join(parts)


def _openai_embeddings(texts: list) -> list:
    """Generate embeddings via OpenAI REST API (no sdk needed)."""
    r = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBEDDING_MODEL, "input": texts},
        timeout=30,
    )
    r.raise_for_status()
    return [item["embedding"] for item in r.json()["data"]]


def _supabase_upsert(records: list):
    """Upsert records to Supabase via REST API (no sdk needed)."""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{POSTS_TABLE}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        json=records,
        timeout=30,
    )
    r.raise_for_status()


def vectorize_new_posts(posts: list, community: str):
    """Embed and upsert new posts to Supabase. Gracefully skips if not configured."""
    if not _init_vectorize():
        return

    if not posts:
        return

    try:
        # Build embedding texts + records
        embedding_texts = []
        records = []
        for post in posts:
            post_id = str(post.get("id", ""))
            if not post_id:
                continue
            post_url = post.get("postUrl") or post.get("url") or ""
            slug = post.get("slug") or (post_url.split("/")[-1] if "/" in post_url else "")
            author = post.get("authorName") or ""
            emb_text = _build_post_embedding_text(post)

            embedding_texts.append(emb_text)
            records.append({
                "id": post_id,
                "community": community,
                "title": (post.get("title") or "")[:500],
                "slug": slug,
                "content": (post.get("content") or "")[:10000],
                "author_name": author,
                "author_id": (post.get("author", {}) or {}).get("username", ""),
                "author_profile_url": "",
                "created_at": post.get("createdAt") or None,
                "likes": post.get("likesCount", 0) or 0,
                "comment_count": post.get("commentsCount", 0) or 0,
                "pinned": False,
                "category": post.get("categoryName") or "",
                "category_id": "",
                "post_url": post_url,
                "comments": "[]",
                "embedding_text": emb_text[:5000],
            })

        if not records:
            return

        # Generate embeddings via OpenAI REST API
        embeddings = _openai_embeddings(embedding_texts)

        # Add embeddings to records
        for record, embedding in zip(records, embeddings):
            record["embedding"] = embedding

        # Upsert via Supabase REST API
        _supabase_upsert(records)
        print(f"  [vectorize] Upserted {len(records)} posts to Supabase")

    except Exception as e:
        print(f"  [vectorize] Error: {e}")
        # Non-fatal — monitor continues even if vectorization fails


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
        self._restart_every = 50

    async def start(self):
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
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = self.context = self.browser = self._playwright = None

    async def maybe_restart(self):
        self._cycle_count += 1
        if self._cycle_count >= self._restart_every:
            print(f"  Restarting browser (cycle {self._cycle_count})...")
            await self.stop()
            await self.start()

    @property
    def is_alive(self) -> bool:
        return self.page is not None and self.browser is not None


# ============================================================================
# INLINE ENRICHMENT — Perplexity + Tavily LinkedIn
# ============================================================================

def _get_tavily_key():
    """Get next available Tavily key, skipping exhausted ones."""
    global _tavily_idx
    if not TAVILY_KEYS:
        return None
    for _ in range(len(TAVILY_KEYS)):
        idx = _tavily_idx % len(TAVILY_KEYS)
        _tavily_idx += 1
        if idx not in _tavily_exhausted:
            return TAVILY_KEYS[idx]
    return None


LINKEDIN_PATTERN = re.compile(
    r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)',
    re.IGNORECASE
)


def _extract_linkedin_url(text: str):
    """Extract first valid LinkedIn /in/ URL from text."""
    if not text:
        return None
    match = LINKEDIN_PATTERN.search(text)
    if match:
        slug = match.group(1).rstrip('/')
        if slug.lower() in ('example', 'username', 'yourname', 'profile', '', 'dir'):
            return None
        return f"https://www.linkedin.com/in/{slug}"
    return None


def _validate_linkedin_for_person(url: str, name: str) -> bool:
    """Check that a LinkedIn URL likely belongs to this person."""
    if not url or not name:
        return False
    slug = url.split('/in/')[-1].lower().rstrip('/')
    slug_clean = re.sub(r'-[0-9a-f]{6,}$', '', slug)
    name_parts = [p.lower() for p in name.split() if len(p) > 1]
    if not name_parts:
        return False
    if len(name_parts) >= 2:
        last = name_parts[-1]
        if last not in slug_clean:
            return False
        first = name_parts[0]
        return first in slug_clean or first[:3] in slug_clean
    return name_parts[0] in slug_clean


def enrich_with_perplexity(name: str, bio: str, profile_url: str) -> dict:
    """Quick Perplexity enrichment — extract company, website, services, city."""
    if not PERPLEXITY_KEY:
        return {}

    bio_context = f'\nTheir Skool bio says: "{bio}"' if bio and len(bio.strip()) > 3 else ""
    prompt = f"""Research this person and extract business intelligence. They are a member of an AI automation community on Skool.

Name: {name}
Skool profile: {profile_url}{bio_context}

Extract and return as JSON only (no markdown, no explanation):
{{
    "company_name": "their company name or null",
    "company_description": "1-2 sentence description or null",
    "website": "personal/business website if found or null",
    "city": "city name or null",
    "country": "country name or null",
    "services": ["list of services they offer"],
    "industries": ["industries/niches they serve"],
    "linkedin_url": "LinkedIn profile URL if found or null",
    "confidence": "high/medium/low"
}}

Only include factual, verifiable information. If you can't find much, mark confidence as low."""

    try:
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'sonar',
                'messages': [
                    {'role': 'system', 'content': 'You are a business research assistant. Return valid JSON only, no markdown code blocks.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 600
            },
            timeout=15
        )
        if response.status_code == 200:
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            # Parse JSON from response
            content = content.strip()
            if content.startswith('```'):
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON object in text
                match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
            return {}
        elif response.status_code == 429:
            print(f"    Perplexity rate limited")
            return {}
        else:
            print(f"    Perplexity error: {response.status_code}")
            return {}
    except Exception as e:
        print(f"    Perplexity exception: {e}")
        return {}


def find_linkedin_tavily(name: str, company: str = "", location: str = "") -> str | None:
    """Search Tavily for LinkedIn profile URL. Returns normalized URL or None."""
    key = _get_tavily_key()
    if not key:
        return None

    query_parts = [f'"{name}"']
    if company:
        query_parts.append(f'"{company}"')
    if location:
        city = location.split('(')[0].strip() if '(' in location else location
        if city:
            query_parts.append(city)

    try:
        response = requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key': key,
                'query': " ".join(query_parts),
                'search_depth': 'basic',
                'max_results': 5,
                'include_answer': False,
                'include_domains': ['linkedin.com']
            },
            timeout=15
        )

        if response.status_code == 200:
            results = response.json().get('results', [])
            for r in results:
                li_url = _extract_linkedin_url(r.get('url', ''))
                if li_url and _validate_linkedin_for_person(li_url, name):
                    return li_url
            # Check content for embedded URLs
            for r in results:
                li_url = _extract_linkedin_url(r.get('content', ''))
                if li_url and _validate_linkedin_for_person(li_url, name):
                    return li_url
            return None
        elif response.status_code in (429, 432):
            idx = (_tavily_idx - 1) % len(TAVILY_KEYS)
            _tavily_exhausted.add(idx)
            print(f"    Tavily key {idx+1} exhausted, rotating...")
            return find_linkedin_tavily(name, company, location)
        else:
            print(f"    Tavily error: {response.status_code}")
            return None
    except Exception as e:
        print(f"    Tavily exception: {e}")
        return None


def enrich_member(member: dict) -> dict:
    """
    Full inline enrichment: Perplexity → Tavily LinkedIn.

    Returns enrichment dict with: company, website, linkedin, city, etc.
    This runs BEFORE notification so links are ready.
    """
    name = member.get("name", "")
    bio = member.get("bio", "")
    profile_url = member.get("profileUrl", "")

    enrichment = {"enriched_at": datetime.now(timezone.utc).isoformat()}

    # Step 1: Perplexity quick enrichment
    print(f"    Enriching {name}...")
    perplexity_data = enrich_with_perplexity(name, bio, profile_url)
    if perplexity_data:
        enrichment["company"] = perplexity_data.get("company_name") or ""
        enrichment["company_description"] = perplexity_data.get("company_description") or ""
        enrichment["website"] = perplexity_data.get("website") or ""
        enrichment["city"] = perplexity_data.get("city") or ""
        enrichment["country"] = perplexity_data.get("country") or ""
        enrichment["services"] = perplexity_data.get("services") or []
        enrichment["industries"] = perplexity_data.get("industries") or []
        enrichment["confidence"] = perplexity_data.get("confidence", "low")
        # Perplexity might find LinkedIn incidentally
        perplexity_linkedin = perplexity_data.get("linkedin_url")
        if perplexity_linkedin:
            li_url = _extract_linkedin_url(perplexity_linkedin)
            if li_url:
                enrichment["linkedin"] = li_url
                enrichment["linkedin_source"] = "perplexity"

    # Step 2: Dedicated Tavily LinkedIn finder (if Perplexity didn't find it)
    if not enrichment.get("linkedin"):
        company = enrichment.get("company", "")
        location = enrichment.get("city", "")
        linkedin_url = find_linkedin_tavily(name, company, location)
        if linkedin_url:
            enrichment["linkedin"] = linkedin_url
            enrichment["linkedin_source"] = "tavily"

    found = []
    if enrichment.get("linkedin"):
        found.append("LinkedIn")
    if enrichment.get("website"):
        found.append("website")
    if enrichment.get("company"):
        found.append("company")
    print(f"    Enriched: {', '.join(found) if found else 'minimal data'}")

    return enrichment


# ============================================================================
# ICP SCORING
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

REAL_ESTATE_KEYWORDS = [
    "real estate", "realtor", "realty", "brokerage", "property management",
    "property manager", "property investor", "real estate investor",
    "commercial real estate", "multifamily", "multi-family", "single family",
    "wholesale real estate", "wholesaling", "house flipper", "fix and flip",
    "mortgage broker", "loan officer", "title company", "escrow",
]

US_LOCATION_KEYWORDS = [
    "united states", "usa", "u.s.", "america",
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
    "los angeles", "san francisco", "san diego", "new york", "miami",
    "austin", "dallas", "houston", "phoenix", "denver", "chicago",
    "atlanta", "charlotte", "nashville", "orlando", "tampa", "seattle",
]

US_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}


def quick_score_member(member: dict, enrichment: dict = None) -> dict:
    """Keyword-based ICP scoring. Uses bio + enrichment data for scoring."""
    name = (member.get("name", "") or "").lower()
    bio = (member.get("bio", "") or "").lower()

    # Include enrichment data in scoring text
    extra_text = ""
    if enrichment:
        extra_text = " ".join([
            enrichment.get("company", ""),
            enrichment.get("company_description", ""),
            " ".join(enrichment.get("services", [])),
            " ".join(enrichment.get("industries", [])),
        ]).lower()

    text = f"{name} {bio} {extra_text}"

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


def _member_signal_text(member: dict, enrichment: dict | None = None) -> str:
    parts = [
        member.get("name", ""),
        member.get("bio", ""),
        member.get("location", ""),
        member.get("raw_location", ""),
    ]
    raw_fields = member.get("raw_fields", {}) or {}
    for key in ("location", "city", "state", "country", "bio", "headline"):
        value = raw_fields.get(key)
        if isinstance(value, str):
            parts.append(value)
    if enrichment:
        parts.extend([
            enrichment.get("company", ""),
            enrichment.get("company_description", ""),
            " ".join(enrichment.get("services", [])),
            " ".join(enrichment.get("industries", [])),
            enrichment.get("city", ""),
            enrichment.get("country", ""),
        ])
    return " ".join(p for p in parts if p).lower()


def _member_location_text(member: dict, enrichment: dict | None = None) -> str:
    raw_fields = member.get("raw_fields", {}) or {}
    parts = [
        member.get("location", ""),
        member.get("raw_location", ""),
        raw_fields.get("location", ""),
        raw_fields.get("city", ""),
        raw_fields.get("state", ""),
        raw_fields.get("country", ""),
    ]
    if enrichment:
        parts.extend([enrichment.get("city", ""), enrichment.get("country", "")])
    return " ".join(str(p) for p in parts if p)


def _match_us_location(text: str, location_text: str = "") -> str:
    combined = text.lower()
    for keyword in US_LOCATION_KEYWORDS:
        if keyword in combined:
            return keyword

    loc = location_text.strip()
    if loc:
        loc_upper = re.sub(r"[^A-Za-z]", " ", loc).upper()
        tokens = set(loc_upper.split())
        matches = sorted(tokens & US_STATE_ABBREVIATIONS)
        if matches:
            return matches[0]

    abbreviation_pattern = r",\s*(" + "|".join(sorted(US_STATE_ABBREVIATIONS)) + r")\b"
    match = re.search(abbreviation_pattern, text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return ""


def detect_real_estate_us_members(members: list, enrichment_by_handle: dict | None = None) -> list:
    """Find new members who appear real-estate-related and US-based."""
    matches = []
    enrichment_by_handle = enrichment_by_handle or {}
    for member in members:
        handle = (member.get("handle") or "").lower()
        enrichment = enrichment_by_handle.get(handle)
        signal_text = _member_signal_text(member, enrichment)
        real_estate_kw = next((kw for kw in REAL_ESTATE_KEYWORDS if kw in signal_text), "")
        if not real_estate_kw:
            continue
        location_text = _member_location_text(member, enrichment)
        us_signal = _match_us_location(signal_text, location_text)
        if not us_signal:
            continue
        enriched = dict(member)
        enriched["real_estate_signal"] = real_estate_kw
        enriched["us_signal"] = us_signal
        matches.append(enriched)
    return matches


# ============================================================================
# DETECTION: WINS + MENTIONS + MEANINGFUL TAGS
# ============================================================================

def detect_money_pattern(text: str):
    """Detect monetary win patterns in text."""
    text_lower = text.lower()
    for pattern in MONEY_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def is_meaningful_mention(post: dict) -> bool:
    """
    Filter out noise mentions. A mention is meaningful if:
    - Post is > 15 words (excluding the tag itself)
    - Contains a question mark OR discussion indicator words
    - Is NOT purely gratitude
    """
    content = (post.get('content', '') or post.get('title', '')).strip()
    if not content:
        return False

    # Remove the tag itself for word counting
    cleaned = re.sub(r'@\w+', '', content).strip()
    words = cleaned.split()
    word_count = len(words)

    # Must be substantial enough
    if word_count < 15:
        return False

    content_lower = cleaned.lower()

    # Check if it's purely gratitude
    gratitude_count = sum(1 for w in GRATITUDE_WORDS if w in content_lower)
    non_gratitude_words = [w for w in words if w.lower().strip('.,!?') not in GRATITUDE_WORDS]
    if gratitude_count > 0 and len(non_gratitude_words) < 10:
        return False

    # Must contain a question or discussion indicator
    has_question = '?' in content
    has_discussion = any(indicator in content_lower for indicator in DISCUSSION_INDICATORS)

    return has_question or has_discussion


def _combined_text(item: dict) -> str:
    """Return title + content/body text for mention detection."""
    title = item.get('title', '') or ''
    content = item.get('content', '') or item.get('body', '') or ''
    return f"{title}\n{content}".strip()


def _body_text(item: dict) -> str:
    """Return only the actual post/comment body text for notification previews."""
    return (item.get('content', '') or item.get('body', '') or item.get('text', '') or '').strip()


def _short_preview(text: str, limit: int = MENTION_PREVIEW_CHARS) -> str:
    cleaned = re.sub(r'\s+', ' ', text or '').strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def _post_comment_count(post: dict) -> int:
    try:
        return int(post.get('commentsCount', post.get('commentCount', 0)) or 0)
    except (TypeError, ValueError):
        return 0


def is_intro_post(post: dict) -> bool:
    """Return True when a post belongs to an introduction-like category."""
    category = (
        post.get('categoryName')
        or post.get('category')
        or post.get('labelName')
        or ''
    ).lower()
    return bool(category) and any(keyword in category for keyword in INTRO_CATEGORY_KEYWORDS)


def select_posts_for_comment_scan(posts: list, new_posts: list, comment_state: dict,
                                  limit: int = COMMENT_SCAN_POST_LIMIT) -> list:
    """Pick new or changed-comment posts for comment mention scanning."""
    new_ids = {str(p.get('id') or p.get('postId') or '') for p in new_posts}
    previous_counts = comment_state.get('post_comment_counts', {}) or {}
    selected = []
    seen = set()

    for post in posts:
        post_id = str(post.get('id') or post.get('postId') or '')
        if not post_id or post_id in seen:
            continue
        count = _post_comment_count(post)
        if count <= 0:
            continue
        previous = previous_counts.get(post_id)
        if post_id in new_ids or previous is None or int(previous or 0) != count:
            selected.append(post)
            seen.add(post_id)
        if len(selected) >= limit:
            break

    return selected


def detect_mentions_in_source(source: dict, location: str = "post",
                              parent_post: dict | None = None) -> list:
    """Detect configured mention keywords in a post or comment source."""
    content = _combined_text(source)
    content_lower = content.lower()
    mentions = []

    for keyword in MENTION_KEYWORDS:
        keyword_lower = keyword.lower()
        if keyword_lower not in content_lower:
            continue

        exact_tag = keyword.startswith('@')
        meaningful = True if exact_tag else is_meaningful_mention({
            'title': source.get('title', ''),
            'content': content,
        })
        pos = content_lower.find(keyword_lower)
        start = max(0, pos - 80)
        end = min(len(content), pos + len(keyword) + 80)
        context = content[start:end].strip()
        if start > 0:
            context = '...' + context
        if end < len(content):
            context = context + '...'

        post = parent_post or source
        body_text = _body_text(source) or content
        mentions.append({
            'post_id': post.get('id') or post.get('postId') or source.get('postId'),
            'comment_id': source.get('id') if location == "comment" else '',
            'type': '@mention' if exact_tag else 'name_mention',
            'location': location,
            'keyword': keyword,
            'meaningful': meaningful,
            'author_name': source.get('authorName') or source.get('author', {}).get('name', 'Unknown'),
            'author_handle': source.get('authorHandle') or source.get('author', {}).get('username', '') or source.get('author', {}).get('name', ''),
            'post_title': post.get('title', ''),
            'post_url': post.get('url') or post.get('postUrl', ''),
            'context': context,
            'preview': _short_preview(body_text),
            'likes_count': post.get('likesCount', post.get('likes', 0)),
            'comments_count': _post_comment_count(post),
        })
        break

    return mentions


def detect_mentions(posts: list) -> list:
    """Detect @mentions and name mentions of Florian in posts. Filters for meaningful ones."""
    mentions = []
    for post in posts:
        mentions.extend(detect_mentions_in_source(post, location="post"))
    return mentions


def detect_comment_mentions(comments_by_post: dict, comment_state: dict) -> list:
    """Detect mentions in newly observed comments only."""
    seen_comment_ids = {str(i) for i in comment_state.get("seen_ids", [])}
    mentions = []
    for post_id, payload in comments_by_post.items():
        post = payload.get("post", {})
        for comment in payload.get("comments", []):
            comment_id = str(comment.get("id") or "")
            if not comment_id or comment_id in seen_comment_ids:
                continue
            mentions.extend(detect_mentions_in_source(comment, location="comment", parent_post=post))
    return mentions


def detect_antigravity_mentions(posts: list) -> list:
    """Detect anti-gravity/brand mentions in posts (separate from @mentions)."""
    mentions = []
    for post in posts:
        content = (post.get('content', '') or '') + ' ' + (post.get('title', '') or '')
        content_lower = content.lower()

        for keyword in ANTIGRAVITY_KEYWORDS:
            if keyword in content_lower:
                pos = content_lower.find(keyword)
                start = max(0, pos - 60)
                end = min(len(content), pos + len(keyword) + 60)
                context = content[start:end].strip()

                mentions.append({
                    'post_id': post.get('id') or post.get('postId'),
                    'keyword': keyword,
                    'author_name': post.get('authorName') or post.get('author', {}).get('name', 'Unknown'),
                    'author_handle': post.get('author', {}).get('username', ''),
                    'post_title': post.get('title', ''),
                    'post_url': post.get('url') or post.get('postUrl', ''),
                    'context': context,
                })
                break
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
                'author_handle': post.get('author', {}).get('username', ''),
                'money_pattern': money_match,
                'post_url': post.get('url') or post.get('postUrl', ''),
                'likes_count': post.get('likesCount', 0),
                'comments_count': post.get('commentsCount', 0),
            })
    return wins


# ============================================================================
# MEMBER SCRAPING
# ============================================================================

def _parse_members_from_next_data(next_data: dict, community: str, seen_handles: set) -> list:
    """Extract member dicts from __NEXT_DATA__ JSON."""
    members = []
    page_props = next_data.get('props', {}).get('pageProps', {}) or {}
    member_list = (
        page_props.get('members', []) or
        page_props.get('groupMembers', []) or
        page_props.get('users', []) or []
    )

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
        if m.get('firstName') or m.get('lastName'):
            first = m.get("firstName", "")
            last = m.get("lastName", "")
            full_name = f"{first} {last}".strip() or m.get("name", "")
            handle = m.get("name", "")
            meta = m.get("metadata", {}) or {}
            bio = meta.get("bio", "") or ""
            location = meta.get("location") or meta.get("city") or meta.get("country") or ""
            member_data = {
                "name": full_name,
                "handle": handle,
                "bio": bio,
                "location": location,
                "profileUrl": f"https://www.skool.com/@{handle}",
                "joinedAt": m.get("createdAt", "") or m.get("joinedAt", ""),
                "raw_fields": {
                    "location": meta.get("location", ""),
                    "city": meta.get("city", ""),
                    "state": meta.get("state", ""),
                    "country": meta.get("country", ""),
                    "headline": meta.get("headline", ""),
                },
            }
        elif 'user' in m and isinstance(m['user'], dict):
            user = m['user']
            meta = user.get("metadata", {}) or m.get("metadata", {}) or {}
            location = user.get("location", "") or meta.get("location", "") or meta.get("city", "") or meta.get("country", "")
            member_data = {
                "name": user.get("name", ""),
                "handle": user.get("username", "") or user.get("handle", ""),
                "bio": user.get("bio", "") or m.get("bio", ""),
                "location": location,
                "profileUrl": f"https://www.skool.com/@{user.get('username', '')}",
                "joinedAt": m.get("createdAt", "") or m.get("joinedAt", ""),
                "raw_fields": {
                    "location": location,
                    "city": meta.get("city", ""),
                    "state": meta.get("state", ""),
                    "country": meta.get("country", ""),
                    "headline": meta.get("headline", ""),
                },
            }
        else:
            meta = m.get("metadata", {}) or {}
            location = m.get("location", "") or meta.get("location", "") or meta.get("city", "") or meta.get("country", "")
            member_data = {
                "name": m.get("name", ""),
                "handle": m.get("username", "") or m.get("handle", "") or m.get("name", ""),
                "bio": m.get("bio", ""),
                "location": location,
                "profileUrl": f"https://www.skool.com/@{m.get('username', m.get('handle', m.get('name', '')))}",
                "joinedAt": m.get("createdAt", "") or m.get("joinedAt", ""),
                "raw_fields": {
                    "location": location,
                    "city": meta.get("city", ""),
                    "state": meta.get("state", ""),
                    "country": meta.get("country", ""),
                    "headline": meta.get("headline", ""),
                },
            }

        handle = member_data["handle"].lower()
        if handle and handle not in seen_handles:
            seen_handles.add(handle)
            member_data["community"] = community
            members.append(member_data)

    return members


async def scrape_members_with_page(page, community: str, max_pages: int = 1) -> list:
    """Scrape newest members using an existing Playwright page."""
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
    """Scrape newest members (standalone browser)."""
    session = BrowserSession(headless=headless)
    await session.start()
    try:
        return await scrape_members_with_page(session.page, community, max_pages)
    finally:
        await session.stop()


# ============================================================================
# CANCELLING TAB SCRAPER — detects paid cancellations
# ============================================================================

def _parse_cancelling_from_next_data(next_data: dict, community: str) -> list:
    """
    Parse members from the Cancelling tab's __NEXT_DATA__.

    Each member has subscription status info. We extract:
    - Basic member data (name, handle, bio)
    - Whether it's a trial cancellation or paid cancellation
    - Days until churn
    - Price/plan info

    From screenshots, Skool shows:
    - "Trial cancelled (removing in 1 day)" → trial, skip
    - "Cancelled (churns in 25 days)" → paid, ALERT
    """
    members = []
    page_props = next_data.get('props', {}).get('pageProps', {}) or {}

    # Try all possible member list locations
    member_list = (
        page_props.get('members', []) or
        page_props.get('groupMembers', []) or
        page_props.get('users', []) or []
    )

    # Check dehydratedState as fallback
    if not member_list:
        dehydrated = page_props.get('dehydratedState', {})
        if dehydrated:
            for q in dehydrated.get('queries', []):
                data = q.get('state', {}).get('data', {})
                if isinstance(data, dict):
                    items = data.get('items', []) or data.get('members', []) or data.get('data', [])
                    if items and isinstance(items, list) and len(items) > 0:
                        first = items[0]
                        if isinstance(first, dict) and ('name' in first or 'user' in first or 'firstName' in first):
                            member_list = items
                            break
                elif isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, dict) and ('name' in first or 'user' in first or 'firstName' in first):
                        member_list = data
                        break

    for m in member_list:
        # Extract basic member info (same parsing as active members)
        if m.get('firstName') or m.get('lastName'):
            first = m.get("firstName", "")
            last = m.get("lastName", "")
            full_name = f"{first} {last}".strip() or m.get("name", "")
            handle = m.get("name", "")
            meta = m.get("metadata", {}) or {}
            bio = meta.get("bio", "") or ""
        elif 'user' in m and isinstance(m['user'], dict):
            user = m['user']
            full_name = user.get("name", "")
            handle = user.get("username", "") or user.get("handle", "")
            bio = user.get("bio", "") or m.get("bio", "")
        else:
            full_name = m.get("name", "")
            handle = m.get("username", "") or m.get("handle", "") or m.get("name", "")
            bio = m.get("bio", "")

        if not handle:
            continue

        # Extract subscription/cancellation status from all possible fields
        member_meta = m.get("metadata", {}) or {}
        member_obj = m.get("member", {}) or {}
        member_member_meta = member_obj.get("metadata", {}) or {}

        # Look for cancellation indicators in various Skool data shapes
        # The key is distinguishing "Trial cancelled" from "Cancelled" (paid)
        is_trial = False
        cancel_status = ""
        price = ""
        joined_at = m.get("createdAt", "") or m.get("joinedAt", "") or member_obj.get("createdAt", "")

        # Check for trial indicators in all available fields
        # Skool may use: trialEnd, isTrial, subscriptionStatus, cancelReason, etc.
        all_fields = {**m, **member_meta, **member_obj, **member_member_meta}

        # Check for explicit trial flags
        if all_fields.get("isTrial") or all_fields.get("is_trial"):
            is_trial = True
        if all_fields.get("trialEnd") or all_fields.get("trial_end"):
            is_trial = True
        # subscription object may contain plan details
        sub = all_fields.get("subscription", {}) or {}
        if isinstance(sub, dict):
            if sub.get("trial") or sub.get("isTrial"):
                is_trial = True
            price = sub.get("price", "") or sub.get("amount", "")
            cancel_status = sub.get("status", "") or sub.get("cancelStatus", "")

        # Check cancelledAt vs trialCancelledAt
        if all_fields.get("trialCancelledAt") or all_fields.get("trialCanceledAt"):
            is_trial = True
        if all_fields.get("cancelledAt") or all_fields.get("canceledAt"):
            if not is_trial:
                cancel_status = "cancelled"

        # Check the status/memberStatus field
        status = (all_fields.get("status", "") or all_fields.get("memberStatus", "") or "").lower()
        if "trial" in status:
            is_trial = True

        members.append({
            "name": full_name,
            "handle": handle.lower(),
            "bio": bio,
            "profileUrl": f"https://www.skool.com/@{handle}",
            "community": community,
            "joinedAt": joined_at,
            "is_trial": is_trial,
            "cancel_status": cancel_status,
            "price": str(price),
            "raw_fields": {
                k: str(v)[:200] for k, v in all_fields.items()
                if k not in ('metadata', 'member', 'user', 'dehydratedState')
                and v is not None and str(v).strip()
            },
        })

    return members


async def scrape_cancelling_with_page(page, community: str, max_pages: int = 2) -> list:
    """
    Scrape the Cancelling tab to detect members who cancelled their subscription.

    URL: /{community}/-/members?tab=cancelling&sort=newest
    """
    all_cancelling = []
    seen_handles = set()

    for page_num in range(1, max_pages + 1):
        url = f"https://www.skool.com/{community}/-/members?tab=cancelling&sort=newest"
        if page_num > 1:
            url += f"&p={page_num}"

        print(f"  [Cancelling {page_num}/{max_pages}] Loading...")
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
            # On first page, dump a sample of raw data to help debug field names
            if page_num == 1:
                page_props = next_data.get('props', {}).get('pageProps', {}) or {}
                sample_list = (
                    page_props.get('members', []) or
                    page_props.get('groupMembers', []) or
                    page_props.get('users', []) or []
                )
                if not sample_list:
                    dehydrated = page_props.get('dehydratedState', {})
                    if dehydrated:
                        for q in dehydrated.get('queries', []):
                            data = q.get('state', {}).get('data', {})
                            if isinstance(data, dict):
                                items = data.get('items', []) or data.get('members', []) or []
                                if items:
                                    sample_list = items
                                    break
                if sample_list:
                    first = sample_list[0]
                    # Log field keys from first cancelling member for debugging
                    print(f"    Cancelling member fields: {list(first.keys())[:15]}")
                    member_sub = first.get("member", {})
                    if member_sub:
                        print(f"    member sub-fields: {list(member_sub.keys())[:15]}")
                    meta = first.get("metadata", {})
                    if meta:
                        print(f"    metadata fields: {list(meta.keys())[:10]}")

            members = _parse_cancelling_from_next_data(next_data, community)
            for m in members:
                h = m["handle"]
                if h not in seen_handles:
                    seen_handles.add(h)
                    all_cancelling.append(m)

            print(f"    Found {len(members)} cancelling members (page {page_num})")

        if page_num < max_pages:
            await asyncio.sleep(5)

    return all_cancelling


def detect_new_cancellations(cancelling_members: list, community: str,
                              enrichment_cache: dict) -> list:
    """
    Detect NEW paid cancellations from the Cancelling tab scrape.

    Compares against previously seen cancelling handles to only alert once per member.
    Filters out trial cancellations — only alerts for paid $77/month cancellations.
    On first run (no state file yet), seeds state silently — no flood of old cancellations.

    Returns list of cancellation dicts ready for ICP scoring + notification.
    """
    state_path = STATE_DIR / f"cancelling_{community}.json"

    # First run: seed all current handles without alerting (prevents flood on deploy)
    if not state_path.exists():
        cancel_state = {"seen_ids": []}
        all_handles = [m["handle"] for m in cancelling_members if m.get("handle")]
        add_to_state(cancel_state, all_handles)
        save_state("cancelling", community, cancel_state)
        print(f"  Cancelling state initialized: {len(all_handles)} handles (no alerts on first run)")
        return []

    cancel_state = load_state("cancelling", community)
    seen_cancelling = set(cancel_state.get("seen_ids", []))

    new_cancellations = []

    for member in cancelling_members:
        handle = member["handle"]

        # Skip if we already alerted for this cancellation
        if handle in seen_cancelling:
            continue

        # Skip trial cancellations — we only care about PAID cancellations
        if member.get("is_trial"):
            print(f"    Skip trial cancel: {member['name']} ({handle})")
            seen_cancelling.add(handle)
            continue

        # This is a new paid cancellation — prepare for ICP scoring + notification
        cached = enrichment_cache.get(handle, {})
        enrichment = cached.get("enrichment", {})

        new_cancellations.append({
            "handle": handle,
            "name": member.get("name", handle),
            "bio": member.get("bio", ""),
            "profileUrl": member.get("profileUrl", f"https://www.skool.com/@{handle}"),
            "joinedAt": member.get("joinedAt", ""),
            "tier": cached.get("tier", "unknown"),
            "icp_score": cached.get("icp_score", 0),
            "enrichment": enrichment,
            "raw_fields": member.get("raw_fields", {}),
        })

    # Update state with ALL cancelling handles (trial + paid) to avoid re-processing
    all_handles = [m["handle"] for m in cancelling_members]
    add_to_state(cancel_state, all_handles)
    save_state("cancelling", community, cancel_state)

    return new_cancellations


# ============================================================================
# POST SCRAPING
# ============================================================================

def _extract_group_metadata(next_data: dict) -> tuple[str, dict]:
    """Extract Skool group id and label-id -> category-name mapping."""
    page_props = next_data.get('props', {}).get('pageProps', {}) or {}
    current_group = page_props.get('currentGroup', {}) or {}
    group_id = current_group.get('id', '') or page_props.get('groupId', '')
    labels = {}

    for label in current_group.get('labels', []) or []:
        label_id = label.get('id', '')
        display = (
            label.get('metadata', {}).get('displayName')
            or label.get('name')
            or label.get('displayName')
            or ''
        )
        if label_id and display:
            labels[label_id] = display

    return group_id, labels


async def scrape_posts_with_page(page, community: str, max_pages: int = 2) -> list:
    """Scrape recent posts using an existing Playwright page."""
    posts = []
    seen_ids = set()
    group_id = ""
    labels = {}

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
            next_group_id, next_labels = _extract_group_metadata(next_data)
            group_id = group_id or next_group_id
            labels.update(next_labels)
            page_props = next_data.get('props', {}).get('pageProps', {}) or {}

            # Skool uses postTrees[].post with metadata for content
            post_trees = page_props.get('postTrees', []) or []
            post_list = page_props.get('posts', []) or []

            if post_trees:
                # Current Skool format: postTrees[].post.metadata.{title,content,upvotes,comments}
                for tree in post_trees:
                    raw = tree.get('post', {}) or {}
                    post_id = raw.get('id', '')
                    if not post_id or post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    meta = raw.get('metadata', {}) or {}
                    user = raw.get('user', {}) or {}
                    slug = raw.get('name', '')
                    label_id = raw.get('labelId', '') or meta.get('labelId', '')
                    first_name = user.get('firstName', '')
                    last_name = user.get('lastName', '')
                    author_name = f"{first_name} {last_name}".strip() or user.get('name', '')
                    comment_count = meta.get('comments', 0) or 0

                    posts.append({
                        'id': post_id,
                        'title': meta.get('title', '') or '',
                        'content': meta.get('content', '') or '',
                        'authorName': author_name,
                        'author': {'name': user.get('name', ''), 'username': user.get('name', '')},
                        'url': f"https://www.skool.com/{community}/{slug}" if slug else f"https://www.skool.com/{community}/{post_id}",
                        'postUrl': f"https://www.skool.com/{community}/{slug}" if slug else f"https://www.skool.com/{community}/{post_id}",
                        'likesCount': meta.get('upvotes', 0) or 0,
                        'commentsCount': comment_count,
                        'commentCount': comment_count,
                        'createdAt': raw.get('createdAt', ''),
                        'categoryName': labels.get(label_id, ''),
                        'categoryId': label_id,
                        'groupId': group_id,
                    })

                print(f"    Found {len(post_trees)} posts ({len(posts)} total unique)")

            elif post_list:
                # Legacy format fallback: pageProps.posts[]
                for post in post_list:
                    post_id = post.get('id') or post.get('postId')
                    if post_id and post_id not in seen_ids:
                        seen_ids.add(post_id)
                        author = post.get('author', {}) or {}
                        author_name = post.get('authorName') or author.get('name', '')
                        comment_count = post.get('commentsCount', post.get('commentCount', 0)) or 0
                        posts.append({
                            'id': post_id,
                            'title': post.get('title', ''),
                            'content': post.get('content', '') or post.get('body', ''),
                            'authorName': author_name,
                            'author': author,
                            'url': post.get('url') or post.get('postUrl') or f"https://www.skool.com/{community}/{post_id}",
                            'postUrl': post.get('url') or post.get('postUrl') or f"https://www.skool.com/{community}/{post_id}",
                            'likesCount': post.get('likesCount', 0),
                            'commentsCount': comment_count,
                            'commentCount': comment_count,
                            'createdAt': post.get('createdAt', ''),
                            'categoryName': post.get('categoryName', ''),
                            'groupId': group_id,
                        })

                print(f"    Found {len(post_list)} posts ({len(posts)} total unique)")

            else:
                print(f"    No posts found in pageProps")

        if page_num < max_pages:
            await asyncio.sleep(5)

    return posts


def _parse_comment(raw: dict, post_id: str, parent_id: str = "") -> dict:
    post_data = raw.get('post', raw) or {}
    meta = post_data.get('metadata', {}) or {}
    user = post_data.get('user', {}) or {}
    first_name = user.get('firstName', '')
    last_name = user.get('lastName', '')
    author_name = f"{first_name} {last_name}".strip() or user.get('name', '')
    return {
        'id': post_data.get('id', ''),
        'postId': post_id,
        'parentId': parent_id,
        'content': meta.get('content', '') or post_data.get('content', '') or post_data.get('body', ''),
        'authorName': author_name,
        'authorId': user.get('id', ''),
        'authorHandle': user.get('name', ''),
        'createdAt': post_data.get('createdAt', ''),
        'likes': meta.get('upvotes', 0),
    }


async def fetch_comments_for_post_with_page(page, post: dict) -> list:
    """Fetch comments for one post through the authenticated browser context."""
    post_id = str(post.get('id') or post.get('postId') or '')
    group_id = post.get('groupId', '')
    if not post_id or not group_id:
        return []

    all_comments = []
    cursor = None
    while True:
        url = f"https://api2.skool.com/posts/{post_id}/comments?group-id={group_id}&limit=20"
        if cursor:
            url += f"&last={cursor}"

        result = await page.evaluate(
            """async (url) => {
                const response = await fetch(url, {
                    method: "GET",
                    headers: { "accept": "application/json" },
                    credentials: "include"
                });
                if (!response.ok) return { error: response.status };
                return await response.json();
            }""",
            url,
        )

        if isinstance(result, dict) and result.get('error'):
            print(f"    Comment fetch failed for {post_id}: HTTP {result.get('error')}")
            break

        post_tree = (result or {}).get('post_tree', {}) or {}
        children = post_tree.get('children', []) or []
        if not children:
            break

        for child in children:
            comment = _parse_comment(child, post_id)
            if comment.get('id'):
                all_comments.append(comment)
            for reply in child.get('children', []) or []:
                reply_comment = _parse_comment(reply, post_id, parent_id=comment.get('id', ''))
                if reply_comment.get('id'):
                    all_comments.append(reply_comment)

        next_cursor = (result or {}).get('last')
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        await asyncio.sleep(COMMENT_PAGE_DELAY_SECONDS)

    return all_comments


async def fetch_comments_for_posts_with_page(page, posts: list) -> dict:
    comments_by_post = {}
    for post in posts:
        post_id = str(post.get('id') or post.get('postId') or '')
        if not post_id:
            continue
        comments = await fetch_comments_for_post_with_page(page, post)
        comments_by_post[post_id] = {"post": post, "comments": comments}
        print(f"    Comments for {post_id}: {len(comments)}")
    return comments_by_post


def update_comment_state(comment_state: dict, posts: list, comments_by_post: dict):
    seen = {str(i) for i in comment_state.get("seen_ids", [])}
    counts = comment_state.get("post_comment_counts", {}) or {}
    for post in posts:
        post_id = str(post.get('id') or post.get('postId') or '')
        if post_id:
            counts[post_id] = _post_comment_count(post)
    for payload in comments_by_post.values():
        for comment in payload.get("comments", []):
            comment_id = str(comment.get("id") or "")
            if comment_id:
                seen.add(comment_id)
    comment_state["seen_ids"] = list(seen)
    comment_state["post_comment_counts"] = counts


async def scrape_recent_posts(community: str, max_pages: int = 2,
                               headless: bool = True) -> list:
    """Scrape recent posts (standalone browser)."""
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
    path = STATE_DIR / f"{state_type}_{community}.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}


def save_state(state_type: str, community: str, state: dict):
    path = STATE_DIR / f"{state_type}_{community}.json"
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def filter_new_ids(items: list, state: dict, id_key: str = "handle") -> list:
    seen = set(state.get("seen_ids", []))
    new_items = []
    for item in items:
        item_id = item.get(id_key, "").lower() if id_key == "handle" else str(item.get(id_key, ""))
        if item_id and item_id not in seen:
            new_items.append(item)
    return new_items


def add_to_state(state: dict, ids: list):
    seen = set(state.get("seen_ids", []))
    seen.update(ids)
    state["seen_ids"] = list(seen)


def load_enrichment_cache(community: str) -> dict:
    """Load cached enrichment data keyed by member handle."""
    path = STATE_DIR / f"enrichment_cache_{community}.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_enrichment_cache(community: str, cache: dict):
    """Save enrichment cache atomically."""
    path = STATE_DIR / f"enrichment_cache_{community}.json"
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ============================================================================
# EVENT LOGGING — daily JSONL for digest consumption
# ============================================================================

def log_event(community: str, event_type: str, data: dict):
    """Append event to daily JSONL log. Read by the nightly digest."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = EVENTS_DIR / f"{community}_{today}.jsonl"

    event = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "community": community,
        "data": data,
    }

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ============================================================================
# NOTIFICATIONS — formatted with clickable links
# ============================================================================

def send_ntfy_notification(title: str, body: str, notify_type: str = "info",
                           tag: str = None, dry_run: bool = False,
                           ntfy_url: str = None) -> bool:
    """Send a direct ntfy push when an ntfy topic URL is configured."""
    target_url = (NTFY_URL if ntfy_url is None else ntfy_url).strip()
    if not target_url:
        return False

    priority = "high" if notify_type in {"warning", "failure"} else "default"
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tag or "skool",
    }
    match = re.search(r"https?://\S+", body)
    if match:
        headers["Click"] = match.group(0).rstrip(").,")

    if dry_run:
        print(f"\n  [DRY RUN] ntfy notification ({notify_type}):")
        print(f"    Title: {title}")
        print(f"    Body: {body[:300]}...")
        print(f"    URL: {target_url}")
        return True

    try:
        resp = requests.post(
            target_url,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        if 200 <= resp.status_code < 300:
            print(f"  ntfy sent: {title}")
            return True
        print(f"  ntfy failed ({resp.status_code}): {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"  ntfy error: {e}")
    return False


def send_apprise_notification(title: str, body: str, notify_type: str = "info",
                               tag: str = None, dry_run: bool = False,
                               ntfy_url: str = None,
                               fallback_to_apprise: bool = True) -> bool:
    if send_ntfy_notification(
        title,
        body,
        notify_type=notify_type,
        tag=tag,
        dry_run=dry_run,
        ntfy_url=ntfy_url,
    ):
        return True

    if ntfy_url is not None and not fallback_to_apprise:
        print("  WARNING: ntfy topic unavailable and Apprise fallback disabled")
        return False

    if dry_run:
        print(f"\n  [DRY RUN] Notification ({notify_type}):")
        print(f"    Title: {title}")
        print(f"    Body: {body[:300]}...")
        return True

    urls = build_apprise_urls()
    if not urls:
        print("  WARNING: No Apprise notification URLs configured")
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
        resp = requests.post(f"{APPRISE_URL}/notify", json=payload, timeout=30)
        if resp.status_code == 200:
            print(f"  Notification sent: {title}")
            return True
        else:
            print(f"  Notification failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        print(f"  Notification error: {e}")
        return False


def format_member_notification(member: dict, enrichment: dict) -> tuple:
    """Format a single enriched ICP member into notification title + body with links."""
    tier = member.get("tier", "?")
    score = member.get("icp_score", 0)
    name = member.get("name", "Unknown")

    company = enrichment.get("company", "")
    desc = (enrichment.get("company_description", "") or "")[:140]
    services = ", ".join(enrichment.get("services", []))
    industries = ", ".join(enrichment.get("industries", []))
    city = enrichment.get("city", "")
    country = enrichment.get("country", "")
    location = f"{city}, {country}".strip(", ") if (city or country) else ""
    linkedin = enrichment.get("linkedin") or enrichment.get("linkedin_url", "")
    website = enrichment.get("website", "")

    title = f"NEW ICP [{tier}]: {name} (Score: {score})"

    lines = []
    # Company + what they do
    if company and desc:
        lines.append(f"{company} — {desc}")
    elif company:
        lines.append(company)
    elif desc:
        lines.append(desc)
    elif member.get("bio"):
        lines.append(member["bio"][:140])

    # Services / industries
    if services:
        lines.append(f"Services: {services}")
    if industries and not services:
        lines.append(f"Industry: {industries}")

    # Location
    if location:
        lines.append(f"Location: {location}")

    # Why flagged
    reasons = ", ".join(member.get("match_reasons", []))
    if reasons:
        lines.append(f"Signals: {reasons}")

    lines.append("")
    lines.append(f"Skool: {member.get('profileUrl', '')}")
    if linkedin:
        lines.append(f"LinkedIn: {linkedin}")
    if website:
        lines.append(f"Website: {website}")

    body = "\n".join(lines)
    return title, body


def format_member_join_notification(members: list) -> tuple:
    """Format newly joined Skool members without enrichment or ICP scoring."""
    count = len(members)
    title = f"Skool: {count} new member{'s' if count != 1 else ''} joined"
    lines = []
    limit = 10

    for member in members[:limit]:
        name = member.get("name") or member.get("handle") or "Unknown"
        handle = member.get("handle", "")
        lines.append(name)
        if member.get("location"):
            lines.append(f"    Location: {member['location']}")
        bio = (member.get("bio") or "").replace("\n", " ").strip()
        if bio:
            lines.append(f"    {bio[:220]}")
        profile_url = member.get("profileUrl") or (f"https://www.skool.com/@{handle}" if handle else "")
        if profile_url:
            lines.append(f"    Skool: {profile_url}")
        lines.append("")

    overflow = count - limit
    if overflow > 0:
        lines.append(f"...and {overflow} more new members.")

    return title, "\n".join(lines)


def format_churn_notification(member_data: dict) -> tuple:
    """Format a paid ICP cancellation notification with enrichment links."""
    name = member_data.get("name", "Unknown")
    handle = member_data.get("handle", "")
    tier = member_data.get("tier", "unknown")
    score = member_data.get("icp_score", 0)
    enrichment = member_data.get("enrichment", {})
    bio = member_data.get("bio", "")

    title = f"CANCELLED [{tier}]: {name} — $77/mo (Score: {score})"

    lines = []
    company = enrichment.get("company", "")
    desc = (enrichment.get("company_description", "") or "")[:140]
    services = ", ".join(enrichment.get("services", []))
    city = enrichment.get("city", "")
    country = enrichment.get("country", "")
    location = f"{city}, {country}".strip(", ") if (city or country) else ""
    linkedin = enrichment.get("linkedin") or enrichment.get("linkedin_url", "")
    website = enrichment.get("website", "")

    if company and desc:
        lines.append(f"{company} — {desc}")
    elif company:
        lines.append(company)
    elif bio:
        lines.append(bio[:140])

    if services:
        lines.append(f"Services: {services}")
    if location:
        lines.append(f"Location: {location}")

    joined = member_data.get("joinedAt", "")
    if joined:
        lines.append(f"Joined: {joined[:10]}")

    reasons = ", ".join(member_data.get("match_reasons", []))
    if reasons:
        lines.append(f"Signals: {reasons}")

    lines.append("")
    lines.append(f"Skool: https://www.skool.com/@{handle}")
    if linkedin:
        lines.append(f"LinkedIn: {linkedin}")
    if website:
        lines.append(f"Website: {website}")

    body = "\n".join(lines)
    return title, body


def format_wins_notification(wins: list) -> tuple:
    count = len(wins)
    title = f"Skool: {count} financial win{'s' if count != 1 else ''} posted"
    lines = []
    for w in wins:
        lines.append(f"{w['money_pattern'].upper()} — {w['author_name']}")
        if w.get('title'):
            lines.append(f'    "{w["title"][:100]}"')
        lines.append(f"    Post: {w.get('post_url', '')}")
        lines.append(f"    {w['likes_count']} likes | {w['comments_count']} comments")
        lines.append("")
    return title, "\n".join(lines)


def _find_cached_author_context(post: dict, enrichment_cache: dict) -> str:
    author_name = (post.get("authorName") or "").strip().lower()
    author_handle = (post.get("authorHandle") or post.get("author", {}).get("username") or "").strip().lower()
    for handle, cached in (enrichment_cache or {}).items():
        cached_name = (cached.get("name") or "").strip().lower()
        if (author_handle and author_handle == str(handle).lower()) or (author_name and author_name == cached_name):
            tier = cached.get("tier") or cached.get("icp_tier")
            score = cached.get("icp_score")
            if tier and score is not None:
                return f"Tier {tier} / ICP {score}"
            if tier:
                return f"Tier {tier}"
    return ""


def format_intro_notification(intro_posts: list, enrichment_cache: dict | None = None) -> tuple:
    count = len(intro_posts)
    title = f"Skool: {count} new intro post{'s' if count != 1 else ''}"
    lines = []
    for post in intro_posts[:10]:
        author = post.get("authorName") or "Unknown"
        context = _find_cached_author_context(post, enrichment_cache or {})
        header = f"{author}"
        if context:
            header += f" ({context})"
        lines.append(header)
        if post.get("title"):
            lines.append(f'    "{post["title"][:120]}"')
        excerpt = (post.get("content") or "").replace("\n", " ").strip()
        if excerpt:
            lines.append(f"    {excerpt[:220]}")
        category = post.get("categoryName") or post.get("category") or ""
        if category:
            lines.append(f"    Category: {category}")
        lines.append(f"    Post: {post.get('url') or post.get('postUrl', '')}")
        lines.append("")
    return title, "\n".join(lines)


def format_all_new_posts_notification(posts: list) -> tuple:
    count = len(posts)
    title = f"Skool: {count} new post{'s' if count != 1 else ''}"
    lines = []
    limit = max(1, ALL_NEW_POSTS_NOTIFY_LIMIT)

    for post in posts[:limit]:
        author = (
            post.get("authorName")
            or post.get("author", {}).get("name")
            or post.get("author", {}).get("username")
            or "Unknown"
        )
        lines.append(author)

        post_title = (post.get("title") or "").strip()
        if post_title:
            lines.append(f'    "{post_title[:140]}"')

        category = post.get("categoryName") or post.get("category") or ""
        if category:
            lines.append(f"    Category: {category}")

        excerpt = (post.get("content") or "").replace("\n", " ").strip()
        if excerpt:
            lines.append(f"    {excerpt[:220]}")

        post_url = post.get("url") or post.get("postUrl") or ""
        if post_url:
            lines.append(f"    Post: {post_url}")
        lines.append("")

    overflow = count - limit
    if overflow > 0:
        lines.append(f"...and {overflow} more new posts.")

    return title, "\n".join(lines)


def format_real_estate_us_notification(members: list) -> tuple:
    count = len(members)
    title = f"Skool: {count} US real estate member{'s' if count != 1 else ''} joined"
    lines = []
    for member in members[:10]:
        name = member.get("name") or member.get("handle") or "Unknown"
        tier = member.get("tier")
        score = member.get("icp_score")
        header = name
        if tier and score is not None:
            header += f" (Tier {tier}, ICP {score})"
        lines.append(header)
        if member.get("location"):
            lines.append(f"    Location: {member['location']}")
        if member.get("real_estate_signal"):
            lines.append(f"    Real estate signal: {member['real_estate_signal']}")
        if member.get("us_signal"):
            lines.append(f"    US signal: {member['us_signal']}")
        bio = (member.get("bio") or "").replace("\n", " ").strip()
        if bio:
            lines.append(f"    {bio[:220]}")
        lines.append(f"    Skool: {member.get('profileUrl', '')}")
        lines.append("")
    return title, "\n".join(lines)


def format_mentions_notification(mentions: list) -> tuple:
    count = len(mentions)
    title = f"Skool: {count} meaningful mention{'s' if count != 1 else ''}"
    lines = []
    for m in mentions:
        location = m.get("location", "post")
        lines.append(f"[{m.get('type', 'mention')} / {location}] {m['author_name']}")
        if m.get("post_title"):
            lines.append(f'    Post title: "{m["post_title"][:90]}"')
        preview = m.get("preview") or _short_preview(m.get("context", ""))
        if preview:
            lines.append(f'    Preview: "{preview}"')
        lines.append(f"    Post: {m.get('post_url', '')}")
        lines.append("")
    return title, "\n".join(lines)


def format_antigravity_notification(mentions: list) -> tuple:
    count = len(mentions)
    title = f"Skool: {count} anti-gravity mention{'s' if count != 1 else ''}!"
    lines = []
    for m in mentions:
        lines.append(f"{m['author_name']} mentioned \"{m['keyword']}\"")
        if m.get('post_title'):
            lines.append(f'    Post: "{m["post_title"][:80]}"')
        lines.append(f"    {m.get('post_url', '')}")
        lines.append("")
    return title, "\n".join(lines)


# ============================================================================
# CHURN DETECTION — removed, replaced by Cancelling tab scraper above
# ============================================================================
# Old approach diffed active member handles. New approach scrapes the
# Cancelling tab directly at /-/members?tab=cancelling which shows:
# - "Cancelled (churns in X days)" = paid cancellation → ALERT
# - "Trial cancelled (removing in X day)" = trial → skip
# See: scrape_cancelling_with_page() and detect_new_cancellations()


# ============================================================================
# TEST MODE — fire all notification types with realistic fake data
# ============================================================================

def run_test_notifications(dry_run: bool = False):
    """
    Send one test notification for each type. No scraping — tests the full
    format → send pipeline with realistic data.

    Usage: python skool_apprise_monitor.py --test
           python skool_apprise_monitor.py --test --dry-run
    """
    print(f"\n{'='*60}")
    print("TEST MODE — Sending all notification types")
    print(f"{'='*60}")

    sent = 0
    total = sum([
        ALERT_MEMBER_JOINS,
        ALERT_ICP_MEMBERS,
        ALERT_CHURN,
        ALERT_WINS,
        ALERT_MENTIONS,
        ALERT_INTRO_POSTS,
        NOTIFY_ALL_NEW_POSTS,
        ALERT_REAL_ESTATE_US,
        ALERT_ANTIGRAVITY,
    ])

    # --- 1. New Member Join ---
    print("\n[1/9] New Member Join")
    test_member = {
        "name": "Sarah Mitchell",
        "handle": "sarah-mitchell-test",
        "bio": "CEO at GrowthStack Digital. Helping local businesses scale with AI automation and GoHighLevel. Former agency owner, now building SaaS.",
        "profileUrl": "https://www.skool.com/@sarah-mitchell-test",
        "tier": "A",
        "icp_score": 72,
        "match_reasons": ["Position: ceo", "Industry: local business", "Pain: scale"],
    }
    title, body = format_member_join_notification([test_member])
    if ALERT_MEMBER_JOINS and send_apprise_notification(title, body, notify_type="info", tag="member", dry_run=dry_run):
        sent += 1

    # --- 2. New ICP Member (Tier A) ---
    print("\n[2/9] New ICP Member (Tier A)")
    test_enrichment = {
        "company": "GrowthStack Digital",
        "company_description": "AI-powered marketing automation for local service businesses. Specializes in GoHighLevel implementations.",
        "services": ["GoHighLevel", "AI Chatbots", "Marketing Automation"],
        "industries": ["Local Services", "Digital Marketing"],
        "city": "Austin",
        "country": "USA",
        "linkedin_url": "https://linkedin.com/in/sarahmitchell-test",
        "website": "https://growthstackdigital.com",
    }
    title, body = format_member_notification(test_member, test_enrichment)
    if ALERT_ICP_MEMBERS and send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
        sent += 1

    # --- 3. ICP Churn (Tier A cancelled) ---
    print("\n[3/9] ICP Churn (Tier A Cancellation)")
    test_churn = {
        "name": "Marcus Rivera",
        "handle": "marcus-rivera-test",
        "bio": "Owner of Rivera Home Services. 15 trucks, $2M revenue. Looking for better lead gen.",
        "tier": "A",
        "icp_score": 65,
        "match_reasons": ["Position: owner", "Industry: home services", "Revenue: $2m"],
        "joinedAt": "2025-11-15T00:00:00Z",
        "enrichment": {
            "company": "Rivera Home Services",
            "company_description": "Full-service HVAC and plumbing company serving the greater Phoenix area.",
            "services": ["HVAC", "Plumbing", "Emergency Repairs"],
            "city": "Phoenix",
            "country": "USA",
            "linkedin_url": "https://linkedin.com/in/marcusrivera-test",
            "website": "https://riverahomeservices.com",
        },
    }
    title, body = format_churn_notification(test_churn)
    if ALERT_CHURN and send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
        sent += 1

    # --- 4. Financial Win ---
    print("\n[4/9] Financial Win")
    test_wins = [{
        "money_pattern": "$15,000 deal",
        "author_name": "Jake Thompson",
        "author_handle": "jake-thompson-test",
        "title": "Just closed my biggest client ever — $15,000/month retainer for AI automation!",
        "post_url": "https://www.skool.com/aiautomationsbyjack/test-post-123",
        "likes_count": 47,
        "comments_count": 23,
    }]
    title, body = format_wins_notification(test_wins)
    if ALERT_WINS and send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
        sent += 1

    # --- 5. Meaningful @florian Mention ---
    print("\n[5/9] Meaningful @florian Mention")
    test_mentions = [{
        "type": "@mention",
        "author_name": "David Park",
        "author_handle": "david-park-test",
        "post_title": "Question about appointment booking agents",
        "context": "...has anyone tried building a GoHighLevel integration with AI agents? @florian I saw your post about automation workflows — would love to hear how you approached the appointment booking pipeline...",
        "preview": "has anyone tried building a GoH...",
        "post_url": "https://www.skool.com/aiautomationsbyjack/test-mention-456",
        "meaningful": True,
    }]
    title, body = format_mentions_notification(test_mentions)
    if ALERT_MENTIONS and send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
        sent += 1

    # --- 6. New Intro Post ---
    print("\n[6/9] New Intro Post")
    test_intro = [{
        "authorName": "Angela Morris",
        "title": "Excited to join",
        "content": "I run a small operations consultancy in Texas and I am looking forward to learning more about AI systems.",
        "categoryName": "Introductions",
        "url": "https://www.skool.com/aiautomationsbyjack/test-intro-001",
    }]
    title, body = format_intro_notification(test_intro, {})
    if ALERT_INTRO_POSTS and send_apprise_notification(title, body, notify_type="info", tag="intro", dry_run=dry_run):
        sent += 1

    # --- 7. All New Posts ---
    print("\n[7/9] All New Posts")
    test_posts = [
        {
            "authorName": "Angela Morris",
            "title": "Excited to join",
            "content": "I run a small operations consultancy in Texas and I am looking forward to learning more about AI systems.",
            "categoryName": "Introductions",
            "postUrl": "https://www.skool.com/aiautomationsbyjack/test-intro-001",
        },
        {
            "authorName": "Noah Patel",
            "title": "Need feedback on my outbound workflow",
            "content": "I am testing a new appointment booking automation and would love a second set of eyes.",
            "categoryName": "General",
            "postUrl": "https://www.skool.com/aiautomationsbyjack/test-post-002",
        },
    ]
    title, body = format_all_new_posts_notification(test_posts)
    if NOTIFY_ALL_NEW_POSTS and send_apprise_notification(
        title,
        body,
        notify_type="info",
        tag="new-post",
        dry_run=dry_run,
        ntfy_url=NTFY_ALL_POSTS_URL,
        fallback_to_apprise=False,
    ):
        sent += 1

    # --- 8. US Real Estate Member ---
    print("\n[8/9] US Real Estate Member")
    test_re_member = [{
        "name": "Carlos Bennett",
        "handle": "carlos-bennett-test",
        "bio": "Real estate investor and property manager focused on multifamily deals.",
        "location": "Austin, TX",
        "profileUrl": "https://www.skool.com/@carlos-bennett-test",
        "tier": "B",
        "icp_score": 45,
        "real_estate_signal": "real estate",
        "us_signal": "TX",
    }]
    title, body = format_real_estate_us_notification(test_re_member)
    if ALERT_REAL_ESTATE_US and send_apprise_notification(title, body, notify_type="info", tag="real-estate", dry_run=dry_run):
        sent += 1

    # --- 9. Anti-Gravity Brand Mention ---
    print("\n[9/9] Anti-Gravity Brand Mention")
    test_ag = [{
        "author_name": "Lisa Chen",
        "author_handle": "lisa-chen-test",
        "keyword": "anti-gravity",
        "post_title": "Tools and resources that actually helped me scale",
        "post_url": "https://www.skool.com/aiautomationsbyjack/test-ag-789",
    }]
    title, body = format_antigravity_notification(test_ag)
    if ALERT_ANTIGRAVITY and send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
        sent += 1

    print(f"\n{'='*60}")
    print(f"TEST COMPLETE: {sent}/{total} notifications sent")
    print(f"{'='*60}")
    return sent


# ============================================================================
# MAIN MONITOR
# ============================================================================

async def run_monitor(community: str, headless: bool = True,
                       dry_run: bool = False, init: bool = False,
                       members_only: bool = False, posts_only: bool = False,
                       session: BrowserSession = None):
    """
    Run the unified Skool monitor (single cycle).

    1. Scrape members → detect new ICPs → enrich → notify with links
    2. Detect churn (cancelled members) → alert for ICP qualified
    3. Scrape posts → detect wins + mentions + antigravity → notify
    """
    print(f"\n{'='*60}")
    print(f"SKOOL MONITOR v2 — {community}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = {
        "member_joins": 0, "new_members": 0, "enriched": 0, "churned": 0,
        "wins": 0, "mentions": 0, "antigravity": 0, "intros": 0,
        "real_estate_us": 0, "all_new_posts": 0,
        "notifications_sent": 0,
    }

    enrichment_cache = load_enrichment_cache(community)

    # --- MEMBER MONITORING ---
    if not posts_only:
        print(f"\n[1/3] MEMBER MONITORING")
        member_state = load_state("members", community)

        try:
            if session and session.is_alive:
                scraped = await scrape_members_with_page(session.page, community, max_pages=1)
            else:
                scraped = await scrape_member_list(community, max_pages=2, headless=headless)
            print(f"  Scraped {len(scraped)} members")

            current_handles = {m["handle"].lower() for m in scraped if m.get("handle")}

            if init and not member_state.get("seen_ids"):
                # First run: initialize state, no notifications
                add_to_state(member_state, list(current_handles))
                save_state("members", community, member_state)
                print(f"  Initialized state with {len(current_handles)} members.")
            else:
                # --- NEW MEMBER DETECTION ---
                new_members = filter_new_ids(scraped, member_state, id_key="handle")
                print(f"\n  New members: {len(new_members)}")

                if new_members:
                    # Score all new members first (quick keyword scoring)
                    scored = [quick_score_member(m) for m in new_members]
                    qualified = [m for m in scored if m.get("tier") in ("A", "B")]

                    tier_counts = {}
                    for m in scored:
                        t = m.get("tier", "?")
                        tier_counts[t] = tier_counts.get(t, 0) + 1
                    print(f"  Tiers: {tier_counts}")

                    results["member_joins"] = len(scored)
                    if ALERT_MEMBER_JOINS:
                        title, body = format_member_join_notification(scored)
                        if send_apprise_notification(title, body, notify_type="info", tag="member", dry_run=dry_run):
                            results["notifications_sent"] += 1
                        print(f"  Member join alerts: {len(scored)}")
                    else:
                        print(f"  Member join alerts disabled: {len(scored)} new member(s)")
                    for m in scored:
                        log_event(community, "member_join", {
                            "handle": m.get("handle", ""),
                            "name": m.get("name", ""),
                            "profileUrl": m.get("profileUrl", ""),
                            "joinedAt": m.get("joinedAt", ""),
                        })

                    real_estate_us_members = detect_real_estate_us_members(scored)
                    if real_estate_us_members:
                        results["real_estate_us"] = len(real_estate_us_members)
                        if ALERT_REAL_ESTATE_US:
                            title, body = format_real_estate_us_notification(real_estate_us_members)
                            if send_apprise_notification(title, body, notify_type="info", tag="real-estate", dry_run=dry_run):
                                results["notifications_sent"] += 1
                            print(f"  US real estate member alerts: {len(real_estate_us_members)}")
                        else:
                            print(f"  US real estate detected, alert disabled: {len(real_estate_us_members)}")
                        for m in real_estate_us_members:
                            log_event(community, "real_estate_us_member", m)

                    if ALERT_ICP_MEMBERS:
                        # Enrich qualified members BEFORE notifying
                        for m in qualified:
                            handle = m["handle"].lower()
                            enrichment = enrich_member(m)
                            results["enriched"] += 1

                            # Re-score with enrichment data for better accuracy
                            m = quick_score_member(m, enrichment)

                            # Cache enrichment data (for churn detection + digest)
                            enrichment_cache[handle] = {
                                "name": m.get("name", ""),
                                "handle": handle,
                                "tier": m.get("tier", "D"),
                                "icp_score": m.get("icp_score", 0),
                                "match_reasons": m.get("match_reasons", []),
                                "enrichment": enrichment,
                                "cached_at": datetime.now(timezone.utc).isoformat(),
                            }

                            # Only notify if still qualified after re-scoring with enrichment
                            if m.get("tier") in ("A", "B"):
                                results["new_members"] += 1
                                title, body = format_member_notification(m, enrichment)
                                if send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
                                    results["notifications_sent"] += 1

                                # Log event for daily digest
                                log_event(community, "new_member", {
                                    "handle": handle,
                                    "name": m.get("name", ""),
                                    "tier": m.get("tier"),
                                    "icp_score": m.get("icp_score"),
                                    "match_reasons": m.get("match_reasons", []),
                                    "enrichment": enrichment,
                                })
                    elif qualified:
                        print(f"  ICP alerts disabled, skipped enrichment for {len(qualified)} qualified member(s)")

                    # Also cache basic data for non-qualified members (for churn tracking)
                    for m in scored:
                        handle = m["handle"].lower()
                        if handle not in enrichment_cache:
                            enrichment_cache[handle] = {
                                "name": m.get("name", ""),
                                "handle": handle,
                                "tier": m.get("tier", "D"),
                                "icp_score": m.get("icp_score", 0),
                                "cached_at": datetime.now(timezone.utc).isoformat(),
                            }

                    save_enrichment_cache(community, enrichment_cache)

                # Update member state with ALL current handles
                add_to_state(member_state, list(current_handles))

            save_state("members", community, member_state)

        except Exception as e:
            print(f"  ERROR in member monitoring: {e}")
            import traceback
            traceback.print_exc()

    # --- CANCELLATION MONITORING (scrape Cancelling tab) ---
    if not posts_only:
        print(f"\n[2/3] CANCELLATION MONITORING (Cancelling tab)")
        try:
            if session and session.is_alive:
                cancelling = await scrape_cancelling_with_page(session.page, community, max_pages=2)
            else:
                # Standalone mode — need a browser
                tmp_session = BrowserSession(headless=headless)
                await tmp_session.start()
                try:
                    cancelling = await scrape_cancelling_with_page(tmp_session.page, community, max_pages=2)
                finally:
                    await tmp_session.stop()

            print(f"  Total cancelling: {len(cancelling)}")
            trial_count = sum(1 for m in cancelling if m.get("is_trial"))
            paid_count = len(cancelling) - trial_count
            print(f"  Breakdown: {paid_count} paid, {trial_count} trial")

            if not init:
                new_cancellations = detect_new_cancellations(cancelling, community, enrichment_cache)
                if new_cancellations:
                    print(f"  NEW paid cancellations to evaluate: {len(new_cancellations)}")
                    notified = 0
                    if not ALERT_CHURN:
                        print(f"  Churn alerts disabled; marking {len(new_cancellations)} cancellation(s) seen")

                    for cancel in new_cancellations:
                        if not ALERT_CHURN:
                            log_event(community, "cancellation", cancel)
                            continue

                        handle = cancel["handle"]

                        # Enrich cancelling member (Perplexity + Tavily LinkedIn)
                        if not cancel.get("enrichment") or not cancel["enrichment"].get("company"):
                            enrichment = enrich_member(cancel)
                            cancel["enrichment"] = enrichment
                        else:
                            enrichment = cancel["enrichment"]

                        # Re-score WITH enrichment data now available
                        cancel = quick_score_member(cancel, enrichment)

                        # ICP FILTER: only notify for Tier A or B members
                        tier = cancel.get("tier", "D")
                        if tier not in ("A", "B"):
                            print(f"    Skip (not ICP, tier {tier}): {cancel['name']}")
                            log_event(community, "cancellation", cancel)  # Log for digest
                            continue

                        # Update enrichment cache with full data
                        enrichment_cache[handle] = {
                            "name": cancel.get("name", ""),
                            "handle": handle,
                            "tier": tier,
                            "icp_score": cancel.get("icp_score", 0),
                            "enrichment": enrichment,
                            "cached_at": datetime.now(timezone.utc).isoformat(),
                        }

                        title, body = format_churn_notification(cancel)
                        # Use "info" — silent visual popup, no sound
                        if send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
                            notified += 1
                            results["notifications_sent"] += 1
                        log_event(community, "cancellation", cancel)

                    results["churned"] = notified
                    if notified:
                        print(f"  ICP cancellation alerts sent: {notified}")
                    save_enrichment_cache(community, enrichment_cache)
                else:
                    print(f"  No new paid cancellations")
            else:
                # Init mode (--init flag): handled in detect_new_cancellations on first run
                print(f"  Cancelling tab: {len(cancelling)} members (init mode, no alerts)")

        except Exception as e:
            print(f"  ERROR in cancellation monitoring: {e}")
            import traceback
            traceback.print_exc()

    # --- POST MONITORING (wins + mentions + antigravity) ---
    if not members_only:
        print(f"\n[3/3] POST MONITORING")
        post_state = load_state("posts", community)
        intro_state = load_state("intro_posts", community)
        comment_state = load_state("comments", community)

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
                intro_ids = [str(p.get("id", "")) for p in posts if p.get("id") and is_intro_post(p)]
                add_to_state(intro_state, intro_ids)
                save_state("intro_posts", community, intro_state)
                comment_candidates = select_posts_for_comment_scan(posts, posts, comment_state)
                comments_by_post = {}
                if comment_candidates:
                    active_page = session.page if session and session.is_alive else None
                    if active_page:
                        comments_by_post = await fetch_comments_for_posts_with_page(active_page, comment_candidates)
                update_comment_state(comment_state, posts, comments_by_post)
                save_state("comments", community, comment_state)
                print(f"  Initialized state with {len(post_ids)} posts.")
            else:
                intro_posts = [p for p in posts if is_intro_post(p)]
                new_intro_posts = filter_new_ids(intro_posts, intro_state, id_key="id")
                if new_intro_posts:
                    results["intros"] = len(new_intro_posts)
                    if ALERT_INTRO_POSTS:
                        title, body = format_intro_notification(new_intro_posts, enrichment_cache)
                        if send_apprise_notification(title, body, notify_type="info", tag="intro", dry_run=dry_run):
                            results["notifications_sent"] += 1
                        print(f"  New intro posts: {len(new_intro_posts)}")
                    else:
                        print(f"  Intro post alerts disabled: {len(new_intro_posts)}")
                    for p in new_intro_posts:
                        log_event(community, "intro_post", p)

                if new_posts:
                    if NOTIFY_ALL_NEW_POSTS:
                        results["all_new_posts"] = len(new_posts)
                        title, body = format_all_new_posts_notification(new_posts)
                        if send_apprise_notification(
                            title,
                            body,
                            notify_type="info",
                            tag="new-post",
                            dry_run=dry_run,
                            ntfy_url=NTFY_ALL_POSTS_URL,
                            fallback_to_apprise=False,
                        ):
                            results["notifications_sent"] += 1
                        print(f"  All-new-post alerts: {len(new_posts)}")
                        for p in new_posts:
                            log_event(community, "new_post", p)

                    if ALERT_WINS:
                        # Financial wins
                        wins = detect_wins(new_posts)
                        if wins:
                            results["wins"] = len(wins)
                            title, body = format_wins_notification(wins)
                            if send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
                                results["notifications_sent"] += 1
                            print(f"  Financial wins: {len(wins)}")
                            for w in wins:
                                log_event(community, "win", w)

                    if ALERT_ANTIGRAVITY:
                        # Anti-gravity / brand mentions
                        ag_mentions = detect_antigravity_mentions(new_posts)
                        if ag_mentions:
                            results["antigravity"] = len(ag_mentions)
                            title, body = format_antigravity_notification(ag_mentions)
                            if send_apprise_notification(title, body, notify_type="info", dry_run=dry_run):
                                results["notifications_sent"] += 1
                            print(f"  Anti-gravity mentions: {len(ag_mentions)}")
                            for ag in ag_mentions:
                                log_event(community, "antigravity", ag)

                    # @florian mentions in new posts
                    post_mentions = detect_mentions(new_posts) if ALERT_MENTIONS else []
                    if post_mentions:
                        print(f"  Post mentions found: {len(post_mentions)}")
                else:
                    post_mentions = []

                comment_candidates = select_posts_for_comment_scan(posts, new_posts, comment_state)
                comments_by_post = {}
                if comment_candidates:
                    active_page = session.page if session and session.is_alive else None
                    if active_page:
                        print(f"  Scanning comments on {len(comment_candidates)} post(s)")
                        comments_by_post = await fetch_comments_for_posts_with_page(active_page, comment_candidates)
                    else:
                        print("  Comment scan skipped in standalone post scrape without active browser page")

                comment_mentions = detect_comment_mentions(comments_by_post, comment_state) if ALERT_MENTIONS else []
                mentions = post_mentions + comment_mentions
                if mentions:
                    meaningful = [m for m in mentions if m.get("meaningful")]
                    noise = [m for m in mentions if not m.get("meaningful")]

                    if meaningful:
                        results["mentions"] += len(meaningful)
                        title, body = format_mentions_notification(meaningful)
                        if send_apprise_notification(title, body, notify_type="info", tag="mention", dry_run=dry_run):
                            results["notifications_sent"] += 1
                        print(f"  Meaningful mentions: {len(meaningful)}")

                    if noise:
                        print(f"  Filtered noise mentions: {len(noise)} (logged only)")

                    # Log ALL mentions (meaningful and noise) for daily digest
                    for m in mentions:
                        log_event(community, "mention", m)

                # Vectorize new posts to Supabase (non-blocking, graceful degradation)
                if new_posts:
                    vectorize_new_posts(new_posts, community)

                post_ids = [str(p.get("id", "")) for p in posts if p.get("id")]
                add_to_state(post_state, post_ids)
                intro_ids = [str(p.get("id", "")) for p in intro_posts if p.get("id")]
                add_to_state(intro_state, intro_ids)
                update_comment_state(comment_state, posts, comments_by_post)

            save_state("posts", community, post_state)
            save_state("intro_posts", community, intro_state)
            save_state("comments", community, comment_state)

        except Exception as e:
            print(f"  ERROR in post monitoring: {e}")
            import traceback
            traceback.print_exc()

    # --- SUMMARY ---
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Member joins:       {results['member_joins']}")
    print(f"  New ICP members:    {results['new_members']} (enriched: {results['enriched']})")
    print(f"  US real estate:     {results['real_estate_us']}")
    print(f"  Churn (ICP):        {results['churned']}")
    print(f"  Intro posts:        {results['intros']}")
    print(f"  All new posts:      {results['all_new_posts']}")
    print(f"  Financial wins:     {results['wins']}")
    print(f"  Mentions:           {results['mentions']}")
    print(f"  Anti-gravity:       {results['antigravity']}")
    print(f"  Notifications sent: {results['notifications_sent']}")
    print(f"{'='*60}\n")

    return results


# ============================================================================
# DAEMON MODE
# ============================================================================

def _check_and_run_digest(community: str, dry_run: bool = False):
    """
    Check if it's time to send the daily digest (9:30pm EST / 02:30 UTC).

    Runs once per day. Uses a state file to track whether today's digest was sent.
    The digest window is 02:25-02:35 UTC (9:25-9:35pm EST) to handle cycle timing.
    """
    from datetime import timedelta

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    # Check if digest already sent today
    digest_state_path = STATE_DIR / f"digest_sent_{community}.json"
    if digest_state_path.exists():
        try:
            with open(digest_state_path, 'r') as f:
                state = json.load(f)
            if state.get("last_sent") == today_str:
                return  # Already sent today
        except (json.JSONDecodeError, KeyError):
            pass

    # Check if we're in the digest window: 02:25-02:35 UTC (9:25-9:35pm EST)
    hour, minute = now_utc.hour, now_utc.minute
    in_window = (hour == 2 and 25 <= minute <= 35)

    # Also support configurable hour via env var (DIGEST_HOUR_UTC, default 2 = 9pm EST)
    digest_hour = int(os.getenv("DIGEST_HOUR_UTC", "2"))
    if digest_hour != 2:
        in_window = (hour == digest_hour and 25 <= minute <= 35)

    if not in_window:
        return

    print(f"\n  [DIGEST] 9:30pm EST window detected — generating daily digest...")

    try:
        # Import the digest module (in Docker: same /app directory)
        try:
            from skool_daily_digest_v3 import run_digest
        except ImportError:
            # Try from execution/ directory (local development)
            sys.path.insert(0, str(Path(__file__).parent))
            from skool_daily_digest_v3 import run_digest

        email_to = os.getenv("APPRISE_EMAIL_TO", "you@example.com")
        success = run_digest(
            community=community,
            dry_run=dry_run,
            email_to=email_to,
        )

        if success:
            # Mark digest as sent today
            with open(digest_state_path, 'w') as f:
                json.dump({"last_sent": today_str, "sent_at": now_utc.isoformat()}, f)
            print(f"  [DIGEST] Sent successfully. Next digest tomorrow.")
        else:
            print(f"  [DIGEST] No events today or send failed.")

    except Exception as e:
        print(f"  [DIGEST] Error: {e}")
        import traceback
        traceback.print_exc()


async def run_daemon(community: str, interval: int = 180, headless: bool = True,
                      dry_run: bool = False, members_only: bool = False,
                      posts_only: bool = False):
    """Run the monitor in a persistent loop (daemon mode)."""
    print(f"\n{'='*60}")
    print(f"SKOOL MONITOR v2 — DAEMON MODE")
    print(f"Community: {community}")
    print(f"Interval: {interval}s ({interval/60:.1f} min)")
    print(f"Enrichment: {'enabled' if PERPLEXITY_KEY else 'DISABLED (no API key)'}")
    print(f"LinkedIn finder: {'enabled' if TAVILY_KEYS else 'DISABLED (no API keys)'}")
    print(f"Digest: 9:30pm EST daily (02:30 UTC)")
    print(f"Dry run: {dry_run}")
    print(f"{'='*60}\n")

    session = BrowserSession(headless=headless)
    cycle = 0

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
                    print("  State initialized. Next cycles will detect changes.")
            except Exception as e:
                print(f"  CYCLE ERROR: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await session.stop()
                except Exception:
                    pass
                await asyncio.sleep(10)
                await session.start()

            # Check if it's time for the daily digest (disabled by default)
            if ALERT_DAILY_DIGEST:
                _check_and_run_digest(community, dry_run=dry_run)

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
    parser = argparse.ArgumentParser(description="Skool Apprise Monitor v2")
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
    parser.add_argument("--test", action="store_true",
                        help="Send test notifications for all 5 alert types (no scraping)")
    args = parser.parse_args()

    if args.test:
        run_test_notifications(dry_run=args.dry_run)
        return

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
