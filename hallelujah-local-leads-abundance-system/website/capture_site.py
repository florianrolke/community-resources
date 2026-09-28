#!/usr/bin/env python3
"""
Capture a prospect's website — HTML, screenshot, and branding extraction.

Uses Firecrawl to scrape the site and extract:
- Full HTML content
- Full-page screenshot
- Brand colors, fonts, and visual identity

Usage:
    python website/capture_site.py --url "https://example.com" --slug example-corp
    python website/capture_site.py --url "https://example.com" --slug example-corp --output-dir .tmp/captures
"""

import os
import sys
import re
import json
import base64
import argparse
from pathlib import Path

# Windows UTF-8 fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from lib.safe_io import safe_json_write


def extract_branding_from_html(html):
    """Extract brand colors, fonts, and visual identity from HTML/CSS."""
    branding = {
        'primary_color': None,
        'accent_color': None,
        'background_color': None,
        'text_color': None,
        'heading_font': None,
        'body_font': None,
        'color_scheme': 'light',
        'all_colors': [],
        'all_fonts': [],
    }

    if not html:
        return branding

    # Extract theme-color meta tag
    meta_match = re.search(r'<meta[^>]*name="theme-color"[^>]*content="([^"]+)"', html, re.I)
    if meta_match:
        branding['primary_color'] = meta_match.group(1)

    # Extract CSS custom properties
    css_vars = re.findall(r'--([a-zA-Z-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', html)
    for name, color in css_vars:
        name_lower = name.lower()
        if 'primary' in name_lower and not branding['primary_color']:
            branding['primary_color'] = color
        elif 'accent' in name_lower and not branding['accent_color']:
            branding['accent_color'] = color
        elif 'background' in name_lower or 'bg' in name_lower:
            if not branding['background_color']:
                branding['background_color'] = color
        elif 'text' in name_lower or 'foreground' in name_lower:
            if not branding['text_color']:
                branding['text_color'] = color

    # Extract all hex colors
    hex_colors = re.findall(r'#[0-9a-fA-F]{6}', html)
    color_freq = {}
    for c in hex_colors:
        c_upper = c.upper()
        if c_upper not in ('#000000', '#FFFFFF', '#FFFFFF', '#000'):
            color_freq[c_upper] = color_freq.get(c_upper, 0) + 1

    # Top colors by frequency
    sorted_colors = sorted(color_freq.items(), key=lambda x: -x[1])
    branding['all_colors'] = [c for c, _ in sorted_colors[:10]]

    # Guess primary from most frequent non-grayscale color
    if not branding['primary_color'] and sorted_colors:
        for color, count in sorted_colors:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            # Skip near-grayscale
            if max(r, g, b) - min(r, g, b) > 30:
                branding['primary_color'] = color
                break

    if not branding['accent_color'] and len(sorted_colors) > 1:
        for color, count in sorted_colors:
            if color != branding['primary_color']:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                if max(r, g, b) - min(r, g, b) > 30:
                    branding['accent_color'] = color
                    break

    # Extract fonts from CSS
    font_matches = re.findall(r"font-family\s*:\s*['\"]?([^;'\"}{]+)", html)
    seen_fonts = set()
    for font_str in font_matches:
        first_font = font_str.split(',')[0].strip().strip("'\"")
        if first_font and first_font.lower() not in ('inherit', 'sans-serif', 'serif', 'monospace'):
            if first_font not in seen_fonts:
                seen_fonts.add(first_font)
                branding['all_fonts'].append(first_font)

    # Extract Google Fonts
    gfont_matches = re.findall(r'fonts\.googleapis\.com/css2?\?family=([^"&]+)', html)
    for gfont in gfont_matches:
        font_name = gfont.split(':')[0].replace('+', ' ')
        if font_name not in seen_fonts:
            seen_fonts.add(font_name)
            branding['all_fonts'].append(font_name)

    # Assign heading/body fonts
    if len(branding['all_fonts']) >= 2:
        branding['heading_font'] = branding['all_fonts'][0]
        branding['body_font'] = branding['all_fonts'][1]
    elif branding['all_fonts']:
        branding['heading_font'] = branding['all_fonts'][0]
        branding['body_font'] = branding['all_fonts'][0]

    # Detect color scheme (dark vs light)
    bg = branding['background_color'] or '#FFFFFF'
    if bg.startswith('#') and len(bg) == 7:
        r = int(bg[1:3], 16)
        g = int(bg[3:5], 16)
        b = int(bg[5:7], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        branding['color_scheme'] = 'dark' if luminance < 0.5 else 'light'

    return branding


def capture_website(url, slug, output_dir='.tmp/captures'):
    """Capture a website using Firecrawl.

    Returns dict with paths to saved files.
    """
    from firecrawl import FirecrawlApp

    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not set in .env")

    app = FirecrawlApp(api_key=api_key)

    print(f"  Scraping {url} via Firecrawl...")
    result = app.scrape_url(url, params={
        'formats': ['html', 'screenshot']
    })

    # Create output directory
    site_dir = os.path.join(output_dir, slug)
    os.makedirs(site_dir, exist_ok=True)

    paths = {
        'html_path': None,
        'screenshot_path': None,
        'branding_path': None,
    }

    # Save HTML
    html_content = result.get('html', '')
    if html_content:
        html_path = os.path.join(site_dir, 'page.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        paths['html_path'] = html_path
        print(f"  HTML saved: {html_path} ({len(html_content):,} chars)")

    # Save screenshot
    screenshot_data = result.get('screenshot')
    if screenshot_data:
        screenshot_path = os.path.join(site_dir, 'screenshot.png')
        if screenshot_data.startswith('data:'):
            # Base64 data URL
            b64 = screenshot_data.split(',', 1)[1]
            with open(screenshot_path, 'wb') as f:
                f.write(base64.b64decode(b64))
        elif screenshot_data.startswith('http'):
            # URL — download it
            import requests
            resp = requests.get(screenshot_data, timeout=30)
            with open(screenshot_path, 'wb') as f:
                f.write(resp.content)
        paths['screenshot_path'] = screenshot_path
        print(f"  Screenshot saved: {screenshot_path}")

    # Extract and save branding
    branding = extract_branding_from_html(html_content)
    branding['url'] = url
    branding['slug'] = slug
    branding_path = os.path.join(site_dir, 'branding.json')
    safe_json_write(branding_path, branding)
    paths['branding_path'] = branding_path
    print(f"  Branding extracted: primary={branding['primary_color']}, fonts={branding['all_fonts'][:3]}")

    return paths


def main():
    parser = argparse.ArgumentParser(description='Capture a website for redesign')
    parser.add_argument('--url', required=True, help='Website URL to capture')
    parser.add_argument('--slug', required=True, help='Project slug (e.g., example-corp)')
    parser.add_argument('--output-dir', default='.tmp/captures', help='Output directory')

    args = parser.parse_args()

    print(f"Capturing: {args.url}")
    result = capture_website(args.url, args.slug, args.output_dir)

    print(f"\nCapture complete:")
    for key, path in result.items():
        if path:
            print(f"  {key}: {path}")


if __name__ == '__main__':
    main()
