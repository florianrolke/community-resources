#!/usr/bin/env python3
"""
Build a widget demo page: iframe of prospect's real site + Retell chat widget.

Takes the prospect's live URL and wraps it in a full-viewport iframe with the
Retell AI chat widget floating on top. The result is a single HTML file
deployable to the preview subdomain.

Usage:
    python widget-demo/build_widget_page.py --url https://delta-vega.com --slug delta-vega
    python widget-demo/build_widget_page.py --url https://dunkertonscider.co.uk --slug dunkertons-cider
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

CONFIG_DIR = Path(__file__).parent
OUTPUT_DIR = CONFIG_DIR / "output"


def check_iframe_allowed(url):
    """Check if a site allows iframe embedding (X-Frame-Options / CSP)."""
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        xfo = resp.headers.get('X-Frame-Options', '').upper()
        csp = resp.headers.get('Content-Security-Policy', '')

        if xfo in ('DENY', 'SAMEORIGIN'):
            return False, f"X-Frame-Options: {xfo}"
        if 'frame-ancestors' in csp and "'self'" in csp:
            return False, f"CSP frame-ancestors blocks embedding"
        return True, "OK"
    except Exception as e:
        return True, f"Could not check (assuming OK): {e}"


def load_retell_config(slug):
    """Load Retell agent config for a slug."""
    # Try per-slug config first
    slug_config = CONFIG_DIR / f"retell-config-{slug}.json"
    if slug_config.exists():
        with open(slug_config, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Fall back to main config file
    main_config = CONFIG_DIR / "retell-config.json"
    if main_config.exists():
        with open(main_config, 'r', encoding='utf-8') as f:
            all_configs = json.load(f)
            if slug in all_configs:
                return all_configs[slug]

    return None


def _get_title(url):
    """Extract a clean title from a URL."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.replace('www.', '')
    return domain.split('.')[0].replace('-', ' ').title()


def build_widget_html(url, slug, agent_id, public_key, accent_color="#FF0000"):
    """Generate the iframe + widget wrapper HTML."""
    title = _get_title(url)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script
        id="retell-widget"
        src="https://dashboard.retellai.com/retell-widget.js"
        type="module"
        data-public-key="{public_key}"
        data-agent-id="{agent_id}"
        data-title="Chat with {title}"
        data-color="{accent_color}"
        data-bot-name="{title} Assistant"
    ></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; }}
        iframe {{ width: 100%; height: 100%; border: none; display: block; }}
    </style>
</head>
<body>
    <iframe src="{url}" allow="autoplay; fullscreen" loading="eager"></iframe>
</body>
</html>"""


def build_widget_fallback_html(url, slug, agent_id, public_key, accent_color="#FF0000"):
    """Generate a screenshot-based fallback when iframe is blocked.

    Uses the Firecrawl full-page screenshot (already captured) as a scrollable
    background image. Retell widget still works since it's on our page.
    """
    import base64
    title = _get_title(url)

    # Load the full-page screenshot
    screenshot_path = Path(f'.tmp/screenshots/{slug}_before_full.png')
    if not screenshot_path.exists():
        # Try viewport screenshot
        screenshot_path = Path(f'.tmp/screenshots/{slug}_before.png')
    if not screenshot_path.exists():
        print(f"  WARNING: No screenshot found for fallback at .tmp/screenshots/{slug}_before*.png")
        print(f"  Using text-only fallback.")
        return _build_text_only_fallback(url, title, agent_id, public_key, accent_color)

    with open(screenshot_path, 'rb') as f:
        img_data = base64.b64encode(f.read()).decode('ascii')
    print(f"  Using screenshot fallback: {screenshot_path} ({len(img_data) // 1024}KB base64)")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Preview</title>
    <script
        id="retell-widget"
        src="https://dashboard.retellai.com/retell-widget.js"
        type="module"
        data-public-key="{public_key}"
        data-agent-id="{agent_id}"
        data-title="Chat with {title}"
        data-color="{accent_color}"
        data-bot-name="{title} Assistant"
    ></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ background: #0a0a0a; }}
        body {{ min-height: 100vh; font-family: system-ui, -apple-system, sans-serif; }}
        .top-bar {{
            position: fixed; top: 0; left: 0; right: 0; z-index: 100;
            background: rgba(10,10,10,0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 12px 24px;
            display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }}
        .top-bar .title {{
            color: rgba(255,255,255,0.7); font-size: 13px; font-weight: 500;
            letter-spacing: 0.02em;
        }}
        .top-bar .open-btn {{
            display: inline-flex; align-items: center; gap: 6px;
            padding: 8px 18px;
            background: {accent_color}; color: #fff;
            font-size: 13px; font-weight: 600;
            border-radius: 8px; text-decoration: none;
            transition: all 0.2s ease;
        }}
        .top-bar .open-btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}
        .screenshot-wrap {{
            padding-top: 52px;
            display: flex; justify-content: center;
        }}
        .screenshot-wrap img {{
            max-width: 1440px; width: 100%;
            border-radius: 0;
            box-shadow: 0 20px 80px rgba(0,0,0,0.4);
        }}
        .footer-note {{
            text-align: center; padding: 20px;
            font-size: 11px; color: rgba(255,255,255,0.3);
        }}
    </style>
</head>
<body>
    <div class="top-bar">
        <span class="title">Preview of {title}</span>
        <a href="{url}" target="_blank" class="open-btn">
            Open live site &#x2197;
        </a>
    </div>
    <div class="screenshot-wrap">
        <img src="data:image/png;base64,{img_data}" alt="{title} website preview">
    </div>
    <div class="footer-note">
        Screenshot captured from public website &middot; Chat with our AI assistant using the widget below
    </div>
</body>
</html>"""


