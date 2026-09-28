#!/usr/bin/env python3
"""Chamber Platform Auto-Detection

Detects chamber directory platform from URL patterns and HTML content.
Returns one of: growthzone, chambermaster, atlas, wordpress, locable, wix, custom.

Usage:
    python platform_detector.py https://business.olathe.org/list
    python platform_detector.py https://greaterkansascitychamberofcommerce-dev.growthzoneapp.com/memberdirectory
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import requests
from urllib.parse import urlparse


def detect_platform(url: str) -> str:
    """Detect chamber platform from URL patterns and HTML content.

    Detection order:
    1. URL-based (fast, no HTTP needed)
    2. Path-based heuristics
    3. HTML-based (requires HTTP request)

    Returns: one of growthzone, chambermaster, atlas, wordpress, locable, wix, custom
    """
    url_lower = url.lower()

    # --- URL-based detection (fast, no HTTP request needed) ---
    if "growthzoneapp.com" in url_lower or "gz." in url_lower:
        return "growthzone"
    if "chambermaster.com" in url_lower or "cm.business" in url_lower:
        return "chambermaster"
    if "/atlas/" in url_lower or "weblinkconnect.com" in url_lower:
        return "atlas"

    # --- Path-based detection ---
    parsed = urlparse(url)
    path = parsed.path.lower()

    # ChamberMaster typically uses /list endpoint on a business. subdomain
    if "/list" in path and ("chambermaster" in url_lower or "cm." in url_lower):
        return "chambermaster"

    # /memberdirectory and /directory are common GrowthZone patterns
    if "/memberdirectory" in path or "/directory" in path:
        # Could be GrowthZone — confirm via HTML if possible, default to growthzone
        return "growthzone"

    # --- HTML-based detection (requires HTTP request) ---
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        html = resp.text[:50000].lower()

        # GrowthZone / ChamberMaster share gz-* CSS classes
        # Distinguish by URL patterns: /list = ChamberMaster, /memberdirectory = GrowthZone
        if "gz-results-card" in html or "gz-directory-card" in html:
            if "/list" in path:
                return "chambermaster"
            return "growthzone"

        # Atlas Angular SPA markers
        if "atlas" in html and "h2" in html and "mb-15" in html:
            return "atlas"

        # Locable platform
        if "powered by locable" in html:
            return "locable"

        # Wix platform
        if "wix.com" in html or "_wix_browser_sess" in html:
            return "wix"

        # WordPress detection
        if "wp-content" in html or 'name="generator" content="wordpress' in html:
            return "wordpress"

        # Additional GrowthZone markers (sometimes gz classes appear differently)
        if "growthzone" in html or "growthzoneapp" in html:
            return "growthzone"

        # Additional ChamberMaster markers
        if "chambermaster" in html:
            return "chambermaster"

        # Check final redirect URL for platform clues
        final_url = resp.url.lower()
        if "growthzoneapp.com" in final_url:
            return "growthzone"
        if "chambermaster.com" in final_url or "cm.business" in final_url:
            return "chambermaster"
        if "weblinkconnect.com" in final_url:
            return "atlas"

    except requests.exceptions.Timeout:
        print(f"[WARN] Timeout connecting to {url}", file=sys.stderr)
    except requests.exceptions.ConnectionError:
        print(f"[WARN] Connection error for {url}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] Detection error for {url}: {e}", file=sys.stderr)

    return "custom"


def suggest_scraper(platform: str) -> str:
    """Suggest which scraper script to use for a given platform."""
    suggestions = {
        "growthzone": "scrape_directory.py (A-Z alpha navigation with FindStartsWith)",
        "chambermaster": "scrape_directory.py (A-Z alpha navigation with searchalpha)",
        "atlas": "scrape_atlas_api.py (REST API with Playwright token capture)",
        "wordpress": "scrape_directory.py --generic (fallback CSS selectors) or scrape_deep.py (multi-level)",
        "locable": "scrape_directory.py --generic",
        "wix": "scrape_directory.py --generic",
        "custom": "scrape_deep.py (multi-level) or manual inspection needed",
    }
    return suggestions.get(platform, "Manual inspection needed")


def detect_from_config(config_path: str) -> list:
    """Detect platforms for all chambers in a config file.

    Returns list of dicts with slug, name, detected_platform, suggested_scraper.
    """
    import json
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    results = []
    for chamber in config.get("chambers", []):
        url = chamber.get("directory_url", "")
        slug = chamber.get("slug", "unknown")
        name = chamber.get("name", "Unknown")

        if not url:
            results.append({
                "slug": slug,
                "name": name,
                "detected_platform": "unknown",
                "suggested_scraper": "No directory URL provided",
                "url": url,
            })
            continue

        print(f"Detecting: {name} ({url})...")
        platform = detect_platform(url)
        results.append({
            "slug": slug,
            "name": name,
            "detected_platform": platform,
            "suggested_scraper": suggest_scraper(platform),
            "url": url,
        })

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Detect chamber platform type")
    parser.add_argument("url", nargs="?", help="Chamber directory URL to detect")
    parser.add_argument("--config", help="Path to chambers.json config file (detect all)")
    args = parser.parse_args()

    if args.config:
        results = detect_from_config(args.config)
        print(f"\n{'='*70}")
        print(f"{'Chamber':<35} {'Platform':<15} {'Scraper'}")
        print(f"{'='*70}")
        for r in results:
            print(f"{r['name'][:34]:<35} {r['detected_platform']:<15} {r['suggested_scraper'][:40]}")
    elif args.url:
        platform = detect_platform(args.url)
        print(f"Platform: {platform}")
        print(f"Suggested scraper: {suggest_scraper(platform)}")
    else:
        parser.print_help()
        sys.exit(1)
