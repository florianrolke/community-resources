#!/usr/bin/env python3
"""
Full Transformation Pipeline — "The NexGen Treatment"

Takes any website URL and produces a single killer page with:
  1. AI-generated redesign (v0/Gemini)
  2. Video hero animation (Skill 5)
  3. Embedded voice widget (GHL/Retell)
  4. Deployed to live preview URL
  5. Before/after comparison image
  6. (Optional) Cold outreach email

This chains 7 existing scripts into one command:
  scrape → generate → animate → widget → deploy → comparison → outreach

Differs from batch_all.py (breadth: 3 deliverables) — this is depth (1 killer page).

Usage:
    # Full pipeline from URL
    python execution/full_transformation.py \\
      --url "https://nexgenroofing.com.au" \\
      --slug nexgen-roofing \\
      --effect video-hero \\
      --widget-type ghl

    # Skip scrape+generate, start from existing HTML
    python execution/full_transformation.py \\
      --input .tmp/redesigns/delta-vega-improved.html \\
      --slug delta-vega-full \\
      --effect video-hero \\
      --widget-type ghl \\
      --brand-color "#09240F"

    # Full pipeline with outreach
    python execution/full_transformation.py \\
      --url "https://example.com" \\
      --slug example \\
      --effect cinematic-full \\
      --widget-type ghl \\
      --send-email \\
      --email "owner@example.com" \\
      --name "John" \\
      --company "Example Corp" \\
      --sender-name "Will Coates"
"""

import os
import sys
import re
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Add execution directory to import path
sys.path.insert(0, os.path.dirname(__file__))


def slugify(text):
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'https?://', '', text)
    text = re.sub(r'www\.', '', text)
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')[:60]


def detect_video_category(slug, branding_data=None):
    """Auto-detect video category from slug or branding keywords."""
    slug_lower = slug.lower()

    tech_words = ['tech', 'ai', 'saas', 'software', 'digital', 'data', 'automation', 'cloud']
    nature_words = ['food', 'organic', 'cider', 'farm', 'garden', 'nature', 'wellness', 'health']
    city_words = ['real-estate', 'property', 'roofing', 'construction', 'urban', 'consulting']
    finance_words = ['finance', 'bank', 'invest', 'capital', 'venture', 'risk', 'trading']
    code_words = ['dev', 'engineer', 'code', 'github', 'api']

    for words, cat in [
        (tech_words, 'tech'), (nature_words, 'nature'), (city_words, 'city'),
        (finance_words, 'finance'), (code_words, 'code')
    ]:
        if any(w in slug_lower for w in words):
            return cat

    return 'abstract'


