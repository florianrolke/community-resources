#!/usr/bin/env python3
"""
Generate a website redesign using Google Stitch MCP.

Takes branding data from Firecrawl capture, analyzes the current website
to identify design gaps, then generates a targeted redesign via Stitch AI.

Flow:
  1. Analyze current site (HTML + branding) -> description + gap list
  2. Build targeted Stitch prompt addressing specific weaknesses
  3. Generate redesign via Stitch MCP subprocess (JSON-RPC)

Outputs:
  - .tmp/analysis/{slug}-analysis.json  (website analysis + scores)
  - .tmp/redesigns/{slug}-redesign.html (Tailwind CSS responsive HTML)
  - .tmp/redesigns/{slug}-redesign.png  (Screenshot of redesign)

Usage:
    # Single site (auto-analyzes + builds targeted prompt)
    python execution/generate_redesign.py --slug "delta-vega"

    # Custom prompt override (skips analysis)
    python execution/generate_redesign.py --slug "delta-vega" --prompt "A modern dark homepage..."

    # Analysis only (no Stitch generation)
    python execution/generate_redesign.py --slug "delta-vega" --analyze-only

    # Batch from Google Sheet (status=screenshot_taken)
    python execution/generate_redesign.py --sheet-url "SHEET_URL" --batch-size 10
"""

import os
import sys
import json
import subprocess
import time
import argparse
import requests
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

# --- Stitch MCP subprocess communication ---

class StitchMCP:
    """Wrapper for Stitch MCP called via subprocess JSON-RPC."""

    def __init__(self):
        self.stitch_key = os.getenv('STITCH_API_KEY')
        if not self.stitch_key:
            raise ValueError("STITCH_API_KEY not found in .env")
        self.proc = None
        self._msg_id = 0

    def start(self):
        """Start the MCP server subprocess."""
        env = os.environ.copy()
        env['STITCH_API_KEY'] = self.stitch_key

        self.proc = subprocess.Popen(
            ['npx.cmd', '-y', '@_davideast/stitch-mcp', 'proxy'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )

        # Initialize MCP protocol (required before any tool calls)
        resp = self._send('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'generate-redesign', 'version': '1.0'}
        }, wait=15)

        if not resp:
            raise RuntimeError("Failed to initialize Stitch MCP")
        return self

    def stop(self):
        """Stop the MCP subprocess."""
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except:
                self.proc.kill()
            self.proc = None

    def _send(self, method, params, wait=180):
        """Send JSON-RPC message and wait for response."""
        self._msg_id += 1
        msg = json.dumps({
            'jsonrpc': '2.0',
            'id': self._msg_id,
            'method': method,
            'params': params
        }) + '\n'

        self.proc.stdin.write(msg)
        self.proc.stdin.flush()

        start = time.time()
        while time.time() - start < wait:
            line = self.proc.stdout.readline().strip()
            if line:
                try:
                    data = json.loads(line)
                    if data.get('id') == self._msg_id:
                        return data
                except (json.JSONDecodeError, ValueError):
                    pass
        return None

    def _call_tool(self, name, arguments, wait=180):
        """Call an MCP tool and return the result."""
        resp = self._send('tools/call', {
            'name': name,
            'arguments': arguments
        }, wait=wait)

        if not resp:
            raise TimeoutError(f"Stitch MCP tool '{name}' timed out after {wait}s")

        result = resp.get('result', {})
        if result.get('isError'):
            error_text = result.get('content', [{}])[0].get('text', 'Unknown error')
            raise RuntimeError(f"Stitch MCP error: {error_text}")

        return result.get('structuredContent', {})

    def create_project(self, title):
        """Create a new Stitch project. Returns project ID."""
        data = self._call_tool('create_project', {'title': title}, wait=15)
        project_name = data.get('name', '')
        return project_name.replace('projects/', '')

    def generate_screen(self, project_id, prompt):
        """Generate a screen from text prompt. Returns (html_url, screenshot_url, metadata)."""
        # CRITICAL: Do NOT pass deviceType — causes "invalid argument" error
        data = self._call_tool('generate_screen_from_text', {
            'projectId': project_id,
            'prompt': prompt
        }, wait=180)

        # Extract screen data from nested response
        components = data.get('outputComponents', [])
        if not components:
            raise RuntimeError("No output components in Stitch response")

        screen = components[0].get('design', {}).get('screens', [{}])[0]
        html_url = screen.get('htmlCode', {}).get('downloadUrl', '')
        screenshot_url = screen.get('screenshot', {}).get('downloadUrl', '')

        if not html_url:
            raise RuntimeError("No HTML URL in Stitch response")

        return html_url, screenshot_url, {
            'width': screen.get('width'),
            'height': screen.get('height'),
            'device_type': screen.get('deviceType'),
            'generated_by': screen.get('generatedBy'),
        }


