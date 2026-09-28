#!/usr/bin/env python3
"""Universal Chamber Directory Scraper

Supports GrowthZone, ChamberMaster (same gz-* CSS classes, different URL patterns),
Atlas (Angular SPA), and generic fallback with 10+ CSS selector strategies.

Usage:
    python scrape_directory.py --config data/chambers.json --all
    python scrape_directory.py --config data/chambers.json --chamber olathe
    python scrape_directory.py --config data/chambers.json --chamber kc-metro --platform growthzone
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import asyncio
import argparse
import json
import time
import string
import signal
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from pathlib import Path

# ---------------------------------------------------------------------------
# JavaScript extraction snippets
# ---------------------------------------------------------------------------

GZ_EXTRACT_JS = """
() => {
    const members = [];
    const cards = document.querySelectorAll('.card.gz-results-card, .card.gz-directory-card');
    for (const card of cards) {
        const nameEl = card.querySelector('.gz-card-title a, .card-title a, a.card-link');
        const company = nameEl ? nameEl.textContent.trim() : '';
        const detailUrl = nameEl ? nameEl.href : '';
        const addrEl = card.querySelector('.gz-card-address');
        const address = addrEl ? addrEl.textContent.trim().replace(/\\s+/g, ' ') : '';
        const phoneEl = card.querySelector('.gz-card-phone a[href^="tel:"], a[href^="tel:"]');
        let phone = phoneEl ? phoneEl.textContent.trim() : '';
        if (!phone) {
            const pm = card.textContent.match(/\\(?\\d{3}\\)?[\\s.-]?\\d{3}[\\s.-]?\\d{4}/);
            phone = pm ? pm[0] : '';
        }
        let website = '';
        const links = card.querySelectorAll('a[href]');
        for (const l of links) {
            if (l.href.startsWith('http') &&
                !l.href.includes('facebook') && !l.href.includes('linkedin') &&
                !l.href.includes('twitter') && !l.href.includes('instagram') &&
                !l.href.includes('youtube') && !l.href.includes('google') &&
                !l.href.includes(window.location.hostname) &&
                !l.href.includes('growthzone') && !l.href.includes('gz.') &&
                !l.href.includes('chambermaster') && !l.href.includes('/list')) {
                website = l.href;
                break;
            }
        }
        const descEl = card.querySelector('.gz-description, .gz-member-description');
        let category = descEl ? descEl.textContent.trim().substring(0, 100) : '';
        if (!category) {
            const catEl = card.querySelector('.gz-card-cat');
            if (catEl) category = catEl.textContent.trim().replace(/\\s+/g, ' ').substring(0, 100);
        }
        if (company && company.length > 2) {
            members.push({ company, address, phone, website, category, detail_url: detailUrl });
        }
    }
    return members;
}
"""

ATLAS_EXTRACT_JS = """
() => {
    const members = [];
    const headings = document.querySelectorAll('h2.mb-15');
    for (const h2 of headings) {
        const company = h2.textContent.trim();
        const parent = h2.closest('.listing-item, .card, [class*="listing"]') || h2.parentElement;
        let phone = '', address = '', website = '', detail_url = '';
        if (parent) {
            const phoneEl = parent.querySelector('a[href^="tel:"]');
            phone = phoneEl ? phoneEl.textContent.trim() : '';
            const addrEl = parent.querySelector('[class*="address"], .text-muted');
            address = addrEl ? addrEl.textContent.trim().replace(/\\s+/g, ' ') : '';
            const links = parent.querySelectorAll('a[href]');
            for (const l of links) {
                if (l.href.startsWith('http') && !l.href.includes(window.location.hostname) &&
                    !l.href.includes('facebook') && !l.href.includes('linkedin') &&
                    !l.href.includes('twitter') && !l.href.includes('instagram')) {
                    website = l.href;
                    break;
                }
            }
            const detailLink = h2.querySelector('a') || parent.querySelector('a[href*="atlas"]');
            detail_url = detailLink ? detailLink.href : '';
        }
        if (company && company.length > 2) {
            members.push({ company, address, phone, website, category: '', detail_url });
        }
    }
    return members;
}
"""

GENERIC_EXTRACT_JS = """
() => {
    const members = [];
    const selectors = [
        '.member-card', '.business-card', '.directory-entry', '.member-listing',
        '.listing-item', '.directory-item', '.et_pb_team_member', '.wp-block-group',
        '.entry-content li', '.locable-business', '[class*="member"]',
        '[class*="directory"] .card', '.gz-results-card', '.mn-search-result'
    ];
    let cards = [];
    for (const sel of selectors) {
        const found = document.querySelectorAll(sel);
        if (found.length > 0) {
            cards = found;
            break;
        }
    }
    if (cards.length === 0) {
        // Last resort: look for repeated card-like structures
        const allCards = document.querySelectorAll('.card, [class*="item"], [class*="listing"]');
        if (allCards.length > 2) cards = allCards;
    }
    for (const card of cards) {
        const headings = card.querySelectorAll('h2, h3, h4, h5, .card-title, a.card-link, strong');
        let company = '';
        let detail_url = '';
        for (const h of headings) {
            const text = h.textContent.trim();
            if (text.length > 2 && text.length < 200) {
                company = text;
                const link = h.tagName === 'A' ? h : h.querySelector('a');
                if (link) detail_url = link.href;
                break;
            }
        }
        if (!company) continue;
        const phoneEl = card.querySelector('a[href^="tel:"]');
        let phone = phoneEl ? phoneEl.textContent.trim() : '';
        if (!phone) {
            const pm = card.textContent.match(/\\(?\\d{3}\\)?[\\s.-]?\\d{3}[\\s.-]?\\d{4}/);
            phone = pm ? pm[0] : '';
        }
        let address = '';
        const addrEl = card.querySelector('[class*="address"], [class*="addr"]');
        if (addrEl) address = addrEl.textContent.trim().replace(/\\s+/g, ' ');
        let website = '';
        const links = card.querySelectorAll('a[href]');
        for (const l of links) {
            if (l.href.startsWith('http') && !l.href.includes(window.location.hostname) &&
                !l.href.includes('facebook') && !l.href.includes('linkedin') &&
                !l.href.includes('twitter') && !l.href.includes('instagram') &&
                !l.href.includes('youtube') && !l.href.includes('google') &&
                !l.href.includes('mailto:') && !l.href.includes('tel:')) {
                website = l.href;
                break;
            }
        }
        if (company.length > 2) {
            members.push({ company, address, phone, website, category: '', detail_url });
        }
    }
    return members;
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    """Load chambers config JSON."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_members(output_path: str) -> list:
    """Load existing members file if it exists."""
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_members(members: list, output_path: str):
    """Save members to JSON file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(members, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] {len(members)} members -> {output_path}")


def deduplicate_members(members: list) -> list:
    """Deduplicate by normalized company name within same chamber."""
    seen = set()
    unique = []
    for m in members:
        key = (m.get("chamber_slug", ""), m.get("company", "").lower().strip())
        if key not in seen and key[1]:
            seen.add(key)
            unique.append(m)
    return unique


def classify_if_available(member: dict) -> dict:
    """Try to classify member using ICP classifier if available."""
    try:
        from lib.icp_classifier import classify_business
        result = classify_business(
            company=member.get("company", ""),
            category=member.get("category", ""),
            website=member.get("website", ""),
        )
        member["icp_tier"] = result.get("tier", "")
        member["icp_score"] = result.get("score", 0)
        member["icp_reason"] = result.get("reason", "")
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] ICP classification error for {member.get('company')}: {e}")
    return member