def full_transformation(
    url=None,
    slug=None,
    input_html=None,
    effect='video-hero',
    widget_type='ghl',
    brand_color=None,
    video_category=None,
    hero_image=None,
    generator='v0',
    send_email=False,
    email=None,
    name=None,
    company=None,
    sender_name='Will Coates',
    skip_scrape=False,
    skip_generate=False,
    skip_animate=False,
    skip_widget=False,
    skip_deploy=False,
    skip_comparison=False,
):
    """
    Complete pipeline: scrape → generate → animate → widget → deploy → comparison → outreach.

    Returns:
        dict with live_url, comparison_path, brand_color, all intermediate paths
    """
    results = {
        'slug': slug,
        'url': url,
        'steps_completed': [],
        'live_url': None,
        'comparison_path': None,
        'brand_color': brand_color,
        'html_path': None,
        'screenshot_before': None,
    }

    start_time = time.time()

    print("=" * 70)
    print("  FULL TRANSFORMATION PIPELINE")
    print(f"  URL: {url or '(from input HTML)'}")
    print(f"  Slug: {slug}")
    print(f"  Effect: {effect}")
    print(f"  Widget: {widget_type}")
    print(f"  Generator: {generator}")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────────────────
    # STEP 1: Scrape (Firecrawl — screenshot + HTML + branding)
    # ──────────────────────────────────────────────────────────────────────
    if input_html:
        # Starting from existing HTML — skip scrape and generate
        print(f"\n[1/7] SCRAPE — skipped (using input: {input_html})")
        results['html_path'] = input_html
        results['steps_completed'].append('scrape_skipped')

        # Try to load branding if exists
        branding_path = f'.tmp/branding/{slug}.json'
        if os.path.exists(branding_path) and not brand_color:
            with open(branding_path, 'r', encoding='utf-8') as f:
                branding = json.load(f)
            brand_color = branding.get('colors', {}).get('primary', brand_color)
            results['brand_color'] = brand_color
            print(f"  Loaded brand color from branding: {brand_color}")

    elif skip_scrape:
        print(f"\n[1/7] SCRAPE — skipped (--skip-scrape)")
        results['steps_completed'].append('scrape_skipped')

        # Check for existing scrape data
        html_path = f'.tmp/html/{slug}.html'
        if os.path.exists(html_path):
            print(f"  Using existing HTML: {html_path}")
        else:
            print(f"  WARNING: No existing HTML at {html_path}")

        branding_path = f'.tmp/branding/{slug}.json'
        if os.path.exists(branding_path) and not brand_color:
            with open(branding_path, 'r', encoding='utf-8') as f:
                branding = json.load(f)
            brand_color = branding.get('colors', {}).get('primary', brand_color)
            results['brand_color'] = brand_color

    else:
        print(f"\n[1/7] SCRAPE — capturing {url}")
        from capture_website_screenshot import capture_website

        scrape_data = capture_website(url, lead_id=slug)
        if scrape_data.get('error'):
            print(f"  ERROR: {scrape_data['error']}")
            print("  Continuing without scrape data...")
        else:
            results['screenshot_before'] = scrape_data.get('screenshot_path') or scrape_data.get('fullpage_path')
            print(f"  Screenshot: {results['screenshot_before']}")
            print(f"  HTML: {scrape_data.get('html_path')}")
            print(f"  Branding: {scrape_data.get('branding_path')}")

            # Extract brand color from branding
            if not brand_color and scrape_data.get('branding_data'):
                branding = scrape_data['branding_data']
                if isinstance(branding, dict):
                    colors = branding.get('colors', branding.get('theme', {}))
                    if isinstance(colors, dict):
                        brand_color = colors.get('primary', colors.get('accent', None))
                    elif isinstance(colors, list) and colors:
                        brand_color = colors[0]
                results['brand_color'] = brand_color

        results['steps_completed'].append('scrape')

    # Default brand color if none detected
    if not brand_color:
        brand_color = '#FF3B30'
        results['brand_color'] = brand_color
        print(f"  Using default brand color: {brand_color}")
    else:
        print(f"  Brand color: {brand_color}")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 2: Generate Redesign (v0/Gemini/Stitch)
    # ──────────────────────────────────────────────────────────────────────
    redesign_path = results.get('html_path')

    if input_html:
        print(f"\n[2/7] GENERATE — skipped (using input HTML)")
        redesign_path = input_html
        results['steps_completed'].append('generate_skipped')

    elif skip_generate:
        print(f"\n[2/7] GENERATE — skipped (--skip-generate)")
        redesign_path = f'.tmp/redesigns/{slug}-redesign.html'
        if os.path.exists(redesign_path):
            print(f"  Using existing redesign: {redesign_path}")
        else:
            print(f"  WARNING: No existing redesign at {redesign_path}")
        results['steps_completed'].append('generate_skipped')

    else:
        print(f"\n[2/7] GENERATE — creating redesign via {generator}")
        from generate_redesign import generate_redesign as gen_redesign

        try:
            gen_result = gen_redesign(slug=slug, generator=generator)
            redesign_path = gen_result.get('html_path', f'.tmp/redesigns/{slug}-redesign.html')
            print(f"  Generated in {gen_result.get('elapsed_seconds', 0):.0f}s")
            print(f"  Output: {redesign_path}")
            results['steps_completed'].append('generate')
        except Exception as e:
            print(f"  ERROR generating redesign: {e}")
            print("  Pipeline cannot continue without HTML.")
            return results

    results['html_path'] = redesign_path

    if not redesign_path or not os.path.exists(redesign_path):
        print(f"\n  FATAL: HTML file not found: {redesign_path}")
        print("  Pipeline stopped.")
        return results

    # ──────────────────────────────────────────────────────────────────────
    # STEP 3: Animate with Video (Skill 5)
    # ──────────────────────────────────────────────────────────────────────
    animated_path = redesign_path  # fallback: use unamimated if skip

    if skip_animate:
        print(f"\n[3/7] ANIMATE — skipped (--skip-animate)")
        results['steps_completed'].append('animate_skipped')
    else:
        print(f"\n[3/7] ANIMATE — applying {effect} effect")
        from animate_static_page import animate_static_page

        # Determine video category
        vid_cat = video_category or detect_video_category(slug)
        print(f"  Video category: {vid_cat}")

        os.makedirs('.tmp/animated', exist_ok=True)
        animated_path = f'.tmp/animated/{slug}-{effect}.html'

        try:
            animate_static_page(redesign_path, effect, brand_color, animated_path, vid_cat,
                                hero_image=hero_image)
            file_size = os.path.getsize(animated_path) / 1024
            print(f"  Output: {animated_path} ({file_size:.0f}KB)")
            results['steps_completed'].append('animate')
        except Exception as e:
            print(f"  ERROR animating: {e}")
            print("  Continuing with unanimated HTML...")
            animated_path = redesign_path

    results['html_path'] = animated_path

    # ──────────────────────────────────────────────────────────────────────
    # STEP 4: Inject Voice Widget (GHL/Retell)
    # ──────────────────────────────────────────────────────────────────────
    final_html_path = animated_path

    if skip_widget:
        print(f"\n[4/7] WIDGET — skipped (--skip-widget)")
        results['steps_completed'].append('widget_skipped')
    else:
        print(f"\n[4/7] WIDGET — injecting {widget_type.upper()} widget")
        from inject_widget import inject_css, inject_script, load_ghl_config, load_retell_config, build_retell_embed

        # Read the animated HTML
        with open(animated_path, 'r', encoding='utf-8', errors='replace') as f:
            html_content = f.read()

        widget_injected = False

        if widget_type == 'ghl':
            config = load_ghl_config(slug)
            if not config:
                # Try to create a default GHL config
                print(f"  No GHL config for {slug} — using default location")
                ghl_location_id = os.getenv('GHL_LOCATION_ID', 'V99IPPukYvrLIB1hYHGG')
                css = f"""
/* GHL Chat Widget */
[data-chat-widget] {{
    position: fixed !important;
    bottom: 20px !important;
    right: 20px !important;
    z-index: 99999 !important;
}}
""".strip()
                script = f"""
<!-- GHL Chat Widget -->
<script>
window.hl_chatbot_widget = {{ locationId: "{ghl_location_id}" }};
</script>
<script src="https://widgets.leadconnectorhq.com/loader.js" data-resources-url="https://widgets.leadconnectorhq.com/chat-widget/loader.js"></script>
""".strip()
                html_content = inject_css(html_content, css)
                html_content = inject_script(html_content, script)
                widget_injected = True
                print(f"  Injected default GHL widget (location: {ghl_location_id})")
            else:
                css = config.get("css", "")
                html_trigger = config.get("html_trigger", "")
                script = config.get("script", "")
                script = html_trigger + "\n\n" + script if html_trigger else script
                html_content = inject_css(html_content, css)
                html_content = inject_script(html_content, script)
                widget_injected = True
                print(f"  Injected GHL widget: {config.get('display_name', 'GHL Chat')}")

        elif widget_type == 'retell':
            config = load_retell_config(slug)
            if not config:
                print(f"  No Retell config for {slug} — skipping widget")
            else:
                css, script = build_retell_embed(config)
                html_content = inject_css(html_content, css)
                html_content = inject_script(html_content, script)
                widget_injected = True
                print(f"  Injected Retell widget: agent {config.get('agent_id', 'unknown')}")

        if widget_injected:
            # Save the final HTML with widget
            final_html_path = animated_path.replace('.html', '-widget.html')
            os.makedirs(os.path.dirname(final_html_path) or '.', exist_ok=True)
            with open(final_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"  Output: {final_html_path}")
            results['steps_completed'].append('widget')
        else:
            print("  No widget injected — continuing without")
            results['steps_completed'].append('widget_skipped')

    results['html_path'] = final_html_path

    # ──────────────────────────────────────────────────────────────────────
    # STEP 5: Deploy to Live URL
    # ──────────────────────────────────────────────────────────────────────
    if skip_deploy:
        print(f"\n[5/7] DEPLOY — skipped (--skip-deploy)")
        results['steps_completed'].append('deploy_skipped')
    else:
        print(f"\n[5/7] DEPLOY — pushing to live preview")
        from deploy_redesign import deploy_single_html

        try:
            live_url = deploy_single_html(slug, final_html_path, deploy_type='redesign')
            results['live_url'] = live_url
            print(f"  LIVE: {live_url}")
            results['steps_completed'].append('deploy')
        except Exception as e:
            print(f"  ERROR deploying: {e}")
            results['steps_completed'].append('deploy_failed')

    # ──────────────────────────────────────────────────────────────────────
    # STEP 6: Create Before/After Comparison Image
    # ──────────────────────────────────────────────────────────────────────
    before_screenshot = results.get('screenshot_before')
    if not before_screenshot:
        # Try to find existing screenshot
        for ext in ['png', 'jpg', 'jpeg']:
            path = f'.tmp/screenshots/{slug}.{ext}'
            if os.path.exists(path):
                before_screenshot = path
                break
            path = f'.tmp/screenshots/{slug}-fullpage.{ext}'
            if os.path.exists(path):
                before_screenshot = path
                break

    if skip_comparison or not before_screenshot:
        if not before_screenshot:
            print(f"\n[6/7] COMPARISON — skipped (no before screenshot found)")
        else:
            print(f"\n[6/7] COMPARISON — skipped (--skip-comparison)")
        results['steps_completed'].append('comparison_skipped')
    else:
        print(f"\n[6/7] COMPARISON — creating before/after image")
        from create_comparison_image import create_comparison

        os.makedirs('.tmp/comparisons', exist_ok=True)
        comparison_path = f'.tmp/comparisons/{slug}-comparison.png'
        company_name = company or slug.replace('-', ' ').title()

        # For after screenshot, use the before screenshot path (Firecrawl captures the redesign too)
        # In reality we'd need to screenshot the live URL — for now use before as placeholder
        # The comparison is mainly useful when we have a real "after" screenshot
        after_screenshot = f'.tmp/screenshots/{slug}-after.png'
        if not os.path.exists(after_screenshot):
            print(f"  No after screenshot yet — comparison will be created after site is live")
            print(f"  Use: python execution/create_comparison_image.py --before {before_screenshot} --after <screenshot-of-live-url> --output {comparison_path}")
            results['steps_completed'].append('comparison_deferred')
        else:
            try:
                result_path = create_comparison(
                    before_path=before_screenshot,
                    after_path=after_screenshot,
                    output_path=comparison_path,
                    company_name=company_name,
                    branding_name=sender_name,
                )
                if result_path:
                    results['comparison_path'] = result_path
                    print(f"  Output: {result_path}")
                    results['steps_completed'].append('comparison')
                else:
                    print(f"  Comparison creation returned None")
                    results['steps_completed'].append('comparison_failed')
            except Exception as e:
                print(f"  ERROR creating comparison: {e}")
                results['steps_completed'].append('comparison_failed')

    # ──────────────────────────────────────────────────────────────────────
    # STEP 7: Send Outreach Email (optional)
    # ──────────────────────────────────────────────────────────────────────
    if send_email and email:
        print(f"\n[7/7] OUTREACH — sending email to {email}")
        from send_redesign_outreach import send_outreach_email

        try:
            email_result = send_outreach_email(
                to_email=email,
                first_name=name or slug.replace('-', ' ').title().split()[0],
                company_name=company or slug.replace('-', ' ').title(),
                comparison_image_path=results.get('comparison_path', ''),
                live_preview_url=results.get('live_url', ''),
                from_name=sender_name,
            )
            if email_result.get('message_id'):
                print(f"  Email sent! Message ID: {email_result['message_id']}")
                results['steps_completed'].append('outreach')
            else:
                print(f"  Email error: {email_result.get('error', 'unknown')}")
                results['steps_completed'].append('outreach_failed')
        except Exception as e:
            print(f"  ERROR sending email: {e}")
            results['steps_completed'].append('outreach_failed')
    else:
        print(f"\n[7/7] OUTREACH — skipped {'(no --send-email flag)' if not send_email else '(no --email provided)'}")
        results['steps_completed'].append('outreach_skipped')

    # ──────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("  TRANSFORMATION COMPLETE")
    print("=" * 70)
    print(f"  Slug:        {slug}")
    print(f"  Effect:      {effect}")
    print(f"  Widget:      {widget_type}")
    print(f"  Brand color: {brand_color}")
    print(f"  Time:        {elapsed:.0f}s")
    print(f"  Steps:       {' → '.join(results['steps_completed'])}")

    if results.get('live_url'):
        print(f"\n  LIVE URL: {results['live_url']}")
    if results.get('comparison_path'):
        print(f"  COMPARISON: {results['comparison_path']}")
    if results.get('html_path'):
        print(f"  LOCAL HTML: {results['html_path']}")

    print("=" * 70)

    # Save results to JSON
    os.makedirs('.tmp/transformations', exist_ok=True)
    results_path = f'.tmp/transformations/{slug}-result.json'
    results['elapsed_seconds'] = elapsed
    results['timestamp'] = datetime.now().isoformat()
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Results saved: {results_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Full Transformation Pipeline — scrape → generate → animate → widget → deploy → outreach',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline from URL
  python execution/full_transformation.py --url "https://example.com" --slug example --effect video-hero

  # From existing HTML (skip scrape+generate)
  python execution/full_transformation.py --input redesign.html --slug example --effect video-hero

  # With email outreach
  python execution/full_transformation.py --url "https://example.com" --slug example \\
    --effect cinematic-full --send-email --email "owner@example.com" --name "John"
        """
    )

    # Primary inputs (one of --url or --input required)
    parser.add_argument('--url', help='Target website URL (triggers scrape+generate)')
    parser.add_argument('--input', help='Path to existing HTML (skips scrape+generate)')
    parser.add_argument('--slug', help='URL-safe slug (auto-generated from URL if not provided)')

    # Animation
    parser.add_argument('--effect', default='video-hero',
                        choices=['video-hero', 'image-hero', 'scroll-reveals', 'dot-rhombus',
                                 'dot-arrow', 'particle-torus', 'cinematic-full'],
                        help='Animation effect (default: video-hero)')
    parser.add_argument('--brand-color', help='Brand hex color (auto-detected from scrape)')
    parser.add_argument('--hero-image', help='URL of actual hero image (for image-hero effect)')
    parser.add_argument('--video-category',
                        choices=['tech', 'abstract', 'nature', 'city', 'data', 'code', 'finance'],
                        help='Video category (auto-detected from slug)')

    # Widget
    parser.add_argument('--widget-type', default='ghl', choices=['ghl', 'retell'],
                        help='Voice widget type (default: ghl)')

    # Generator
    parser.add_argument('--generator', default='v0', choices=['v0', 'gemini', 'stitch'],
                        help='Redesign generator (default: v0)')

    # Outreach
    parser.add_argument('--send-email', action='store_true', help='Send outreach email after deploy')
    parser.add_argument('--email', help='Recipient email address')
    parser.add_argument('--name', help='Recipient first name')
    parser.add_argument('--company', help='Company name')
    parser.add_argument('--sender-name', default='Will Coates', help='Sender name (default: Will Coates)')

    # Skip flags
    parser.add_argument('--skip-scrape', action='store_true', help='Skip scrape (use existing data)')
    parser.add_argument('--skip-generate', action='store_true', help='Skip generate (use existing redesign)')
    parser.add_argument('--skip-animate', action='store_true', help='Skip animation')
    parser.add_argument('--skip-widget', action='store_true', help='Skip widget injection')
    parser.add_argument('--skip-deploy', action='store_true', help='Skip deployment')
    parser.add_argument('--skip-comparison', action='store_true', help='Skip comparison image')

    args = parser.parse_args()

    # Validate: need either --url or --input
    if not args.url and not args.input:
        parser.error("Either --url or --input is required")

    # Generate slug from URL if not provided
    slug = args.slug
    if not slug:
        if args.url:
            slug = slugify(args.url)
        elif args.input:
            slug = Path(args.input).stem.split('-')[0]  # rough guess

    result = full_transformation(
        url=args.url,
        slug=slug,
        input_html=args.input,
        effect=args.effect,
        widget_type=args.widget_type,
        brand_color=args.brand_color,
        video_category=args.video_category,
        hero_image=args.hero_image,
        generator=args.generator,
        send_email=args.send_email,
        email=args.email,
        name=args.name,
        company=args.company,
        sender_name=args.sender_name,
        skip_scrape=args.skip_scrape,
        skip_generate=args.skip_generate,
        skip_animate=args.skip_animate,
        skip_widget=args.skip_widget,
        skip_deploy=args.skip_deploy,
        skip_comparison=args.skip_comparison,
    )

    # Exit code based on whether critical steps succeeded
    if result.get('live_url') or 'deploy_skipped' in result.get('steps_completed', []):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
