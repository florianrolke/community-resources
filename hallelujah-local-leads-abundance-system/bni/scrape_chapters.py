#!/usr/bin/env python3
"""
Universal BNI chapter member scraper using Playwright.

Scrapes member data from BNI chapter pages across multiple regional portals.
Each portal may have slightly different HTML structures, but members are
typically displayed in a table or grid on a "Members" tab.

Features:
- Multi-portal support (different BNI regional sites)
- Pagination handling (50 members per page)
- Count validation against header "Member Count: N"
- ICP classification of scraped businesses
- Checkpoint/resume for large scraping jobs

Usage:
    python scrape_chapters.py --config data/chapters.json --all
    python scrape_chapters.py --config data/chapters.json --chapter "Power Players"
    python scrape_chapters.py --portal "north-carolina" --all
    python scrape_chapters.py --config data/chapters.json --all --visible --delay 3
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
import json
import time
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from lib.icp_classifier import classify_business

# ---------------------------------------------------------------------------
# Portal registry -- regional BNI sites with their base URLs
# ---------------------------------------------------------------------------

PORTAL_REGISTRY = {
    "manhattan": {"base_url": "https://manhattanbni.com", "chapter_list": "/chapters"},
    "new-york": {"base_url": "https://bni-newyork.com", "chapter_list": "/chapters"},
    "north-carolina": {"base_url": "https://bni-nc.com", "chapter_list": "/chapters"},
    "michigan": {"base_url": "https://bni-mi.com", "chapter_list": "/chapters"},
    "arizona": {"base_url": "https://bni-az.com", "chapter_list": "/chapters"},
    "georgia": {"base_url": "https://bni-ga.com", "chapter_list": "/chapters"},
    "new-jersey": {"base_url": "https://bni-nj.com", "chapter_list": "/chapters"},
    "kansas-city": {"base_url": "https://bni-kc.com", "chapter_list": "/chapters"},
    "southeast": {"base_url": "https://bnisoutheast.com", "chapter_list": "/chapters"},
    "perth": {"base_url": "https://bniperth.com.au", "chapter_list": "/chapters"},
}

# ---------------------------------------------------------------------------
# JavaScript extraction snippets
# ---------------------------------------------------------------------------

EXTRACT_MEMBERS_JS = """
() => {
    const members = [];
    // Try table rows first, then grid/card layouts
    const rows = document.querySelectorAll('table tbody tr, .member-row, .team-member, .member-card, .member-item');
    for (const row of rows) {
        const nameEl = row.querySelector('td:first-child, .member-name, h3, h4, .name');
        const companyEl = row.querySelector('td:nth-child(2), .member-company, .company, .business-name');
        const categoryEl = row.querySelector('td:nth-child(3), .member-category, .category, .profession');
        const phoneEl = row.querySelector('td:nth-child(4), .member-phone, .phone, a[href^="tel:"]');
        const websiteEl = row.querySelector('a[href^="http"]:not([href*="linkedin"]):not([href*="facebook"])');
        const linkedinEl = row.querySelector('a[href*="linkedin.com"]');

        const name = nameEl ? nameEl.textContent.trim() : '';
        if (name && name.length > 2) {
            members.push({
                name: name,
                company: companyEl ? companyEl.textContent.trim() : '',
                category: categoryEl ? categoryEl.textContent.trim() : '',
                phone: phoneEl ? phoneEl.textContent.trim().replace(/[^0-9+()-\\s]/g, '') : '',
                website: websiteEl ? websiteEl.href : '',
                linkedin: linkedinEl ? linkedinEl.href : ''
            });
        }
    }
    return members;
}
"""

EXTRACT_MEMBER_COUNT_JS = """
() => {
    // Look for "Member Count: N" or "N Members" patterns in page text
    const body = document.body.innerText;
    const patterns = [
        /Member Count:\\s*(\\d+)/i,
        /(\\d+)\\s+Members?/i,
        /Total\\s+Members?:\\s*(\\d+)/i,
        /Showing\\s+\\d+\\s+of\\s+(\\d+)/i,
    ];
    for (const pat of patterns) {
        const m = body.match(pat);
        if (m) return parseInt(m[1]);
    }
    return null;
}
"""

CHECK_PAGINATION_JS = """
() => {
    const nextBtn = document.querySelector(
        'a.next, button.next, [aria-label="Next"], .pagination .next, ' +
        'a:has(> span.next), li.next > a, a[rel="next"], .pager-next a'
    );
    if (!nextBtn) return null;
    if (nextBtn.classList.contains('disabled') || nextBtn.hasAttribute('disabled')) return null;
    return nextBtn.href || 'CLICK';
}
"""

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def member_hash(member: dict) -> str:
    """Dedupe key for a member based on name + company."""
    raw = f"{member.get('name', '').lower().strip()}|{member.get('company', '').lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def load_config(config_path: str) -> dict:
    """Load chapter configuration from JSON file."""
    path = Path(config_path)
    if not path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_results(results: list[dict], output_path: str):
    """Save scraped members to JSON file."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] {len(results)} members -> {out}")