# ---------------------------------------------------------------------------
# A-Z Navigation Detection
# ---------------------------------------------------------------------------

async def detect_az_pattern(page, base_url: str) -> str:
    """Detect which A-Z navigation pattern the directory uses.

    Returns one of:
        'searchalpha'    -> /list/searchalpha/{letter}  (ChamberMaster style)
        'findstartswith' -> /memberdirectory/FindStartsWith?term={letter}  (GrowthZone style)
        'none'           -> no A-Z navigation detected
    """
    html = await page.content()
    html_lower = html.lower()

    # Check for searchalpha links
    if "searchalpha" in html_lower:
        return "searchalpha"

    # Check for FindStartsWith links
    if "findstartswith" in html_lower:
        return "findstartswith"

    # Check for alpha navigation by looking at link patterns
    alpha_links = await page.evaluate("""
        () => {
            const links = document.querySelectorAll('a');
            const patterns = { searchalpha: 0, findstartswith: 0 };
            for (const l of links) {
                const href = (l.href || '').toLowerCase();
                if (href.includes('searchalpha')) patterns.searchalpha++;
                if (href.includes('findstartswith')) patterns.findstartswith++;
            }
            return patterns;
        }
    """)

    if alpha_links.get("searchalpha", 0) > 0:
        return "searchalpha"
    if alpha_links.get("findstartswith", 0) > 0:
        return "findstartswith"

    return "none"


