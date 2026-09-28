#!/usr/bin/env python3
"""
Unified batch pipeline: run all 3 use cases for a prospect in one command.

  UC1: Website Redesign     → {slug}.preview.florianrolke.com
  UC2: Voice Widget         → {slug}-chat.preview.florianrolke.com
  UC3: Custom Landing Page  → {slug}.client.of.florianrolke.com

Pipeline:
  1. Capture website (Firecrawl: screenshot + HTML + branding)
  2. UC1: Generate redesign (v0) → deploy
  3. UC2: Build widget page (iframe + Retell) → deploy
  4. UC3: Research (Perplexity) → Generate landing page (v0) → deploy

Usage:
    # Single prospect
    python batch_all.py --url https://delta-vega.com --slug delta-vega

    # Skip capture if already done
    python batch_all.py --url https://delta-vega.com --slug delta-vega --skip-capture

    # Only run specific use cases
    python batch_all.py --url https://delta-vega.com --slug delta-vega --only redesign,landing

    # Use v0 generator (default) or stitch
    python batch_all.py --url https://delta-vega.com --slug delta-vega --generator v0
"""

import os
import sys
import time
import argparse
import subprocess
import re
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

PROJECT_ROOT = Path(__file__).parent


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60]


def run_script(cmd, label, timeout=300):
    """Run a Python script via subprocess and return success/failure."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        elapsed = time.time() - start

        # Print stdout
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                print(f"  {line}")

        if result.returncode != 0:
            print(f"\n  FAILED ({elapsed:.0f}s)")
            if result.stderr:
                for line in result.stderr.strip().split('\n')[-10:]:
                    print(f"  ERR: {line}")
            return False

        print(f"\n  OK ({elapsed:.0f}s)")
        return True

    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def step_capture(url, slug):
    """Step 1: Capture website via Firecrawl."""
    return run_script(
        [sys.executable, "execution/capture_website_screenshot.py",
         "--url", url, "--lead-id", slug],
        f"CAPTURE: {slug} ({url})",
        timeout=120,
    )


def step_redesign(slug, generator='v0'):
    """Step 2 (UC1): Generate redesign via v0/stitch."""
    return run_script(
        [sys.executable, "execution/generate_redesign.py",
         "--slug", slug, "--generator", generator],
        f"UC1 REDESIGN: {slug} (generator={generator})",
        timeout=240,
    )


def step_deploy_redesign(slug):
    """Step 3 (UC1): Deploy redesign to preview subdomain."""
    html_file = f".tmp/redesigns/{slug}-redesign.html"
    if not os.path.exists(html_file):
        print(f"  SKIP deploy: no file at {html_file}")
        return False
    return run_script(
        [sys.executable, "execution/deploy_redesign.py",
         "--slug", slug,
         "--html-file", html_file,
         "--deploy-type", "redesign"],
        f"DEPLOY UC1: {slug}.preview.florianrolke.com",
        timeout=120,
    )


def step_widget(url, slug):
    """Step 4 (UC2): Build widget page (iframe + Retell)."""
    # First, try to set up a Retell agent (may fail if no API key / no facts)
    run_script(
        [sys.executable, "widget-demo/setup_retell_agent.py",
         "--slug", slug],
        f"UC2 RETELL AGENT: {slug}",
        timeout=60,
    )

    # Build the widget page (works even without Retell agent — uses placeholder)
    return run_script(
        [sys.executable, "widget-demo/build_widget_page.py",
         "--url", url, "--slug", slug],
        f"UC2 WIDGET PAGE: {slug}",
        timeout=90,
    )


def step_deploy_widget(slug):
    """Step 5 (UC2): Deploy widget to preview subdomain."""
    html_file = f"widget-demo/output/{slug}-chat/index.html"
    if not os.path.exists(html_file):
        print(f"  SKIP deploy: no file at {html_file}")
        return False
    return run_script(
        [sys.executable, "execution/deploy_redesign.py",
         "--slug", slug,
         "--html-file", html_file,
         "--deploy-type", "widget"],
        f"DEPLOY UC2: {slug}-chat.preview.florianrolke.com",
        timeout=120,
    )


def step_research(url, slug):
    """Step 6 (UC3): Deep research via Firecrawl + Perplexity."""
    return run_script(
        [sys.executable, "landing-page-demo/research_client.py",
         "--url", url, "--slug", slug],
        f"UC3 RESEARCH: {slug}",
        timeout=120,
    )


def step_landing_page(slug, generator='v0'):
    """Step 7 (UC3): Generate landing page from research brief."""
    return run_script(
        [sys.executable, "landing-page-demo/generate_landing_page.py",
         "--slug", slug, "--generator", generator],
        f"UC3 LANDING PAGE: {slug} (generator={generator})",
        timeout=240,
    )


def step_deploy_landing(slug):
    """Step 8 (UC3): Deploy landing page to client.of subdomain."""
    html_file = f"landing-page-demo/output/{slug}/index.html"
    if not os.path.exists(html_file):
        print(f"  SKIP deploy: no file at {html_file}")
        return False
    return run_script(
        [sys.executable, "execution/deploy_redesign.py",
         "--slug", slug,
         "--html-file", html_file,
         "--deploy-type", "landing"],
        f"DEPLOY UC3: {slug}.client.of.florianrolke.com",
        timeout=120,
    )


def main():
    parser = argparse.ArgumentParser(
        description='Run all 3 use cases for a prospect in one command')
    parser.add_argument('--url', required=True, help='Prospect website URL')
    parser.add_argument('--slug', help='Site identifier (auto-derived from URL if omitted)')
    parser.add_argument('--generator', default='v0', choices=['v0', 'stitch'],
                        help='AI generator for redesign + landing page (default: v0)')
    parser.add_argument('--skip-capture', action='store_true',
                        help='Skip Firecrawl capture (if already done)')
    parser.add_argument('--skip-deploy', action='store_true',
                        help='Generate only, skip all deployments')
    parser.add_argument('--only', default='',
                        help='Comma-separated use cases to run: redesign,widget,landing (default: all)')

    args = parser.parse_args()

    # Derive slug from URL if not provided
    if not args.slug:
        from urllib.parse import urlparse
        domain = urlparse(args.url).netloc.replace('www.', '')
        args.slug = slugify(domain.split('.')[0])

    slug = args.slug
    url = args.url

    # Parse --only filter
    if args.only:
        use_cases = set(args.only.lower().split(','))
    else:
        use_cases = {'redesign', 'widget', 'landing'}

    total_start = time.time()
    results = {}

    print(f"\n{'#'*60}")
    print(f"  BATCH ALL: {slug}")
    print(f"  URL: {url}")
    print(f"  Use cases: {', '.join(sorted(use_cases))}")
    print(f"  Generator: {args.generator}")
    print(f"{'#'*60}")

    # ── Step 1: Capture ──────────────────────────────────────────
    if not args.skip_capture:
        branding_exists = os.path.exists(f".tmp/branding/{slug}.json")
        if branding_exists:
            print(f"\n  Branding data already exists for {slug}, skipping capture.")
            results['capture'] = True
        else:
            results['capture'] = step_capture(url, slug)
    else:
        print(f"\n  Skipping capture (--skip-capture)")
        results['capture'] = True

    # ── UC1: Redesign ────────────────────────────────────────────
    if 'redesign' in use_cases:
        results['redesign'] = step_redesign(slug, args.generator)
        if results['redesign'] and not args.skip_deploy:
            results['deploy_redesign'] = step_deploy_redesign(slug)

    # ── UC2: Widget ──────────────────────────────────────────────
    if 'widget' in use_cases:
        results['widget'] = step_widget(url, slug)
        if results['widget'] and not args.skip_deploy:
            results['deploy_widget'] = step_deploy_widget(slug)

    # ── UC3: Landing Page ────────────────────────────────────────
    if 'landing' in use_cases:
        results['research'] = step_research(url, slug)
        if results.get('research'):
            results['landing'] = step_landing_page(slug, args.generator)
            if results.get('landing') and not args.skip_deploy:
                results['deploy_landing'] = step_deploy_landing(slug)

    # ── Summary ──────────────────────────────────────────────────
    total_elapsed = time.time() - total_start

    print(f"\n{'#'*60}")
    print(f"  RESULTS: {slug}")
    print(f"{'#'*60}\n")

    for step, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {step:25s}  {status}")

    print(f"\n  Total time: {total_elapsed:.0f}s")

    # Print live URLs
    print(f"\n  Live URLs:")
    if results.get('deploy_redesign'):
        print(f"    UC1 Redesign:     https://{slug}.preview.florianrolke.com")
    if results.get('deploy_widget'):
        print(f"    UC2 Widget:       https://{slug}-chat.preview.florianrolke.com")
    if results.get('deploy_landing'):
        print(f"    UC3 Landing Page: https://{slug}.client.of.florianrolke.com")

    # Print local file paths for review
    print(f"\n  Local files:")
    if 'redesign' in use_cases:
        print(f"    UC1: .tmp/redesigns/{slug}-redesign.html")
    if 'widget' in use_cases:
        print(f"    UC2: widget-demo/output/{slug}-chat/index.html")
    if 'landing' in use_cases:
        print(f"    UC3: landing-page-demo/output/{slug}/index.html")

    print()

    # Return 0 if all steps succeeded, 1 if any failed
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