# --- Website Analysis Engine ---

def analyze_website(slug, branding_path, html_path=None):
    """Analyze a website's current state and identify design gaps.

    Parses the captured HTML structure and branding data to produce:
    - A human-readable description of the current site
    - Scores across 10 design categories (0-10 each)
    - Specific gaps (weaknesses to fix in the redesign)
    - Strengths (things to preserve)

    Returns:
        dict with description, scores, gaps, strengths, branding, content, company_name
    """
    with open(branding_path, 'r', encoding='utf-8') as f:
        branding = json.load(f)

    colors = branding.get('colors', {})
    fonts = branding.get('fonts', [])
    personality = branding.get('personality', {})
    typography = branding.get('typography', {})
    components = branding.get('components', {})
    spacing = branding.get('spacing', {})
    company_name = slug.replace('-', ' ').title()

    # Parse font names
    font_names = []
    for f_item in fonts:
        if isinstance(f_item, dict):
            font_names.append(f_item.get('family', 'sans-serif'))
        else:
            font_names.append(str(f_item))

    # --- Parse HTML for structural analysis ---
    ha = {
        'sections': 0, 'headings': [], 'cta_buttons': [],
        'images_count': 0, 'images_with_alt': 0,
        'has_hero': False, 'has_testimonials': False,
        'has_pricing': False, 'has_footer': False,
        'has_contact_info': False, 'has_social_links': False,
        'has_meta_description': False, 'has_viewport_meta': False,
        'nav_items': [], 'about_text': '', 'all_text': [],
        'has_form': False, 'link_count': 0,
        'uses_page_builder': False, 'builder_name': '',
        'word_count': 0, 'has_animations': False,
    }

    if html_path and os.path.exists(html_path):
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()

            # Detect page builder
            for marker, name in [('brz-', 'brizy'), ('elementor-', 'elementor'),
                                  ('et_pb_', 'divi'), ('vc_row', 'wpbakery'),
                                  ('sqs-', 'squarespace'), ('wixui_', 'wix')]:
                if marker in html:
                    ha['uses_page_builder'] = True
                    ha['builder_name'] = name
                    break

            # Count sections
            ha['sections'] = len(re.findall(r'<section[^>]*>', html))
            if ha['sections'] == 0:
                ha['sections'] = len(re.findall(
                    r'<div[^>]*(?:class|id)[^>]*(?:section|block)[^>]*>', html, re.I
                ))

            # Extract headings
            for tag in ['h1', 'h2', 'h3']:
                for m in re.findall(rf'<{tag}[^>]*>(.*?)</{tag}>', html, re.S):
                    clean = re.sub(r'<[^>]+>', '', m).strip()
                    if clean and len(clean) > 2:
                        ha['headings'].append({'tag': tag, 'text': clean[:100]})

            # Extract nav items (Brizy-specific + generic)
            nav_matches = re.findall(r'<span[^>]*class="brz-span"[^>]*>([^<]+)</span>', html)
            if not nav_matches:
                nav_matches = re.findall(
                    r'<li[^>]*class="[^"]*menu-item[^"]*"[^>]*>.*?<a[^>]*>([^<]{2,25})</a>', html, re.S
                )
            if not nav_matches:
                nav_matches = re.findall(r'<a[^>]*>([^<]{2,20})</a>', html)
            seen = set()
            for item in nav_matches:
                clean = item.strip()
                if clean and clean.upper() not in seen and len(clean) < 25:
                    seen.add(clean.upper())
                    ha['nav_items'].append(clean)

            # Extract text content
            for m in re.findall(r'<(?:p|span)[^>]*>([^<]{20,500})', html):
                clean = m.strip()
                if clean and not clean.startswith('{') and 'brz-css' not in clean:
                    ha['all_text'].append(clean)
            if ha['all_text']:
                ha['about_text'] = ha['all_text'][0]
            ha['word_count'] = sum(len(t.split()) for t in ha['all_text'])

            # Count images
            img_tags = re.findall(r'<img[^>]*>', html)
            ha['images_count'] = len(img_tags)
            ha['images_with_alt'] = len([i for i in img_tags if re.search(r'alt="[^"]+[a-zA-Z]', i)])

            # CTA buttons
            for b in re.findall(r'<a[^>]*class="[^"]*btn[^"]*"[^>]*>(.*?)</a>', html, re.S):
                clean = re.sub(r'<[^>]+>', '', b).strip()
                if clean:
                    ha['cta_buttons'].append(clean)

            # Feature detection
            hl = html.lower()
            ha['has_hero'] = bool(re.search(r'hero|banner|jumbotron|bg-image', hl))
            ha['has_testimonials'] = any(w in hl for w in ['testimonial', 'review', 'what our'])
            ha['has_pricing'] = any(w in hl for w in ['pricing', 'price', '£', '$'])
            ha['has_footer'] = '<footer' in hl
            ha['has_contact_info'] = 'mailto:' in hl or 'tel:' in hl
            ha['has_social_links'] = any(w in hl for w in ['linkedin', 'instagram', 'twitter', 'facebook'])
            ha['has_meta_description'] = bool(re.search(r'<meta[^>]*name="description"', html))
            ha['has_viewport_meta'] = 'viewport' in hl
            ha['has_form'] = '<form' in hl or '<input' in hl
            ha['link_count'] = len(re.findall(r'<a\s', html))
            ha['has_animations'] = any(w in hl for w in ['animation', 'transition', 'transform'])

        except Exception as e:
            print(f"  Warning: HTML analysis error: {e}")

    # --- Scoring (0-10 per category) ---
    scores = {}

    # Visual hierarchy
    h_score = min(len(ha['headings']), 5) * 2
    if not any(h['tag'] == 'h1' for h in ha['headings']):
        h_score = max(0, h_score - 3)
    scores['visual_hierarchy'] = h_score

    # Layout structure
    scores['layout'] = min(ha['sections'] * 2.5, 10) if ha['sections'] > 0 else 2

    # CTA
    cta_count = len(ha['cta_buttons'])
    scores['cta'] = min(cta_count * 3, 10) if cta_count > 0 else 1

    # Typography
    font_count = len(font_names)
    scores['typography'] = {0: 2, 1: 5, 2: 8, 3: 6}.get(font_count, 4)
    # Check inverted sizes (body bigger than headings = bad)
    font_sizes = typography.get('fontSizes', {})
    h1_px = int(re.sub(r'[^0-9]', '', font_sizes.get('h1', '32')) or '32')
    body_px = int(re.sub(r'[^0-9]', '', font_sizes.get('body', '16')) or '16')
    if body_px > h1_px:
        scores['typography'] = max(1, scores['typography'] - 4)

    # Color scheme
    real_colors = len([v for v in colors.values() if v and v not in ('#000000', '#FFFFFF')])
    scores['color'] = {0: 3, 1: 4, 2: 5}.get(real_colors, 7)

    # Social proof
    scores['social_proof'] = 8 if ha['has_testimonials'] else 2

    # Content quality
    wc = ha['word_count']
    scores['content'] = 7 if wc > 200 else (5 if wc > 50 else 3)

    # Modern features
    modern = 3
    if ha['has_animations']: modern += 2
    if ha['has_viewport_meta']: modern += 2
    if ha['has_meta_description']: modern += 1
    if ha['has_form']: modern += 1
    scores['modern_features'] = min(modern, 10)

    # Imagery
    scores['imagery'] = 7 if ha['images_count'] > 5 else (5 if ha['images_count'] > 2 else 3)

    scores['overall'] = round(sum(scores.values()) / len(scores), 1)

    # --- Gap identification ---
    gaps = []
    strengths = []

    if not ha['has_hero']:
        gaps.append("No clear hero section with compelling headline and CTA")
    elif ha['cta_buttons']:
        strengths.append("Has hero section with call-to-action")

    if scores['visual_hierarchy'] < 5:
        gaps.append("Weak visual hierarchy - headings don't create clear information flow")
    if not any(h['tag'] == 'h1' for h in ha['headings']):
        gaps.append("Missing H1 heading - no clear primary message")

    if body_px > h1_px:
        gaps.append(f"Inverted typography: body text ({body_px}px) larger than headings ({h1_px}px)")
    if len(font_names) > 3:
        gaps.append(f"Too many fonts ({len(font_names)}) - visual inconsistency")
    if len(font_names) <= 1:
        gaps.append("Single font - no typographic contrast between headings and body")

    if ha['sections'] < 3:
        gaps.append(f"Only {ha['sections']} content sections - needs hero, features, social proof, CTA minimum")
    elif ha['sections'] >= 4:
        strengths.append(f"Good page structure with {ha['sections']} sections")

    if not ha['cta_buttons']:
        gaps.append("No visible CTA buttons - visitors don't know what action to take")
    elif len(ha['cta_buttons']) == 1:
        gaps.append("Only one CTA button - needs primary CTA in hero + secondary CTAs throughout")

    if not ha['has_testimonials']:
        gaps.append("No testimonials or social proof - missing trust signals")
    else:
        strengths.append("Has testimonials/social proof")

    if ha['has_contact_info']:
        strengths.append("Contact information present")
    else:
        gaps.append("No visible contact information")

    if ha['has_social_links']:
        strengths.append("Social media links present")

    if not ha['has_animations']:
        gaps.append("No animations or transitions - feels static and dated")

    if ha['uses_page_builder']:
        gaps.append(f"Built with {ha['builder_name']} page builder - template-looking design")

    btn = components.get('buttonPrimary', {})
    if btn.get('background') == 'transparent':
        gaps.append("Primary CTA has transparent background - weak visual prominence")
    br_val = btn.get('borderRadius', '0').replace('px', '')
    if br_val.isdigit() and int(br_val) < 4:
        gaps.append("Sharp button corners - dated look, modern designs use 8-12px radius")

    if spacing.get('borderRadius', '0px').replace('px', '').isdigit():
        br = int(spacing['borderRadius'].replace('px', ''))
        if br < 4:
            gaps.append("Minimal border radius - boxy, dated appearance")

    if colors.get('accent') == '#FF0000':
        gaps.append("Pure red accent (#FF0000) - feels aggressive, a refined warm tone would work better")

    if ha['word_count'] < 50:
        gaps.append("Very little text - visitors can't understand the offering")

    if ha['images_count'] < 3:
        gaps.append("Very few images - needs hero imagery and visual content")
    if ha['images_count'] > 0 and ha['images_with_alt'] == 0:
        gaps.append("No image alt text - bad for SEO and accessibility")

    # --- Build description ---
    tone = personality.get('tone', 'unknown')
    audience = personality.get('targetAudience', 'unknown')
    scheme = branding.get('color_scheme', 'light')

    desc = (
        f"**{company_name}** - A {tone} site targeting {audience}. "
        f"{'Built with ' + ha['builder_name'].title() + ' page builder. ' if ha['uses_page_builder'] else ''}"
        f"{ha['sections']} content sections, {ha['images_count']} images, "
        f"{len(ha['cta_buttons'])} CTA buttons. "
        f"{'Nav: ' + ', '.join(ha['nav_items'][:6]) + '. ' if ha['nav_items'] else ''}"
        f"{scheme.title()} scheme ({colors.get('primary', '?')} primary, "
        f"{colors.get('accent', '?')} accent). "
        f"{'Fonts: ' + ', '.join(font_names[:3]) + '. ' if font_names else ''}"
    )
    if body_px > h1_px:
        desc += f"Typography inverted (body {body_px}px > h1 {h1_px}px). "

    desc += f"\n\n**Key issues ({len(gaps)}):**"
    for i, gap in enumerate(gaps[:8], 1):
        desc += f"\n{i}. {gap}"

    if strengths:
        desc += f"\n\n**Strengths ({len(strengths)}):**"
        for s in strengths:
            desc += f"\n- {s}"

    return {
        'description': desc,
        'scores': scores,
        'gaps': gaps,
        'strengths': strengths,
        'branding': branding,
        'content': ha,
        'company_name': company_name,
    }


