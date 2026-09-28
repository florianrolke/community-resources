#!/usr/bin/env python3
"""Chamber Detail Page Enrichment Scraper

Visits each member's detail_url to extract LinkedIn, social links, contacts,
and descriptions not available on directory listing pages.

Reads from leads/chamber_directory_members.json (READ ONLY).
Writes per-chamber files to leads/detail_enrichment/{slug}.json.
Checkpoint: saves every 5 members + on Ctrl+C.
Resume: re-running skips already-enriched members.

Usage:
    python scrape_detail_pages.py --chamber olathe
    python scrape_detail_pages.py --chamber olathe --visible --delay 2.0
    python scrape_detail_pages.py --all
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import asyncio
import argparse
import json
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# ---------------------------------------------------------------------------
# Configuration: chamber social patterns to filter OUT
# ---------------------------------------------------------------------------

# Add your chamber's own social links here so they don't get attributed to members
CHAMBER_SOCIAL_PATTERNS = [
    # Generic chamber patterns
    "facebook.com/chamber",
    "linkedin.com/company/chamber",
    "twitter.com/chamber",
    "instagram.com/chamber",
    # GrowthZone / ChamberMaster platform pages
    "growthzoneapp.com",
    "chambermaster.com",
]

# Share button URL patterns to filter out
SHARE_PATTERNS = [
    "shareArticle",
    "sharer.php",
    "share?url=",
    "share?text=",
    "intent/tweet",
    "pinterest.com/pin/create",
    "reddit.com/submit",
    "plus.google.com/share",
    "addthis.com",
    "sharethis.com",
]


# ---------------------------------------------------------------------------
# Social link extraction
# ---------------------------------------------------------------------------

def is_share_button(href: str) -> bool:
    """Check if a URL is a share button rather than a profile link."""
    href_lower = href.lower()
    return any(pattern in href_lower for pattern in SHARE_PATTERNS)


def is_chamber_social(href: str) -> bool:
    """Check if a URL belongs to the chamber itself (not a member)."""
    href_lower = href.lower()
    return any(pattern in href_lower for pattern in CHAMBER_SOCIAL_PATTERNS)


def decode_referral_url(href: str) -> str:
    """Decode ChamberMaster referral redirect URLs.

    ChamberMaster wraps social links: /referral.aspx?URL=https://linkedin.com/...
    """
    if "referral.aspx" in href.lower():
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        url_param = params.get("URL", params.get("url", [None]))[0]
        if url_param:
            return unquote(url_param)
    return href


SOCIAL_EXTRACT_JS = """
() => {
    const social = {linkedin: null, facebook: null, twitter: null, instagram: null, youtube: null};
    const contacts = [];
    let description = '';

    const sharePatterns = [
        'sharearticle', 'sharer.php', 'share?url=', 'share?text=',
        'intent/tweet', 'pinterest.com/pin/create', 'reddit.com/submit',
        'addthis.com', 'sharethis.com'
    ];

    function isShareButton(href) {
        const h = href.toLowerCase();
        return sharePatterns.some(p => h.includes(p));
    }

    function isElementorSocialIcon(el) {
        const classes = Array.from(el.classList || []);
        const parentClasses = el.parentElement ? Array.from(el.parentElement.classList || []) : [];
        return classes.some(c => c.includes('elementor-social-icon')) ||
               parentClasses.some(c => c.includes('elementor-social-icon'));
    }

    function isMemberSocial(el) {
        const classes = Array.from(el.classList || []);
        const parentClasses = el.parentElement ? Array.from(el.parentElement.classList || []) : [];
        const allClasses = [...classes, ...parentClasses].join(' ');
        return allClasses.includes('gz-social') || allClasses.includes('gz-details-social') ||
               allClasses.includes('member-social') || allClasses.includes('listing-social');
    }

    // Extract social links
    const allLinks = document.querySelectorAll('a[href]');
    for (const a of allLinks) {
        const href = a.href.trim();
        if (!href || href === '#') continue;
        if (isShareButton(href)) continue;
        if (isElementorSocialIcon(a)) continue;

        const isMember = isMemberSocial(a);
        const hl = href.toLowerCase();

        // Decode referral URLs
        let actualHref = href;
        if (hl.includes('referral.aspx')) {
            try {
                const url = new URL(href);
                const redirectUrl = url.searchParams.get('URL') || url.searchParams.get('url');
                if (redirectUrl) actualHref = decodeURIComponent(redirectUrl);
            } catch(e) {}
        }
        const al = actualHref.toLowerCase();

        if (al.includes('linkedin.com') && !al.includes('sharedarticle')) {
            if (!social.linkedin || isMember) social.linkedin = actualHref;
        } else if (al.includes('facebook.com') && !al.includes('sharer')) {
            if (!social.facebook || isMember) social.facebook = actualHref;
        } else if ((al.includes('twitter.com') || al.includes('x.com')) && !al.includes('intent/tweet')) {
            if (!social.twitter || isMember) social.twitter = actualHref;
        } else if (al.includes('instagram.com')) {
            if (!social.instagram || isMember) social.instagram = actualHref;
        } else if (al.includes('youtube.com') || al.includes('youtu.be')) {
            if (!social.youtube || isMember) social.youtube = actualHref;
        }
    }

    // Extract contacts (name, title, phone, email)
    const contactCards = document.querySelectorAll(
        '.gz-card-contact, .gz-details-contact, .contact-card, ' +
        '[class*="representative"], [class*="contact-person"], ' +
        '.gz-rep-card, .gz-details-rep'
    );
    for (const card of contactCards) {
        const nameEl = card.querySelector('h3, h4, h5, strong, .contact-name, .gz-rep-name');
        const titleEl = card.querySelector('.contact-title, .gz-rep-title, [class*="title"], em, small');
        const phoneEl = card.querySelector('a[href^="tel:"]');
        const emailEl = card.querySelector('a[href^="mailto:"]');

        if (nameEl) {
            contacts.push({
                name: nameEl.textContent.trim(),
                title: titleEl ? titleEl.textContent.trim() : '',
                phone: phoneEl ? phoneEl.textContent.trim() : '',
                email: emailEl ? emailEl.href.replace('mailto:', '').split('?')[0] : '',
            });
        }
    }

    // If no contact cards found, try to find email/phone inline
    if (contacts.length === 0) {
        const emailLinks = document.querySelectorAll('a[href^="mailto:"]');
        const phoneLinks = document.querySelectorAll('a[href^="tel:"]');
        if (emailLinks.length > 0 || phoneLinks.length > 0) {
            contacts.push({
                name: '',
                title: '',
                phone: phoneLinks.length > 0 ? phoneLinks[0].textContent.trim() : '',
                email: emailLinks.length > 0 ? emailLinks[0].href.replace('mailto:', '').split('?')[0] : '',
            });
        }
    }

    // Extract description
    const descEl = document.querySelector(
        '.gz-details-about, .gz-member-description, .member-description, ' +
        '.business-description, [class*="about"], [class*="description"]'
    );
    if (descEl) {
        description = descEl.textContent.trim().replace(/\\s+/g, ' ').substring(0, 1000);
    }

    return { social, contacts, description };
}
"""


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def get_enrichment_path(base_dir: str, slug: str) -> str:
    """Get path for per-chamber enrichment file."""
    enrichment_dir = os.path.join(base_dir, "leads", "detail_enrichment")
    os.makedirs(enrichment_dir, exist_ok=True)
    return os.path.join(enrichment_dir, f"{slug}.json")


def load_enrichment_file(path: str) -> dict:
    """Load existing enrichment data. Returns dict keyed by company name."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {m.get("company", ""): m for m in data if m.get("company")}
        return data
    return {}


