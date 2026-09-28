#!/usr/bin/env python3
"""
Skill 1: Exact Website Clone

Creates a 1:1 pixel-perfect copy of a website on your domain.
Uses Firecrawl to scrape full HTML, strips tracking/analytics,
preserves layout, fonts, images, and colors.

Output: .tmp/clones/{slug}/index.html

Usage:
    python execution/clone_website.py --url "https://example.com" --slug example
    python execution/clone_website.py --url "https://example.com" --slug example --deploy
"""

import os
import sys
import re
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

CLONE_DIR = ".tmp/clones"

# Tracking/analytics scripts to strip
TRACKING_PATTERNS = [
    r'<script[^>]*google-analytics\.com[^>]*>.*?</script>',
    r'<script[^>]*googletagmanager\.com[^>]*>.*?</script>',
    r'<script[^>]*gtag/js[^>]*>.*?</script>',
    r'<script[^>]*facebook\.net[^>]*>.*?</script>',
    r'<script[^>]*fbevents\.js[^>]*>.*?</script>',
    r'<script[^>]*hotjar\.com[^>]*>.*?</script>',
    r'<script[^>]*clarity\.ms[^>]*>.*?</script>',
    r'<script[^>]*segment\.com[^>]*>.*?</script>',
    r'<script[^>]*mixpanel\.com[^>]*>.*?</script>',
    r'<script[^>]*intercom\.io[^>]*>.*?</script>',
    r'<script[^>]*crisp\.chat[^>]*>.*?</script>',
    r'<script[^>]*hubspot\.com[^>]*>.*?</script>',
    r'<script[^>]*drift\.com[^>]*>.*?</script>',
    r'<!-- Google Tag Manager -->.*?<!-- End Google Tag Manager -->',
    r'<!-- Google Tag Manager \(noscript\) -->.*?<!-- End Google Tag Manager \(noscript\) -->',
]


def strip_tracking_scripts(html: str) -> str:
    """Remove tracking, analytics, and third-party chat scripts."""
    for pattern in TRACKING_PATTERNS:
        html = re.sub(pattern, '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove empty noscript blocks left behind
    html = re.sub(r'<noscript>\s*</noscript>', '', html, flags=re.DOTALL)

    return html


def clone_website(url: str, slug: str, deploy: bool = False) -> dict:
    """
    Clone a website using Firecrawl.

    Args:
        url: Website URL to clone
        slug: Identifier for output files
        deploy: If True, deploy to live server after cloning

    Returns:
        dict with: html_path, screenshot_path, branding_path, error
    """
    from firecrawl import Firecrawl
    from firecrawl.v2.types import ScreenshotFormat

    result = {"html_path": None, "screenshot_path": None, "branding_path": None, "error": None}

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        result["error"] = "FIRECRAWL_API_KEY not set in .env"
        print(f"ERROR: {result['error']}")
        return result

    # Create output directory
    clone_dir = os.path.join(CLONE_DIR, slug)
    os.makedirs(clone_dir, exist_ok=True)

    print(f"Cloning {url} → {clone_dir}/")

    try:
        firecrawl = Firecrawl(api_key=api_key)
        screenshot_fmt = ScreenshotFormat(type="screenshot", full_page=True)

        # Single API call: HTML + branding + screenshot
        print("  Scraping with Firecrawl...")
        scrape_result = firecrawl.scrape(
            url=url,
            formats=["rawHtml", "html", "branding", screenshot_fmt],
            only_main_content=False,
            timeout=120000,
            wait_for=3000,
        )

        # Extract HTML — prefer rawHtml (includes <head>) over html (body only)
        html = getattr(scrape_result, 'rawHtml', None) or getattr(scrape_result, 'raw_html', None) or scrape_result.html or ""
        if not html or len(html) < 100:
            result["error"] = f"Firecrawl returned too little HTML ({len(html)} chars)"
            print(f"ERROR: {result['error']}")
            return result

        print(f"  Got {len(html)} chars of HTML")

        # Strip tracking scripts
        html = strip_tracking_scripts(html)
        print(f"  Stripped tracking scripts → {len(html)} chars")

        # Save HTML
        html_path = os.path.join(clone_dir, "index.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        result["html_path"] = html_path
        print(f"  Saved: {html_path}")

        # Save branding data
        branding = getattr(scrape_result, 'branding', None)
        if branding:
            branding_path = os.path.join(clone_dir, "branding.json")
            branding_dict = branding if isinstance(branding, dict) else branding.dict() if hasattr(branding, 'dict') else {}
            with open(branding_path, 'w', encoding='utf-8') as f:
                json.dump(branding_dict, f, indent=2, ensure_ascii=False)
            result["branding_path"] = branding_path
            print(f"  Saved branding: {branding_path}")

        # Save screenshot
        screenshot_url = scrape_result.screenshot
        if screenshot_url:
            import requests
            img_resp = requests.get(screenshot_url, timeout=30)
            img_resp.raise_for_status()
            screenshot_path = os.path.join(clone_dir, "screenshot.png")
            with open(screenshot_path, 'wb') as f:
                f.write(img_resp.content)
            result["screenshot_path"] = screenshot_path
            print(f"  Saved screenshot: {screenshot_path}")

        print(f"Clone complete: {clone_dir}/index.html")

        # Deploy if requested
        if deploy:
            print(f"\n  Deploying {slug} to live server...")
            import subprocess
            deploy_cmd = [
                sys.executable, "execution/deploy_redesign.py",
                "--slug", slug,
                "--html-file", html_path,
            ]
            proc = subprocess.run(deploy_cmd, capture_output=True, text=True, timeout=300,
                                  encoding='utf-8', errors='replace')
            if proc.returncode == 0:
                print(f"  Deployed to: {slug}.preview.florianrolke.com")
            else:
                print(f"  Deploy failed: {proc.stderr[:500]}")

    except Exception as e:
        result["error"] = str(e)
        print(f"ERROR: {e}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clone a website 1:1 using Firecrawl")
    parser.add_argument("--url", required=True, help="Website URL to clone")
    parser.add_argument("--slug", required=True, help="Slug for output directory")
    parser.add_argument("--deploy", action="store_true", help="Deploy to live server after cloning")

    args = parser.parse_args()
    result = clone_website(args.url, args.slug, deploy=args.deploy)

    if result["error"]:
        sys.exit(1)