def _build_text_only_fallback(url, title, agent_id, public_key, accent_color):
    """Minimal fallback when no screenshot is available."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Widget Demo</title>
    <script
        id="retell-widget"
        src="https://dashboard.retellai.com/retell-widget.js"
        type="module"
        data-public-key="{public_key}"
        data-agent-id="{agent_id}"
        data-title="Chat with {title}"
        data-color="{accent_color}"
        data-bot-name="{title} Assistant"
    ></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ min-height: 100vh; background: #0a0a0a; color: #fff;
                font-family: system-ui, sans-serif;
                display: flex; align-items: center; justify-content: center;
                flex-direction: column; gap: 24px; padding: 40px; }}
        h1 {{ font-size: 28px; font-weight: 300; opacity: 0.9; }}
        p {{ font-size: 16px; opacity: 0.5; max-width: 400px; text-align: center; }}
        a {{ display: inline-block; padding: 12px 28px; background: {accent_color};
             color: #fff; text-decoration: none; border-radius: 8px; font-weight: 600;
             transition: opacity 0.2s; }}
        a:hover {{ opacity: 0.9; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>Try our AI assistant — click the chat widget in the bottom-right corner.</p>
    <a href="{url}" target="_blank">Visit {title} &rarr;</a>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description='Build a widget demo page for a prospect')
    parser.add_argument('--url', required=True, help='Prospect website URL (e.g., https://delta-vega.com)')
    parser.add_argument('--slug', required=True, help='Site identifier (e.g., delta-vega)')
    parser.add_argument('--color', default='#FF0000', help='Widget accent color (hex)')
    args = parser.parse_args()

    print(f"\n=== Building widget page for: {args.slug} ===\n")

    # Check iframe compatibility
    print(f"  Checking iframe compatibility for {args.url}...")
    allowed, reason = check_iframe_allowed(args.url)
    if not allowed:
        print(f"  iframe BLOCKED: {reason}")
        print(f"  Will use screenshot fallback instead of iframe.")
    else:
        print(f"  iframe check: {reason}")

    # Load Retell config
    config = load_retell_config(args.slug)
    agent_id = config.get('agent_id', 'AGENT_ID_PLACEHOLDER') if config else 'AGENT_ID_PLACEHOLDER'

    if agent_id == 'AGENT_ID_PLACEHOLDER':
        print(f"  WARNING: No Retell agent found for '{args.slug}'.")
        print(f"  Run: python widget-demo/setup_retell_agent.py --slug {args.slug}")
        print(f"  Using placeholder — widget won't work until agent is created.")

    # Get public key
    public_key = os.getenv('RETELL_PUBLIC_KEY', 'PUBLIC_KEY_PLACEHOLDER')
    if public_key == 'PUBLIC_KEY_PLACEHOLDER':
        print(f"  WARNING: RETELL_PUBLIC_KEY not found in .env.")
        print(f"  Get it from: Retell Dashboard → Keys → Add Key → Public Key")
        print(f"  Using placeholder — widget won't load until key is added.")

    # Try to get accent color from branding
    branding_path = Path(f'.tmp/branding/{args.slug}.json')
    if branding_path.exists() and args.color == '#FF0000':
        with open(branding_path, 'r', encoding='utf-8') as f:
            branding = json.load(f)
        accent = branding.get('colors', {}).get('accent', args.color)
        if accent:
            args.color = accent
            print(f"  Using brand accent color: {args.color}")

    # Build HTML — use iframe if allowed, screenshot fallback if blocked
    if allowed:
        html = build_widget_html(args.url, args.slug, agent_id, public_key, args.color)
    else:
        html = build_widget_fallback_html(args.url, args.slug, agent_id, public_key, args.color)

    # Save output
    output_dir = OUTPUT_DIR / f"{args.slug}-chat"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n  HTML saved: {output_path} ({len(html)} chars)")

    print(f"\n=== Done! ===")
    print(f"  Preview locally: open {output_path} in browser")
    print(f"  Deploy with:")
    print(f'    python execution/deploy_redesign.py --slug "{args.slug}-chat" --html-file "{output_path}"')


if __name__ == '__main__':
    main()