def save_enrichment_file(path: str, enriched: dict):
    """Save enrichment data."""
    members_list = list(enriched.values())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(members_list, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] {len(members_list)} enriched members -> {path}")


def load_directory_members(base_dir: str) -> list:
    """Load main directory members file (READ ONLY)."""
    path = os.path.join(base_dir, "leads", "chamber_directory_members.json")
    if not os.path.exists(path):
        print(f"[ERROR] Members file not found: {path}")
        print("[HINT] Run scrape_directory.py first to populate the directory.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def enrich_chamber(page, members: list, enrichment_path: str, slug: str, delay: float):
    """Enrich detail pages for one chamber's members."""
    # Load existing enrichment data for resume
    enriched = load_enrichment_file(enrichment_path)
    already_done = set(enriched.keys())

    # Filter to members with detail_url that haven't been enriched
    to_enrich = []
    for m in members:
        company = m.get("company", "")
        detail_url = m.get("detail_url", "")
        if not company or not detail_url:
            continue
        if company in already_done and enriched[company].get("detail_enrichment_complete"):
            continue
        to_enrich.append(m)

    if not to_enrich:
        print(f"[{slug}] All {len(members)} members already enriched. Skipping.")
        return

    print(f"[{slug}] {len(to_enrich)} members to enrich ({len(already_done)} already done)")

    checkpoint_count = 0
    for i, member in enumerate(to_enrich):
        company = member["company"]
        detail_url = member["detail_url"]

        try:
            print(f"  [{i+1}/{len(to_enrich)}] {company[:50]}")
            await page.goto(detail_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(delay)

            # Extract social links, contacts, description
            result = await page.evaluate(SOCIAL_EXTRACT_JS)

            social = result.get("social", {})
            contacts = result.get("contacts", [])
            description = result.get("description", "")

            # Build enriched record (preserve original fields + add new)
            enriched_member = {**member}
            enriched_member["linkedin"] = social.get("linkedin")
            enriched_member["facebook"] = social.get("facebook")
            enriched_member["twitter"] = social.get("twitter")
            enriched_member["instagram"] = social.get("instagram")
            enriched_member["youtube"] = social.get("youtube")
            enriched_member["contacts"] = contacts
            enriched_member["description"] = description
            enriched_member["detail_enrichment_complete"] = True
            enriched_member["detail_enriched_at"] = datetime.now(timezone.utc).isoformat()

            # Filter out chamber social links (post-processing in Python for robustness)
            for platform_key in ["linkedin", "facebook", "twitter", "instagram", "youtube"]:
                url = enriched_member.get(platform_key)
                if url and is_chamber_social(url):
                    enriched_member[platform_key] = None
                if url and is_share_button(url):
                    enriched_member[platform_key] = None
                # Decode referral URLs
                if url and "referral.aspx" in url.lower():
                    enriched_member[platform_key] = decode_referral_url(url)

            enriched[company] = enriched_member
            checkpoint_count += 1

            # Log social links found
            social_found = [k for k in ["linkedin", "facebook", "twitter", "instagram", "youtube"]
                          if enriched_member.get(k)]
            if social_found:
                print(f"    -> Social: {', '.join(social_found)}")
            if contacts:
                print(f"    -> Contacts: {len(contacts)}")

        except Exception as e:
            print(f"    [WARN] Error enriching {company}: {e}")
            # Still mark as attempted to avoid infinite retries
            enriched_member = {**member}
            enriched_member["detail_enrichment_complete"] = True
            enriched_member["detail_enrichment_error"] = str(e)[:200]
            enriched_member["detail_enriched_at"] = datetime.now(timezone.utc).isoformat()
            enriched[company] = enriched_member
            checkpoint_count += 1

        # Checkpoint every 5 members
        if checkpoint_count >= 5:
            save_enrichment_file(enrichment_path, enriched)
            checkpoint_count = 0

    # Final save
    save_enrichment_file(enrichment_path, enriched)

    # Print summary
    linkedin_count = sum(1 for m in enriched.values() if m.get("linkedin"))
    facebook_count = sum(1 for m in enriched.values() if m.get("facebook"))
    contact_count = sum(1 for m in enriched.values() if m.get("contacts"))

    print(f"\n[{slug}] Enrichment complete:")
    print(f"  Total members: {len(enriched)}")
    print(f"  With LinkedIn: {linkedin_count}")
    print(f"  With Facebook: {facebook_count}")
    print(f"  With contacts: {contact_count}")


async def run(args):
    """Main async entry point."""
    from playwright.async_api import async_playwright

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # If we're in the chambers/ folder, base_dir is the parent
    # Adjust if leads/ is a sibling of chambers/
    if not os.path.exists(os.path.join(base_dir, "leads")):
        # Try current working directory structure
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(base_dir)  # Go up one level from chambers/

    # Load all directory members
    all_members = load_directory_members(base_dir)

    # Get unique chamber slugs
    chamber_slugs = sorted(set(m.get("chamber_slug", "") for m in all_members if m.get("chamber_slug")))

    if args.chamber:
        if args.chamber not in chamber_slugs:
            print(f"[ERROR] Chamber slug '{args.chamber}' not found in members file")
            print(f"[INFO] Available slugs: {', '.join(chamber_slugs)}")
            sys.exit(1)
        chambers_to_process = [args.chamber]
    elif args.all:
        chambers_to_process = chamber_slugs
    else:
        print("[ERROR] Specify --chamber SLUG or --all")
        sys.exit(1)

    print(f"[START] Detail enrichment for {len(chambers_to_process)} chamber(s)")

    # Graceful shutdown handler
    shutdown_requested = False
    enrichment_path_ref = [None]
    enriched_ref = [None]

    def signal_handler(sig, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        print("\n[INTERRUPTED] Saving checkpoint and exiting...")
        if enrichment_path_ref[0] and enriched_ref[0]:
            save_enrichment_file(enrichment_path_ref[0], enriched_ref[0])
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

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

        for slug in chambers_to_process:
            if shutdown_requested:
                break

            chamber_members = [m for m in all_members if m.get("chamber_slug") == slug]
            enrichment_path = get_enrichment_path(base_dir, slug)
            enrichment_path_ref[0] = enrichment_path

            print(f"\n{'='*60}")
            print(f"Enriching: {slug} ({len(chamber_members)} members)")
            print(f"Output: {enrichment_path}")
            print(f"{'='*60}")

            await enrich_chamber(page, chamber_members, enrichment_path, slug, args.delay)

        await browser.close()

    print(f"\n[DONE] Detail enrichment complete for {len(chambers_to_process)} chamber(s)")


def main():
    parser = argparse.ArgumentParser(description="Chamber Detail Page Enrichment Scraper")
    parser.add_argument("--chamber", help="Enrich a single chamber by slug")
    parser.add_argument("--all", action="store_true", help="Enrich all chambers")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests (default: 1.5s)")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
