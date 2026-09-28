#!/usr/bin/env python3
"""
Full Website Transformation Pipeline

Takes a prospect's website URL and produces a luxury redesign with
cinematic animations, deployed to a live preview URL.

Pipeline steps:
  1. Capture — Firecrawl scrape (HTML + screenshot + branding)
  2. Analyze — Score current design, identify gaps
  3. Generate — Claude API redesign with component library
  4. Animate — Inject video hero, scroll reveals, canvas effects
  5. Deploy — Push to GitHub Pages or local preview

Usage:
    # Full pipeline from URL
    python website/full_pipeline.py --url "https://example.com" --slug example-corp

    # Skip capture, start from existing HTML
    python website/full_pipeline.py --html .tmp/captures/example/page.html --slug example-corp

    # Specific industry + animation style
    python website/full_pipeline.py --url "https://example.com" --slug example-corp \
        --industry finance --effect cinematic-full --deploy github

    # Local preview only
    python website/full_pipeline.py --url "https://example.com" --slug example-corp \
        --effect video-hero --deploy local --port 8080
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Windows UTF-8 fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add parent to path for lib imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# Add website dir for sibling imports
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from lib.safe_io import safe_json_write, safe_json_read


def detect_industry(slug, branding=None):
    """Auto-detect industry from slug keywords."""
    slug_lower = slug.lower()

    industry_keywords = {
        'finance': ['finance', 'bank', 'invest', 'capital', 'venture', 'risk', 'trading', 'wealth'],
        'law': ['law', 'legal', 'attorney', 'lawyer', 'counsel'],
        'real-estate': ['real-estate', 'realty', 'property', 'home', 'house', 'mortgage'],
        'tech': ['tech', 'ai', 'saas', 'software', 'digital', 'data', 'automation', 'cloud', 'app'],
        'construction': ['construct', 'roofing', 'roof', 'build', 'plumb', 'hvac', 'electric', 'trade'],
        'hospitality': ['food', 'restaurant', 'hotel', 'cider', 'organic', 'farm', 'cafe', 'bar'],
        'medspa': ['medspa', 'beauty', 'wellness', 'spa', 'aesthetic', 'skin', 'dental'],
        'consulting': ['consult', 'coach', 'advisor', 'strategy'],
    }

    for industry, keywords in industry_keywords.items():
        if any(kw in slug_lower for kw in keywords):
            return industry

    return 'tech'  # default


def full_pipeline(
    url=None,
    html_path=None,
    slug=None,
    industry=None,
    style=None,
    effect='video-hero',
    brand_color=None,
    hero_image=None,
    deploy_method=None,
    deploy_repo=None,
    deploy_port=8080,
    output_dir='.tmp',
    skip_capture=False,
    skip_analyze=False,
    skip_generate=False,
    skip_animate=False,
):
    """
    Complete pipeline: capture → analyze → generate → animate → deploy.

    Returns dict with all intermediate paths and the final live URL.
    """
    results = {
        'slug': slug,
        'url': url,
        'steps_completed': [],
        'live_url': None,
        'brand_color': brand_color,
        'html_path': None,
        'errors': [],
    }

    start_time = time.time()
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70)
    print("  WEBSITE TRANSFORMATION PIPELINE")
    print(f"  URL: {url or '(from input HTML)'}")
    print(f"  Slug: {slug}")
    print(f"  Effect: {effect}")
    print(f"  Industry: {industry or '(auto-detect)'}")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────────────────
    # STEP 1: Capture website (Firecrawl)
    # ──────────────────────────────────────────────────────────────────────
    capture_dir = os.path.join(output_dir, 'captures', slug)
    branding_path = os.path.join(capture_dir, 'branding.json')
    captured_html = os.path.join(capture_dir, 'page.html')

    if html_path:
        print(f"\n[1/5] CAPTURE — skipped (using input: {html_path})")
        captured_html = html_path
        results['steps_completed'].append('capture_skipped')
    elif skip_capture:
        print(f"\n[1/5] CAPTURE — skipped")
        if os.path.exists(captured_html):
            print(f"  Using existing: {captured_html}")
        results['steps_completed'].append('capture_skipped')
    else:
        print(f"\n[1/5] CAPTURE — scraping {url}")
        try:
            from capture_site import capture_website
            cap_result = capture_website(url, slug, capture_dir)
            print(f"  HTML: {cap_result.get('html_path', 'N/A')}")
            print(f"  Screenshot: {cap_result.get('screenshot_path', 'N/A')}")

            # Extract brand color from branding
            if not brand_color and os.path.exists(branding_path):
                branding = safe_json_read(branding_path)
                if branding:
                    brand_color = branding.get('primary_color') or branding.get('accent_color')
                    results['brand_color'] = brand_color

            results['steps_completed'].append('capture')
        except Exception as e:
            print(f"  ERROR: {e}")
            results['errors'].append(f"capture: {e}")
            if not os.path.exists(captured_html):
                print("  FATAL: No HTML to work with. Pipeline stopped.")
                return results

    # Default brand color
    if not brand_color:
        brand_color = '#FF3B30'
        results['brand_color'] = brand_color
        print(f"  Using default brand color: {brand_color}")

    # Auto-detect industry
    if not industry:
        industry = detect_industry(slug)
        print(f"  Auto-detected industry: {industry}")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 2: Analyze current design
    # ──────────────────────────────────────────────────────────────────────
    analysis_path = os.path.join(output_dir, 'analysis', f'{slug}.json')

    if skip_analyze:
        print(f"\n[2/5] ANALYZE — skipped")
        results['steps_completed'].append('analyze_skipped')
    else:
        print(f"\n[2/5] ANALYZE — scoring current design")
        try:
            from analyze_site import analyze_website
            analysis = analyze_website(
                captured_html,
                branding_path if os.path.exists(branding_path) else None
            )
            os.makedirs(os.path.dirname(analysis_path), exist_ok=True)
            safe_json_write(analysis_path, analysis)

            score = analysis.get('scores', {}).get('overall', '?')
            gaps = len(analysis.get('gaps', []))
            print(f"  Overall score: {score}/10")
            print(f"  Gaps identified: {gaps}")
            results['steps_completed'].append('analyze')
        except Exception as e:
            print(f"  ERROR: {e}")
            results['errors'].append(f"analyze: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 3: Generate redesign (Claude API)
    # ──────────────────────────────────────────────────────────────────────
    redesign_path = os.path.join(output_dir, 'redesigns', f'{slug}-redesign.html')

    if skip_generate:
        print(f"\n[3/5] GENERATE — skipped")
        redesign_path = captured_html  # use original
        results['steps_completed'].append('generate_skipped')
    else:
        print(f"\n[3/5] GENERATE — creating redesign via Claude")
        try:
            from generate_redesign import generate_redesign

            gen_result = generate_redesign(
                slug=slug,
                analysis_path=analysis_path if os.path.exists(analysis_path) else None,
                industry=industry,
                style=style,
                output_path=redesign_path,
            )
            redesign_path = gen_result.get('html_path', redesign_path)
            print(f"  Output: {redesign_path}")
            results['steps_completed'].append('generate')
        except Exception as e:
            print(f"  ERROR: {e}")
            results['errors'].append(f"generate: {e}")
            redesign_path = captured_html  # fallback to original

    results['html_path'] = redesign_path

    if not os.path.exists(redesign_path):
        print(f"\n  FATAL: HTML not found: {redesign_path}")
        return results

    # ──────────────────────────────────────────────────────────────────────
    # STEP 4: Animate with cinematic effects
    # ──────────────────────────────────────────────────────────────────────
    animated_path = os.path.join(output_dir, 'animated', f'{slug}-{effect}.html')

    if skip_animate:
        print(f"\n[4/5] ANIMATE — skipped")
        animated_path = redesign_path
        results['steps_completed'].append('animate_skipped')
    else:
        print(f"\n[4/5] ANIMATE — applying {effect} effect")
        try:
            from animate_page import animate_page

            os.makedirs(os.path.dirname(animated_path), exist_ok=True)
            animate_page(
                redesign_path, effect, brand_color, animated_path,
                hero_image=hero_image
            )
            size_kb = os.path.getsize(animated_path) / 1024
            print(f"  Output: {animated_path} ({size_kb:.0f}KB)")
            results['steps_completed'].append('animate')
        except Exception as e:
            print(f"  ERROR: {e}")
            results['errors'].append(f"animate: {e}")
            animated_path = redesign_path

    results['html_path'] = animated_path

    # ──────────────────────────────────────────────────────────────────────
    # STEP 5: Deploy
    # ──────────────────────────────────────────────────────────────────────
    if deploy_method:
        print(f"\n[5/5] DEPLOY — {deploy_method}")
        try:
            from deploy_site import deploy

            deploy_result = deploy(
                slug=slug,
                html_path=animated_path,
                method=deploy_method,
                repo=deploy_repo,
                port=deploy_port,
            )
            results['live_url'] = deploy_result.get('url')
            print(f"  Live URL: {results['live_url']}")
            results['steps_completed'].append('deploy')
        except Exception as e:
            print(f"  ERROR: {e}")
            results['errors'].append(f"deploy: {e}")
    else:
        print(f"\n[5/5] DEPLOY — skipped (use --deploy github|local)")
        results['steps_completed'].append('deploy_skipped')

    # ──────────────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"  PIPELINE COMPLETE — {elapsed:.1f}s")
    print(f"  Steps: {', '.join(results['steps_completed'])}")
    print(f"  Final HTML: {results['html_path']}")
    if results['live_url']:
        print(f"  Live URL: {results['live_url']}")
    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
        for err in results['errors']:
            print(f"    - {err}")
    print("=" * 70)

    # Save pipeline results
    results_path = os.path.join(output_dir, 'pipeline', f'{slug}-results.json')
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    safe_json_write(results_path, results)

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Full website transformation pipeline'
    )
    parser.add_argument('--url', help='Website URL to transform')
    parser.add_argument('--html', help='Existing HTML file (skip capture)')
    parser.add_argument('--slug', required=True, help='Project slug (e.g., example-corp)')
    parser.add_argument('--industry', help='Industry: finance, tech, construction, hospitality, medspa, real-estate')
    parser.add_argument('--style', help='Inspiration style: populon, delta-vega, driveby, dunkertons, teamsiok, ezhomes')
    parser.add_argument('--effect', default='video-hero',
                        choices=['video-hero', 'image-hero', 'scroll-reveals',
                                 'dot-rhombus', 'particle-torus', 'cinematic-full'],
                        help='Animation effect (default: video-hero)')
    parser.add_argument('--brand-color', help='Brand hex color (auto-detected if not set)')
    parser.add_argument('--hero-image', help='Hero image URL for image-hero effect')
    parser.add_argument('--deploy', dest='deploy_method', choices=['github', 'local'],
                        help='Deployment method')
    parser.add_argument('--repo', help='GitHub deploy repo (for --deploy github)')
    parser.add_argument('--port', type=int, default=8080, help='Local server port (for --deploy local)')
    parser.add_argument('--output-dir', default='.tmp', help='Output directory (default: .tmp)')
    parser.add_argument('--skip-capture', action='store_true')
    parser.add_argument('--skip-analyze', action='store_true')
    parser.add_argument('--skip-generate', action='store_true')
    parser.add_argument('--skip-animate', action='store_true')

    args = parser.parse_args()

    if not args.url and not args.html:
        parser.error("Either --url or --html is required")

    result = full_pipeline(
        url=args.url,
        html_path=args.html,
        slug=args.slug,
        industry=args.industry,
        style=args.style,
        effect=args.effect,
        brand_color=args.brand_color,
        hero_image=args.hero_image,
        deploy_method=args.deploy_method,
        deploy_repo=args.repo,
        deploy_port=args.port,
        output_dir=args.output_dir,
        skip_capture=args.skip_capture,
        skip_analyze=args.skip_analyze,
        skip_generate=args.skip_generate,
        skip_animate=args.skip_animate,
    )

    if result.get('errors'):
        sys.exit(1)


if __name__ == '__main__':
    main()