def build_letter_url(base_url: str, letter: str, pattern: str) -> str:
    """Build the URL for a specific letter in A-Z navigation."""
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")

    if pattern == "searchalpha":
        # ChamberMaster: /list/searchalpha/A
        return f"{parsed.scheme}://{parsed.netloc}{path}/searchalpha/{letter}"
    elif pattern == "findstartswith":
        # GrowthZone: /memberdirectory/FindStartsWith?term=A
        return f"{parsed.scheme}://{parsed.netloc}{path}/FindStartsWith?term={letter}"
    else:
        return base_url


# ---------------------------------------------------------------------------
# Scraper: GrowthZone / ChamberMaster
# ---------------------------------------------------------------------------

async def scrape_gz_cm(page, chamber: dict, delay: float) -> list:
    """Scrape GrowthZone or ChamberMaster directory using A-Z navigation."""
    url = chamber["directory_url"]
    slug = chamber["slug"]
    all_members = []

    print(f"\n[GZ/CM] Loading: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Detect A-Z navigation pattern
    az_pattern = await detect_az_pattern(page, url)
    print(f"[GZ/CM] A-Z pattern detected: {az_pattern}")

    if az_pattern == "none":
        # No A-Z nav — scrape current page directly
        print("[GZ/CM] No A-Z navigation, scraping current page...")
        members = await page.evaluate(GZ_EXTRACT_JS)
        for m in members:
            m["chamber_slug"] = slug
            m["chamber_name"] = chamber["name"]
            m["source"] = "directory_listing"
            m["scraped_at"] = datetime.now(timezone.utc).isoformat()
        all_members.extend(members)
        print(f"[GZ/CM] Found {len(members)} members on single page")
        return all_members

    # A-Z navigation: iterate through each letter + digits
    letters = list(string.ascii_uppercase) + ["0-9"]
    for letter in letters:
        letter_url = build_letter_url(url, letter, az_pattern)
        print(f"[GZ/CM] Letter {letter}: {letter_url}")

        try:
            await page.goto(letter_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(delay)

            # Check for pagination (more than 50 results)
            page_num = 1
            while True:
                members = await page.evaluate(GZ_EXTRACT_JS)
                for m in members:
                    m["chamber_slug"] = slug
                    m["chamber_name"] = chamber["name"]
                    m["source"] = "directory_listing"
                    m["scraped_at"] = datetime.now(timezone.utc).isoformat()
                all_members.extend(members)

                if len(members) == 0:
                    break

                print(f"  Page {page_num}: {len(members)} members")

                # Check for next page button
                has_next = await page.evaluate("""
                    () => {
                        const nextBtn = document.querySelector(
                            '.pagination .next:not(.disabled) a, ' +
                            'a.gz-pagenav-next:not(.disabled), ' +
                            '.gz-paging-next a, ' +
                            'a[aria-label="Next"]:not([disabled])'
                        );
                        if (nextBtn) { nextBtn.click(); return true; }
                        return false;
                    }
                """)

                if not has_next:
                    break

                page_num += 1
                await asyncio.sleep(delay)
                await page.wait_for_load_state("networkidle", timeout=15000)

        except Exception as e:
            print(f"[WARN] Letter {letter} error: {e}")
            continue

    print(f"[GZ/CM] Total for {slug}: {len(all_members)} members")
    return all_members


# ---------------------------------------------------------------------------
# Scraper: Atlas (Playwright-based, not API)
# ---------------------------------------------------------------------------

async def scrape_atlas(page, chamber: dict, delay: float) -> list:
    """Scrape Atlas Angular SPA directory using Playwright."""
    url = chamber["directory_url"]
    slug = chamber["slug"]
    all_members = []

    print(f"\n[ATLAS] Loading: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)  # Atlas SPAs need extra time

    # Scroll to load all results (Atlas lazy-loads)
    prev_count = 0
    scroll_attempts = 0
    max_scrolls = 50

    while scroll_attempts < max_scrolls:
        members = await page.evaluate(ATLAS_EXTRACT_JS)
        current_count = len(members)

        if current_count == prev_count:
            scroll_attempts += 1
            if scroll_attempts >= 3:
                break
        else:
            scroll_attempts = 0

        prev_count = current_count
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(delay)

    members = await page.evaluate(ATLAS_EXTRACT_JS)
    for m in members:
        m["chamber_slug"] = slug
        m["chamber_name"] = chamber["name"]
        m["source"] = "directory_listing"
        m["scraped_at"] = datetime.now(timezone.utc).isoformat()
    all_members.extend(members)

    print(f"[ATLAS] Total for {slug}: {len(all_members)} members")
    return all_members


# ---------------------------------------------------------------------------
# Scraper: Generic fallback
# ---------------------------------------------------------------------------

async def scrape_generic(page, chamber: dict, delay: float) -> list:
    """Scrape directory using generic multi-selector fallback."""
    url = chamber["directory_url"]
    slug = chamber["slug"]
    all_members = []

    print(f"\n[GENERIC] Loading: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Try pagination: scroll or click "Load More" / next page
    page_num = 1
    max_pages = 50

    while page_num <= max_pages:
        members = await page.evaluate(GENERIC_EXTRACT_JS)
        for m in members:
            m["chamber_slug"] = slug
            m["chamber_name"] = chamber["name"]
            m["source"] = "directory_listing"
            m["scraped_at"] = datetime.now(timezone.utc).isoformat()

        if members:
            all_members.extend(members)
            print(f"  Page {page_num}: {len(members)} members")

        # Try to find next page / load more
        has_next = await page.evaluate("""
            () => {
                const nextSelectors = [
                    '.pagination .next a', 'a.next', '.load-more', 'button.load-more',
                    'a[rel="next"]', '.nav-next a', '.pager .next a',
                    'a[aria-label="Next"]', '.wp-pagenavi .nextpostslink'
                ];
                for (const sel of nextSelectors) {
                    const el = document.querySelector(sel);
                    if (el && !el.classList.contains('disabled') && !el.hasAttribute('disabled')) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }
        """)

        if not has_next:
            break

        page_num += 1
        await asyncio.sleep(delay)

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            await asyncio.sleep(2)

    print(f"[GENERIC] Total for {slug}: {len(all_members)} members")
    return all_members


# ---------------------------------------------------------------------------
# Main scraper dispatcher
# ---------------------------------------------------------------------------

async def scrape_chamber(page, chamber: dict, platform_override: str = None, delay: float = 1.5) -> list:
    """Scrape a single chamber directory.

    Args:
        page: Playwright page object
        chamber: Chamber config dict
        platform_override: Force a specific platform scraper
        delay: Delay between requests in seconds

    Returns: List of member dicts
    """
    platform = platform_override or chamber.get("platform", "").lower()

    if not platform:
        # Auto-detect platform
        from platform_detector import detect_platform
        platform = detect_platform(chamber["directory_url"])
        print(f"[AUTO] Detected platform: {platform}")

    if platform in ("growthzone", "chambermaster"):
        return await scrape_gz_cm(page, chamber, delay)
    elif platform == "atlas":
        return await scrape_atlas(page, chamber, delay)
    else:
        return await scrape_generic(page, chamber, delay)


async def run_scraper(args):
    """Main async entry point."""
    from playwright.async_api import async_playwright

    # Load config
    config = load_config(args.config)
    chambers = config.get("chambers", [])

    if not chambers:
        print("[ERROR] No chambers found in config")
        return

    # Filter chambers
    if args.chamber:
        chambers = [c for c in chambers if c["slug"] == args.chamber]
        if not chambers:
            print(f"[ERROR] Chamber slug '{args.chamber}' not found in config")
            return
    elif not args.all:
        print("[ERROR] Specify --chamber SLUG or --all")
        return

    # Output path
    output_dir = os.path.join(os.path.dirname(args.config), "..", "leads")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "chamber_directory_members.json")

    # Load existing members (preserve data from other chambers)
    all_members = load_existing_members(output_path)
    existing_slugs_to_scrape = {c["slug"] for c in chambers}

    # Remove existing entries for chambers we're about to re-scrape
    all_members = [m for m in all_members if m.get("chamber_slug") not in existing_slugs_to_scrape]

    print(f"[START] Scraping {len(chambers)} chamber(s)")
    print(f"[INFO] Existing members from other chambers: {len(all_members)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not args.visible,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        for chamber in chambers:
            slug = chamber["slug"]
            name = chamber["name"]

            if not chamber.get("public_directory", True):
                print(f"\n[SKIP] {name} — directory not public")
                continue

            if not chamber.get("directory_url"):
                print(f"\n[SKIP] {name} — no directory URL")
                continue

            print(f"\n{'='*60}")
            print(f"Scraping: {name} ({slug})")
            print(f"{'='*60}")

            try:
                members = await scrape_chamber(
                    page, chamber,
                    platform_override=args.platform,
                    delay=args.delay,
                )

                # ICP classification
                for m in members:
                    classify_if_available(m)

                all_members.extend(members)

                # Save after each chamber (checkpoint)
                deduped = deduplicate_members(all_members)
                save_members(deduped, output_path)

            except Exception as e:
                print(f"[ERROR] Failed to scrape {name}: {e}")
                import traceback
                traceback.print_exc()
                continue

        await browser.close()

    # Final dedup and save
    all_members = deduplicate_members(all_members)
    save_members(all_members, output_path)

    # Print summary
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")

    chamber_counts = {}
    for m in all_members:
        s = m.get("chamber_slug", "unknown")
        chamber_counts[s] = chamber_counts.get(s, 0) + 1

    for s, count in sorted(chamber_counts.items()):
        print(f"  {s}: {count} members")
    print(f"  TOTAL: {len(all_members)} members")
    print(f"  Output: {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Universal Chamber Directory Scraper (GrowthZone/ChamberMaster/Atlas/Generic)"
    )
    parser.add_argument("--config", required=True, help="Path to chambers.json config file")
    parser.add_argument("--chamber", help="Scrape a single chamber by slug")
    parser.add_argument("--all", action="store_true", help="Scrape all chambers in config")
    parser.add_argument("--platform", help="Force platform type (growthzone/chambermaster/atlas/generic)")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible (non-headless) mode")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests in seconds (default: 1.5)")
    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n[INTERRUPTED] Saving progress and exiting...")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(run_scraper(args))


if __name__ == "__main__":
    main()