def load_checkpoint(checkpoint_path: Path) -> dict:
    """Load checkpoint file tracking which chapters have been scraped."""
    if checkpoint_path.exists():
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed_chapters": [], "members": []}


def save_checkpoint(checkpoint_path: Path, data: dict):
    """Save checkpoint data."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------


def scrape_chapter_members(page, chapter: dict, delay: float = 2.0) -> list[dict]:
    """
    Scrape all members from a single BNI chapter page.

    Steps:
    1. Navigate to the chapter URL
    2. Click the "Members" tab if present
    3. Wait for member table/grid to load
    4. Extract all members from current page
    5. Handle pagination (click Next until exhausted)
    6. Validate count against header if available
    """
    url = chapter.get("url", "")
    chapter_name = chapter.get("name", "Unknown")
    print(f"\n{'='*60}")
    print(f"[SCRAPING] {chapter_name}")
    print(f"[URL] {url}")

    if not url:
        print(f"[SKIP] No URL for chapter: {chapter_name}")
        return []

    all_members = []
    seen_hashes = set()

    try:
        # Step 1: Navigate to chapter page
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(delay)

        # Step 2: Try to click "Members" tab
        members_tab_clicked = False
        tab_selectors = [
            'a:has-text("Members")',
            'button:has-text("Members")',
            '[data-tab="members"]',
            '.tab:has-text("Members")',
            'li:has-text("Members") > a',
            '#members-tab',
            'a[href="#members"]',
            'a[href*="members"]',
        ]
        for selector in tab_selectors:
            try:
                tab = page.locator(selector).first
                if tab.is_visible(timeout=2000):
                    tab.click()
                    members_tab_clicked = True
                    print(f"[TAB] Clicked Members tab via: {selector}")
                    time.sleep(delay)
                    break
            except Exception:
                continue

        if not members_tab_clicked:
            print("[TAB] No Members tab found -- scraping page directly")

        # Step 3: Wait for member content to appear
        content_selectors = [
            "table tbody tr",
            ".member-row",
            ".team-member",
            ".member-card",
            ".member-item",
        ]
        content_loaded = False
        for sel in content_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                content_loaded = True
                print(f"[CONTENT] Found members via: {sel}")
                break
            except Exception:
                continue

        if not content_loaded:
            print("[WARN] No member content detected on page")

        # Step 4: Get expected member count from header
        expected_count = page.evaluate(EXTRACT_MEMBER_COUNT_JS)
        if expected_count:
            print(f"[HEADER] Expected member count: {expected_count}")

        # Step 5: Paginate and extract
        page_num = 1
        max_pages = 50  # Safety limit

        while page_num <= max_pages:
            print(f"  [PAGE {page_num}] Extracting members...")

            members_on_page = page.evaluate(EXTRACT_MEMBERS_JS)

            new_count = 0
            for m in members_on_page:
                h = member_hash(m)
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    m["chapter"] = chapter_name
                    m["chapter_url"] = url
                    m["meeting_day"] = chapter.get("meeting_day", "")
                    m["meeting_time"] = chapter.get("meeting_time", "")
                    m["city"] = chapter.get("city", "")
                    m["state"] = chapter.get("state", "")
                    m["scraped_at"] = datetime.now(timezone.utc).isoformat()

                    # ICP classification
                    try:
                        classification = classify_business(
                            m.get("company", ""), m.get("category", "")
                        )
                        m["icp_tier"] = classification.get("tier", "D")
                        m["icp_reason"] = classification.get("reason", "")
                    except Exception:
                        m["icp_tier"] = "D"
                        m["icp_reason"] = "classification_error"

                    all_members.append(m)
                    new_count += 1

            print(f"  [PAGE {page_num}] Found {len(members_on_page)} members ({new_count} new)")

            if len(members_on_page) == 0:
                break

            # Check for next page
            next_action = page.evaluate(CHECK_PAGINATION_JS)
            if not next_action:
                print(f"  [DONE] No more pages")
                break

            # Click next or navigate
            if next_action == "CLICK":
                try:
                    next_btn = page.locator(
                        'a.next, button.next, [aria-label="Next"], .pagination .next, '
                        'li.next > a, a[rel="next"], .pager-next a'
                    ).first
                    next_btn.click()
                    time.sleep(delay)
                    page_num += 1
                except Exception as e:
                    print(f"  [WARN] Failed to click Next: {e}")
                    break
            else:
                # next_action is a URL
                try:
                    page.goto(next_action, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(delay)
                    page_num += 1
                except Exception as e:
                    print(f"  [WARN] Failed to navigate to next page: {e}")
                    break

        # Step 6: Validate count
        if expected_count:
            actual = len(all_members)
            if actual == expected_count:
                print(f"[VALID] Count matches: {actual} == {expected_count}")
            elif actual < expected_count:
                pct = (actual / expected_count) * 100
                print(f"[WARN] Scraped {actual}/{expected_count} ({pct:.0f}%) -- may be missing members")
            else:
                print(f"[INFO] Scraped {actual} > expected {expected_count} (possible duplicates in header)")

    except Exception as e:
        print(f"[ERROR] Failed to scrape {chapter_name}: {e}")

    print(f"[RESULT] {chapter_name}: {len(all_members)} members scraped")
    return all_members


def scrape_all_chapters(
    chapters: list[dict],
    output_path: str,
    headless: bool = True,
    delay: float = 2.0,
):
    """
    Scrape members from multiple BNI chapters using Playwright.

    Uses checkpoint/resume so interrupted scraping can continue.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    checkpoint_path = Path(output_path).parent / ".bni_scrape_checkpoint.json"
    checkpoint = load_checkpoint(checkpoint_path)
    completed = set(checkpoint.get("completed_chapters", []))
    all_members = checkpoint.get("members", [])

    remaining = [ch for ch in chapters if ch.get("name", "") not in completed]
    print(f"\n[START] {len(remaining)} chapters to scrape ({len(completed)} already done)")
    print(f"[CHECKPOINT] {len(all_members)} members from previous runs")

    if not remaining:
        print("[DONE] All chapters already scraped")
        save_results(all_members, output_path)
        return all_members

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for i, chapter in enumerate(remaining, 1):
            ch_name = chapter.get("name", f"chapter_{i}")
            print(f"\n--- Chapter {i}/{len(remaining)}: {ch_name} ---")

            members = scrape_chapter_members(page, chapter, delay=delay)
            all_members.extend(members)

            # Update checkpoint
            completed.add(ch_name)
            checkpoint["completed_chapters"] = list(completed)
            checkpoint["members"] = all_members
            save_checkpoint(checkpoint_path, checkpoint)
            print(f"[CHECKPOINT] Saved ({len(all_members)} total members)")

            # Polite delay between chapters
            if i < len(remaining):
                time.sleep(delay)

        browser.close()

    # Final save
    save_results(all_members, output_path)

    # Clean up checkpoint on successful completion
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        print("[CLEANUP] Removed checkpoint file")

    # Summary
    print(f"\n{'='*60}")
    print(f"[SUMMARY]")
    print(f"  Chapters scraped: {len(chapters)}")
    print(f"  Total members: {len(all_members)}")

    # Tier breakdown
    tiers = {"A": 0, "B": 0, "C": 0, "D": 0}
    for m in all_members:
        tier = m.get("icp_tier", "D")
        tiers[tier] = tiers.get(tier, 0) + 1
    print(f"  ICP tiers: A={tiers['A']}, B={tiers['B']}, C={tiers['C']}, D={tiers['D']}")

    # Per-chapter breakdown
    chapter_counts = {}
    for m in all_members:
        ch = m.get("chapter", "Unknown")
        chapter_counts[ch] = chapter_counts.get(ch, 0) + 1
    for ch, count in sorted(chapter_counts.items(), key=lambda x: -x[1]):
        print(f"  {ch}: {count} members")

    return all_members