# --- Targeted prompt generation ---

def build_targeted_prompt(slug, analysis):
    """Build a Stitch prompt that addresses identified gaps.

    Instead of a generic 'make a nice website', this tells Stitch exactly
    what to fix based on the gap analysis of the current site.
    """
    branding = analysis['branding']
    gaps = analysis['gaps']
    content = analysis['content']
    company_name = analysis['company_name']

    colors = branding.get('colors', {})
    primary = colors.get('primary', '#333333')
    accent = colors.get('accent', '#0066cc')
    background = colors.get('background', '#FFFFFF')

    fonts = branding.get('fonts', [])
    font_names = []
    for f_item in fonts:
        if isinstance(f_item, dict):
            font_names.append(f_item.get('family', 'sans-serif'))
        else:
            font_names.append(str(f_item))

    personality = branding.get('personality', {})
    tone = personality.get('tone', 'professional')
    audience = personality.get('targetAudience', 'business professionals')

    # --- Determine sections based on gaps ---
    sections = []

    hero_adj = "Bold, attention-grabbing" if "No clear hero" in str(gaps) else "Clean, modern"
    sections.append(f"{hero_adj} hero section with compelling headline, subheading, and prominent CTA button")

    about_text = content.get('about_text', '')
    if about_text:
        sections.append(f'About section: "{about_text[:150]}"')
    else:
        sections.append("About section explaining the company and its value proposition")

    nav_items = content.get('nav_items', [])
    service_items = [n for n in nav_items if n.upper() not in ('HOME', 'ABOUT', 'CONTACT', 'MENU')]
    if service_items:
        sections.append(f"Services section with cards for: {', '.join(service_items[:4])}")
    else:
        sections.append("Services section with 3 cards showing key offerings")

    if "No testimonials" in str(gaps):
        sections.append("Testimonials section with 3 client quotes (use placeholder names)")

    sections.append("Final CTA section with clear 'Get in Touch' or 'Book a Consultation' button")
    sections.append("Footer with contact details, social links, and quick navigation")

    # --- Style improvements from gaps ---
    style_fixes = []
    gap_str = str(gaps)

    if "transparent background" in gap_str:
        style_fixes.append("solid, high-contrast CTA buttons")
    if "Sharp button" in gap_str or "border radius" in gap_str.lower():
        style_fixes.append("rounded corners (8-12px) on buttons and cards")
    if "No animations" in gap_str:
        style_fixes.append("subtle hover effects on buttons and cards")
    if "inverted typography" in gap_str.lower():
        style_fixes.append("proper typographic hierarchy (large headings, smaller body)")
    if "Pure red" in gap_str:
        style_fixes.append("refined accent color (warm coral instead of pure red)")
    if "page builder" in gap_str:
        style_fixes.append("clean, modern design without template bloat")

    style_fixes.extend(["generous whitespace", "professional, trustworthy appearance"])

    # --- Font spec ---
    if len(font_names) >= 2:
        font_spec = f"{font_names[0]} for headings, {font_names[1]} for body"
    elif font_names:
        font_spec = f"{font_names[0]} for headings and body"
    else:
        font_spec = "modern sans-serif (Inter or Montserrat)"

    # --- Assemble prompt ---
    parts = [
        f"Create a modern, premium homepage for {company_name}.",
        f"Brand colors: {primary} primary, {background} background, {accent} accent for buttons.",
        f"Typography: {font_spec}.",
        f"Audience: {audience}. Tone: {tone} but approachable.",
        "Layout (top to bottom):",
    ]
    for i, section in enumerate(sections, 1):
        parts.append(f"{i}. {section}")

    parts.append("Design: " + "; ".join(style_fixes) + ".")

    if nav_items:
        parts.append(f"Navigation: {', '.join(nav_items[:6])}.")

    return ' '.join(parts)


def build_prompt_from_branding(slug, branding_path, html_path=None):
    """Build a Stitch prompt by analyzing the current site and targeting gaps.

    This runs the full analysis pipeline:
    1. Parse HTML + branding to describe current state
    2. Score against best practices
    3. Identify specific gaps
    4. Build a prompt that tells Stitch exactly what to improve
    """
    analysis = analyze_website(slug, branding_path, html_path)

    # Print analysis summary
    print(f"\n  === Website Analysis: {analysis['company_name']} ===")
    print(f"  Overall score: {analysis['scores']['overall']}/10")
    print(f"  Gaps found: {len(analysis['gaps'])}")
    for gap in analysis['gaps'][:5]:
        print(f"    - {gap}")
    if len(analysis['gaps']) > 5:
        print(f"    ... and {len(analysis['gaps']) - 5} more")
    if analysis['strengths']:
        print(f"  Strengths: {len(analysis['strengths'])}")
        for s in analysis['strengths'][:3]:
            print(f"    + {s}")
    print()

    # Save analysis
    os.makedirs('.tmp/analysis', exist_ok=True)
    analysis_path = f'.tmp/analysis/{slug}-analysis.json'
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump({
            'slug': slug,
            'company_name': analysis['company_name'],
            'description': analysis['description'],
            'scores': analysis['scores'],
            'gaps': analysis['gaps'],
            'strengths': analysis['strengths'],
        }, f, indent=2)
    print(f"  Analysis saved: {analysis_path}")

    return build_targeted_prompt(slug, analysis)