# ---------------------------------------------------------------------------
# Auto-discover chapters from a portal
# ---------------------------------------------------------------------------


def discover_portal_chapters(page, portal_key: str, delay: float = 2.0) -> list[dict]:
    """
    Auto-discover chapters by scraping a portal's chapter listing page.
    Returns a list of chapter dicts with name, slug, url.
    """
    if portal_key not in PORTAL_REGISTRY:
        print(f"[ERROR] Unknown portal: {portal_key}")
        print(f"[AVAILABLE] {', '.join(PORTAL_REGISTRY.keys())}")
        return []

    portal = PORTAL_REGISTRY[portal_key]
    list_url = portal["base_url"] + portal["chapter_list"]
    print(f"\n[DISCOVER] Scanning portal: {portal_key}")
    print(f"[URL] {list_url}")

    try:
        page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(delay)
    except Exception as e:
        print(f"[ERROR] Failed to load portal: {e}")
        return []

    # Extract chapter links from the listing page
    chapters_js = """
    () => {
        const chapters = [];
        const links = document.querySelectorAll(
            'a[href*="/chapter"], a[href*="/chapters/"], .chapter-card a, .chapter-link, ' +
            '.chapter-item a, .chapter-name a, h3 a, h4 a'
        );
        const seen = new Set();
        for (const link of links) {
            const name = link.textContent.trim();
            const href = link.href;
            if (name && name.length > 2 && href && !seen.has(href)) {
                seen.add(href);
                chapters.push({name: name, url: href});
            }
        }
        return chapters;
    }
    """

    raw_chapters = page.evaluate(chapters_js)
    chapters = []
    for ch in raw_chapters:
        slug = ch["url"].rstrip("/").split("/")[-1]
        chapters.append(
            {
                "name": ch["name"],
                "slug": slug,
                "url": ch["url"],
                "meeting_day": "",
                "meeting_time": "",
                "city": "",
                "state": "",
            }
        )

    print(f"[DISCOVER] Found {len(chapters)} chapters on portal")
    for ch in chapters[:10]:
        print(f"  - {ch['name']} ({ch['url']})")
    if len(chapters) > 10:
        print(f"  ... and {len(chapters) - 10} more")

    return chapters


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Scrape BNI chapter members using Playwright"
    )
    parser.add_argument(
        "--config",
        default="data/chapters.json",
        help="Path to chapters config JSON (default: data/chapters.json)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape all chapters in the config",
    )
    parser.add_argument(
        "--chapter",
        type=str,
        help="Scrape a specific chapter by name",
    )
    parser.add_argument(
        "--portal",
        type=str,
        help="Auto-discover and scrape all chapters from a portal (e.g., 'michigan')",
    )
    parser.add_argument(
        "--output",
        default="leads/bni_all_members.json",
        help="Output file path (default: leads/bni_all_members.json)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run browser in visible (non-headless) mode",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between page loads (default: 2.0)",
    )
    args = parser.parse_args()

    # Resolve paths relative to this script's directory
    script_dir = Path(__file__).resolve().parent
    output_path = script_dir / args.output

    chapters = []

    if args.portal:
        # Auto-discover chapters from a portal
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[ERROR] Playwright not installed. Run: pip install playwright && playwright install chromium")
            sys.exit(1)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.visible)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            chapters = discover_portal_chapters(page, args.portal, delay=args.delay)
            browser.close()

        if not chapters:
            print("[ERROR] No chapters discovered from portal")
            sys.exit(1)

        # Save discovered chapters for future reference
        disc_path = script_dir / "data" / f"discovered_{args.portal}.json"
        disc_path.parent.mkdir(parents=True, exist_ok=True)
        with open(disc_path, "w", encoding="utf-8") as f:
            json.dump(
                {"portal": args.portal, "discovered_at": datetime.now(timezone.utc).isoformat(), "chapters": chapters},
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"[SAVED] Discovered chapters -> {disc_path}")

    else:
        # Load from config file
        config_path = script_dir / args.config
        config = load_config(str(config_path))
        chapters = config.get("chapters", [])

    if not chapters:
        print("[ERROR] No chapters found to scrape")
        sys.exit(1)

    # Filter to specific chapter if requested
    if args.chapter:
        target = args.chapter.lower()
        chapters = [ch for ch in chapters if target in ch.get("name", "").lower()]
        if not chapters:
            print(f"[ERROR] No chapter matching '{args.chapter}' found")
            sys.exit(1)
        print(f"[FILTER] Scraping {len(chapters)} chapter(s) matching '{args.chapter}'")

    if not args.all and not args.chapter and not args.portal:
        print("[INFO] No action specified. Use --all, --chapter, or --portal")
        print(f"[INFO] Config has {len(chapters)} chapters available")
        for ch in chapters:
            print(f"  - {ch.get('name', '?')}")
        sys.exit(0)

    # Run the scraper
    scrape_all_chapters(
        chapters=chapters,
        output_path=str(output_path),
        headless=not args.visible,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