# --- Main redesign function ---

def generate_redesign(slug, prompt=None, branding_path=None, html_path=None):
    """Generate a redesign for a single website.

    Args:
        slug: URL-safe identifier (e.g., 'delta-vega')
        prompt: Optional custom prompt. If None, auto-generated from analysis.
        branding_path: Path to branding JSON. Defaults to .tmp/branding/{slug}.json
        html_path: Path to captured HTML. Defaults to .tmp/html/{slug}.html

    Returns:
        dict with paths to output files and metadata
    """
    if not branding_path:
        branding_path = f'.tmp/branding/{slug}.json'
    if not html_path:
        html_path = f'.tmp/html/{slug}.html'

    if not prompt:
        if not os.path.exists(branding_path):
            raise FileNotFoundError(
                f"Branding file not found: {branding_path}\n"
                f"Run capture first: python execution/capture_website_screenshot.py --url ..."
            )
        prompt = build_prompt_from_branding(slug, branding_path, html_path)

    print(f"  Prompt: {prompt[:120]}...")

    os.makedirs('.tmp/redesigns', exist_ok=True)

    stitch = StitchMCP()
    stitch.start()

    try:
        print(f"  Creating Stitch project for {slug}...")
        project_id = stitch.create_project(f"{slug} Redesign")
        print(f"  Project ID: {project_id}")

        print(f"  Generating redesign (this takes ~90 seconds)...")
        start_time = time.time()
        html_url, screenshot_url, metadata = stitch.generate_screen(project_id, prompt)
        elapsed = time.time() - start_time
        print(f"  Generated in {elapsed:.0f}s ({metadata.get('width')}x{metadata.get('height')})")

        # Download HTML
        html_path_out = f'.tmp/redesigns/{slug}-redesign.html'
        r = requests.get(html_url, timeout=30)
        r.raise_for_status()
        with open(html_path_out, 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"  HTML saved: {html_path_out} ({len(r.text)} chars)")

        # Download screenshot
        screenshot_path = f'.tmp/redesigns/{slug}-redesign.png'
        if screenshot_url:
            r2 = requests.get(screenshot_url, timeout=30)
            r2.raise_for_status()
            with open(screenshot_path, 'wb') as f:
                f.write(r2.content)
            print(f"  Screenshot saved: {screenshot_path} ({len(r2.content)} bytes)")
        else:
            screenshot_path = None
            print("  Warning: No screenshot URL in response")

        return {
            'slug': slug,
            'html_path': html_path_out,
            'screenshot_path': screenshot_path,
            'project_id': project_id,
            'prompt': prompt,
            'elapsed_seconds': elapsed,
            'metadata': metadata,
        }

    finally:
        stitch.stop()


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description='Generate website redesign via Stitch MCP')
    parser.add_argument('--slug', help='URL-safe site identifier (e.g., delta-vega)')
    parser.add_argument('--url', help='Website URL (auto-generates slug)')
    parser.add_argument('--prompt', help='Custom Stitch prompt (overrides analysis)')
    parser.add_argument('--branding', help='Path to branding JSON file')
    parser.add_argument('--html', help='Path to captured HTML file')
    parser.add_argument('--sheet-url', help='Google Sheet URL for batch processing')
    parser.add_argument('--batch-size', type=int, default=10, help='Max sites per batch')
    parser.add_argument('--analyze-only', action='store_true',
                        help='Run analysis only, no Stitch generation')

    args = parser.parse_args()

    # Derive slug from URL if needed
    if args.url and not args.slug:
        from urllib.parse import urlparse
        parsed = urlparse(args.url)
        domain = parsed.netloc.replace('www.', '')
        args.slug = re.sub(r'[^a-z0-9-]', '-', domain.split('.')[0].lower())

    if args.slug:
        branding_path = args.branding or f'.tmp/branding/{args.slug}.json'
        html_path = args.html or f'.tmp/html/{args.slug}.html'

        if args.analyze_only:
            # Analysis only mode
            print(f"Analyzing website: {args.slug}")
            if not os.path.exists(branding_path):
                print(f"Error: Branding file not found: {branding_path}")
                sys.exit(1)
            analysis = analyze_website(args.slug, branding_path, html_path)
            print(f"\n{analysis['description']}")
            print(f"\nScores:")
            for k, v in analysis['scores'].items():
                bar = '#' * int(v) + '-' * (10 - int(v))
                print(f"  {k:20s} [{bar}] {v}/10")
            print(f"\nTargeted prompt would be:")
            print(f"  {build_targeted_prompt(args.slug, analysis)[:200]}...")
        else:
            # Full redesign
            print(f"Generating redesign for: {args.slug}")
            result = generate_redesign(
                slug=args.slug,
                prompt=args.prompt,
                branding_path=args.branding,
                html_path=args.html,
            )
            print(f"\nDone! Files:")
            print(f"  HTML: {result['html_path']}")
            if result.get('screenshot_path'):
                print(f"  Screenshot: {result['screenshot_path']}")
            print(f"  Time: {result['elapsed_seconds']:.0f}s")
            print(f"\nNext: deploy with:")
            print(f"  python execution/deploy_redesign.py --slug \"{args.slug}\" "
                  f"--html-file \"{result['html_path']}\"")

    elif args.sheet_url:
        print("Batch mode: reading from Google Sheet...")
        print("TODO: integrate with gspread for batch processing")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
