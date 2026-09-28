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

# --- v0 API Generator (Vercel) ---

class V0Generator:
    """Generate UI via v0.dev Platform API (REST, no MCP needed)."""

    API_URL = "https://api.v0.dev/v1/chats"

    def __init__(self):
        self.api_key = os.getenv('V0_API_KEY')
        if not self.api_key:
            raise ValueError("V0_API_KEY not found in .env")

    def generate(self, prompt, timeout=180):
        """Send prompt to v0, return (html_content, screenshot_url, metadata).

        v0 chat API returns code inside markdown code blocks in the assistant message.
        We extract the HTML from the response.
        """
        # Force plain HTML output (v0 defaults to React/Next.js)
        html_prompt = (
            "IMPORTANT: Generate a SINGLE standalone HTML file with inline Tailwind CSS "
            "(via CDN script tag). Do NOT use React, JSX, Next.js, or any framework. "
            "Output pure HTML + CSS + vanilla JS only. Include the Tailwind CDN: "
            '<script src="https://cdn.tailwindcss.com"></script>\n'
            "Return ONLY the HTML code in a single code block — no explanation text.\n\n"
            + prompt
        )

        resp = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "message": html_prompt,
                "responseMode": "sync",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        # v0 chat API: code is in the assistant message content as markdown
        messages = data.get('messages', [])
        assistant_msg = None
        for msg in messages:
            if msg.get('role') == 'assistant':
                assistant_msg = msg.get('content', '')
                break

        if not assistant_msg:
            raise RuntimeError("v0 returned no assistant message")

        # Extract HTML from markdown code block (```html ... ``` or ``` ... ```)
        html_content = None
        code_blocks = re.findall(r'```(?:html)?\s*\n(.*?)```', assistant_msg, re.S)
        for block in code_blocks:
            block = block.strip()
            if '<!DOCTYPE' in block.upper() or '<html' in block.lower() or '<div' in block.lower():
                html_content = block
                break

        # Fallback: if no code block but response contains raw HTML
        if not html_content and '<html' in assistant_msg.lower():
            # Try to extract just the HTML portion
            match = re.search(r'(<!DOCTYPE[^>]*>.*</html>)', assistant_msg, re.S | re.I)
            if match:
                html_content = match.group(1)

        if not html_content:
            raise RuntimeError(
                f"v0 response contained no HTML code block. "
                f"Response preview: {assistant_msg[:300]}..."
            )

        chat_url = data.get('webUrl', data.get('url', ''))

        return html_content, '', {
            'chat_url': chat_url,
            'chat_id': data.get('id', ''),
            'generated_by': 'v0',
            'response_length': len(assistant_msg),
        }


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


# --- Facts Extraction (Content Lock) ---

def extract_facts(slug, analysis):
    """Extract verifiable facts from the current site to constrain Stitch output.

    Builds a facts_lock.json that the generator MUST NOT contradict.
    Prevents hallucinated stats, fake locations, invented dates, etc.

    Returns:
        dict with verified facts and disallowed content rules
    """
    branding = analysis['branding']
    content = analysis['content']
    company_name = analysis['company_name']

    colors = branding.get('colors', {})
    fonts = branding.get('fonts', [])
    images = branding.get('images', {})
    personality = branding.get('personality', {})

    # Extract font family names
    font_names = []
    for f_item in fonts:
        if isinstance(f_item, dict):
            font_names.append(f_item.get('family', 'sans-serif'))
        else:
            font_names.append(str(f_item))

    # --- Verified business facts ---
    facts = {
        'company_name': company_name,
        'logo_url': images.get('logo', ''),
        'tone': personality.get('tone', 'professional'),
        'target_audience': personality.get('targetAudience', ''),
    }

    # Navigation items (real page structure)
    if content.get('nav_items'):
        facts['navigation'] = content['nav_items'][:8]

    # Real text content from the site
    if content.get('about_text'):
        facts['about_text'] = content['about_text'][:500]
    if content.get('all_text'):
        facts['all_content'] = [t[:300] for t in content['all_text'][:10]]

    # Headings (real structure)
    if content.get('headings'):
        facts['headings'] = [h['text'] for h in content['headings'][:10]]

    # CTAs (must be preserved)
    if content.get('cta_buttons'):
        facts['original_ctas'] = content['cta_buttons'][:5]

    # Contact info markers
    facts['has_contact_info'] = content.get('has_contact_info', False)
    facts['has_form'] = content.get('has_form', False)
    facts['has_social_links'] = content.get('has_social_links', False)

    # Brand tokens
    facts['brand'] = {
        'primary_color': colors.get('primary', '#333333'),
        'accent_color': colors.get('accent', '#0066cc'),
        'background_color': colors.get('background', '#FFFFFF'),
        'fonts': font_names[:3],
    }

    # --- Disallowed content ---
    facts['disallowed'] = [
        "Do NOT invent founding years, establishment dates, or 'Est.' claims",
        "Do NOT invent statistics (years of experience, assets managed, clients served)",
        "Do NOT invent office locations, cities, or 'global hubs'",
        "Do NOT invent event names, dates, or schedules",
        "Do NOT invent team member names or testimonial quotes",
        "Do NOT invent awards, certifications, or press mentions",
        "Do NOT invent phone numbers, email addresses, or physical addresses",
        "Do NOT invent copyright years — use 'Delta Vega' without a year if needed",
        "Do NOT embellish service descriptions beyond what the original site states",
        "If a detail is not provided below, OMIT it entirely — do not fabricate",
    ]

    # Save facts lock
    os.makedirs('.tmp/facts', exist_ok=True)
    facts_path = f'.tmp/facts/{slug}-facts.json'
    with open(facts_path, 'w', encoding='utf-8') as f:
        json.dump(facts, f, indent=2)
    print(f"  Facts lock saved: {facts_path}")

    return facts


# --- Targeted prompt generation ---

def build_targeted_prompt(slug, analysis, facts=None):
    """Build a conversion-grade Stitch prompt using buyer-question framework.

    Every section answers a specific buyer question:
    - Hero: "What is this and why should I care?"
    - About/Proof: "Why should I believe you?"
    - Services: "What exactly do I get?"
    - CTA: "What do I do next?"

    Uses "humble precision" — specific about capabilities, silent on unverified claims.
    """
    branding = analysis['branding']
    company_name = analysis['company_name']

    if not facts:
        facts = extract_facts(slug, analysis)

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

    # --- Build real content block from facts ---
    about_text = facts.get('about_text', '')
    nav_items = facts.get('navigation', [])
    original_ctas = facts.get('original_ctas', [])
    all_content = facts.get('all_content', [])
    headings = facts.get('headings', [])

    content_lines = []
    if about_text:
        content_lines.append(f'ABOUT TEXT (use verbatim): "{about_text[:300]}"')
    if headings:
        content_lines.append(f"HEADINGS: {'; '.join(headings[:6])}")
    if nav_items:
        content_lines.append(f"NAV: {', '.join(nav_items[:8])}")
    if original_ctas:
        content_lines.append(f"CTA BUTTONS (must preserve): {', '.join(original_ctas[:4])}")
    if all_content and len(all_content) > 1:
        extra = [t for t in all_content[1:4] if len(t) > 30]
        if extra:
            content_lines.append(f"BODY TEXT: {' | '.join(extra)}")

    # --- Service items from nav ---
    service_items = [n for n in nav_items if n.upper() not in ('HOME', 'ABOUT', 'CONTACT', 'MENU')]
    hero_cta = original_ctas[0] if original_ctas else "Get in Touch"

    # --- Determine design direction based on industry/tone ---
    is_dark = background.lower() in ('#000', '#000000', '#111', '#1a1a1a', '#0d0d0d')
    bg_style = "dark" if is_dark else "light with strategic dark sections"

    # --- Assemble the prompt ---
    parts = []

    # 1. VISION — agency-grade, not template
    parts.append(f"Design an award-winning homepage for {company_name} — a {tone} business targeting {audience}.")
    parts.append("This must look like a £15,000 agency build, not a template. Think Pentagram, Manual London, or DesignStudio quality.")

    # 2. DESIGN SYSTEM — premium aesthetics
    # Build font instruction
    font_instruction = ""
    if font_names:
        heading_font = font_names[0]
        body_font = font_names[1] if len(font_names) > 1 else font_names[0]
        google_fonts = '+'.join(font_names[:2])
        font_instruction = (
            f"Use Google Fonts: {heading_font} for headings, {body_font} for body text. "
            f'Include: <link href="https://fonts.googleapis.com/css2?family={google_fonts.replace(" ", "+")}'
            f':wght@300;400;600;700;800&display=swap" rel="stylesheet">. '
            f"Set font-family in both the <style> block and Tailwind config."
        )
    else:
        font_instruction = "Use Inter for all text."

    # Build button style instruction from branding
    btn = branding.get('components', {}).get('buttonPrimary', {})
    btn_bg = btn.get('background', accent)
    btn_text = btn.get('textColor', '#FFFFFF')
    btn_radius = btn.get('borderRadius', '8px')

    # Favicon
    favicon_url = branding.get('images', {}).get('favicon', '')
    favicon_instruction = f'Include favicon: <link rel="icon" href="{favicon_url}">' if favicon_url else ''

    parts.append("")
    parts.append("DESIGN SYSTEM:")
    parts.append(f"- LAYOUT: 1440px desktop. Asymmetric hero — oversized type left, atmospheric visual right. Break the grid with offset sections and overlapping elements. Generous whitespace (py-20 to py-32 between sections).")
    parts.append(f"- TYPOGRAPHY: {font_instruction} Hero heading 80-120px (font-extrabold, letter-spacing tight). Subheads 20-24px (font-light, tracking wide). Body 16-18px. Use clamp() for fluid scaling. Mix weights: 800 for impact, 300 for elegance.")
    parts.append(f"- COLOR: Primary {primary}, accent {accent} (sparingly — CTAs and key highlights only). Background: {bg_style}. Text: {colors.get('textPrimary', '#FFFFFF' if is_dark else '#000000')}. Alternate light and dark sections for rhythm. Never more than 3 colours on screen at once.")
    parts.append(f"- BUTTONS: Background {btn_bg}, text {btn_text}, border-radius {btn_radius}. Use these exact styles for all CTA buttons. Secondary buttons: outline style with border-color {accent}.")
    parts.append(f"- DEPTH: Glassmorphism cards (backdrop-blur-xl + bg-white/5 + border-white/10). Layered shadows (shadow-2xl). Gradient overlays on images (from-black/60 to-transparent).")
    parts.append(f"- TEXTURE: Subtle dot-grid or noise backgrounds on alternating sections. Thin decorative lines (1px borders) as section dividers. Abstract gradient orbs as floating accents.")
    if favicon_instruction:
        parts.append(f"- {favicon_instruction}")

    # 3. SECTIONS — each answers a buyer question
    parts.append("")
    parts.append("SECTIONS (each must answer a specific buyer question):")
    parts.append("")
    parts.append(f'1. HERO — answers "What is this and why should I care?"')
    parts.append(f"   Full viewport height. Left: oversized heading with {company_name}. Below it: a single sentence explaining WHAT the company does and WHO it helps — pulled from the real content below. One CTA button: '{hero_cta}' with accent background + subtle glow.")
    parts.append(f"   Right: atmospheric gradient orb or abstract shapes (NOT a stock photo of people in suits).")
    parts.append(f"   Below the fold line: a thin horizontal rule and a small 'scroll' indicator.")

    if about_text:
        parts.append("")
        parts.append(f'2. ABOUT / PROOF — answers "Why should I believe you?"')
        parts.append(f"   Editorial split: large bold heading left ('About' or the company name), real text right. Use the EXACT text provided below — do not rewrite or embellish.")
        parts.append(f"   If the company has publications, talks, or training — mention those as proof of expertise. But ONLY if listed in the real content.")
        parts.append(f"   NO invented stats, years, client counts, or locations. If you have nothing to prove, say nothing — silence is more credible than fabrication.")

    if service_items:
        parts.append("")
        parts.append(f'3. SERVICES — answers "What exactly do I get?"')
        parts.append(f"   Bento grid with varying card sizes: {', '.join(service_items[:5])}. Primary service = large card spanning 2 cols.")
        parts.append(f"   Each card: bold title + ONE real description line from original site. If no description exists, use ONLY the service name — no invented copy.")
        parts.append(f"   Cards: glassmorphism on dark section background, or elevated cards with shadow-2xl on light background. Hover: card lifts (translate-y) + shadow grows.")

    parts.append("")
    parts.append(f'4. CTA BAND — answers "What do I do next?"')
    parts.append(f"   Full-width dark ({primary}) section. One bold line: a direct, specific invitation to act (not generic 'Get Started'). Preserve the original CTA: '{hero_cta}'. Button with accent color + glow.")
    parts.append(f"   This should feel like the natural next step, not a sales push.")

    parts.append("")
    parts.append(f"5. FOOTER — minimal, sophisticated")
    parts.append(f"   Company name in large light text. Nav links. NO invented contact details, phone numbers, addresses, or social links unless provided below.")

    # 4. CONTENT INTEGRITY — the non-negotiable rules
    parts.append("")
    parts.append("CONTENT INTEGRITY (NON-NEGOTIABLE):")
    parts.append("- Use ONLY the verified content provided below. This is a real business — fabricated claims destroy trust.")
    parts.append("- Do NOT invent: founding years, 'Est.' dates, statistics, client counts, monetary figures, office locations, team members, testimonials, awards, phone numbers, emails, addresses, or copyright years.")
    parts.append("- If a section would be empty without fabrication, OMIT THE ENTIRE SECTION. A shorter honest page beats a longer dishonest one.")
    parts.append("- Service descriptions: use real text or just the service name. Never embellish.")
    parts.append("- The rule is 'humble precision': be specific about what you know, silent about what you don't.")
    if content_lines:
        parts.append("")
        parts.append("VERIFIED CONTENT (use only this):")
        for line in content_lines:
            parts.append(f"  {line}")

    # 5. PREMIUM DESIGN LANGUAGE (non-negotiable)
    parts.append("")
    parts.append("PREMIUM DESIGN LANGUAGE (non-negotiable — these rules separate agency-quality from template):")
    parts.append("- TYPE SCALE: Hero heading clamp(44px, 5vw, 96px) font-extrabold. H2 clamp(28px, 2.5vw, 48px). Body clamp(15px, 1.1vw, 18px). Mix weights: 800 for headings, 300 for subheads, 400 for body.")
    parts.append("- SPACING: Section padding clamp(56px, 7vw, 112px). Never less than 48px between sections. Generous whitespace signals premium.")
    parts.append("- SURFACES: Cards use backdrop-filter:blur(10px) + rgba background + 1px border rgba(255,255,255,0.08). Hover: translateY(-4px) + deeper shadow.")
    parts.append("- BACKGROUNDS: Alternate light/dark sections for visual rhythm. Dark sections use a subtle radial gradient highlight behind main content.")
    parts.append("- COLOR DISCIPLINE: Maximum 3 colors visible at once. Accent color ONLY on CTAs and key highlights — never on body text or backgrounds.")
    parts.append("- ICONS: Use inline SVG only — NO Material Icons ligatures (no 'arrow_forward', 'menu', etc. as text).")

    # 6. TECHNICAL
    parts.append("")
    parts.append("TECHNICAL: Desktop-first (1440px). Tailwind CSS utility classes + custom <style> block for glassmorphism/animations. UTF-8 charset + viewport meta required.")

    return '\n'.join(parts)


def build_prompt_from_branding(slug, branding_path, html_path=None):
    """Build a Stitch prompt by analyzing the current site and targeting gaps.

    This runs the full analysis pipeline:
    1. Parse HTML + branding to describe current state
    2. Score against best practices
    3. Identify specific gaps
    4. Extract verifiable facts (content lock)
    5. Build a prompt that preserves real content and fixes design gaps
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

    # Extract and save facts lock
    facts = extract_facts(slug, analysis)
    print(f"  Facts extracted: {len(facts.get('all_content', []))} content blocks, "
          f"{len(facts.get('original_ctas', []))} CTAs, "
          f"{len(facts.get('navigation', []))} nav items")

    return build_targeted_prompt(slug, analysis, facts)


# --- Post-Generation QA Gate ---

# Common Material Icon ligature strings that render as text when CDN is missing
ICON_LIGATURES = [
    'arrow_forward', 'arrow_back', 'arrow_downward', 'arrow_upward',
    'chevron_right', 'chevron_left', 'expand_more', 'expand_less',
    'close', 'menu', 'search', 'check', 'check_circle',
    'play_circle', 'play_arrow', 'pause', 'stop',
    'star', 'star_border', 'star_half',
    'email', 'phone', 'location_on', 'access_time',
    'description', 'insights', 'trending_up', 'analytics',
    'security', 'verified', 'workspace_premium',
    'arrow_right_alt', 'open_in_new', 'launch',
    'north_east', 'south_east',
]

def qa_check_output(html_content, facts):
    """Post-generation QA gate. Scans output HTML for trust-killing issues.

    Returns:
        dict with 'passed' (bool), 'issues' (list of strings), 'severity' (str)
    """
    issues = []

    # 1. Icon ligature detection — visible text like "arrow_forward" instead of icons
    #    Only flag ligatures NOT properly wrapped in material-icons spans
    for ligature in ICON_LIGATURES:
        # Count total appearances as tag content
        pattern = rf'>\s*{re.escape(ligature)}\s*<'
        total = len(re.findall(pattern, html_content))
        if total > 0:
            # Count properly-wrapped instances (inside material-icons span)
            wrapped_pattern = rf'class="material-icons[^"]*">\s*{re.escape(ligature)}\s*<'
            wrapped = len(re.findall(wrapped_pattern, html_content))
            unwrapped = total - wrapped
            if unwrapped > 0:
                issues.append(f"ICON_LIGATURE: '{ligature}' appears as visible text (missing icon font)")

    # 2. Mojibake / encoding corruption
    mojibake_patterns = [
        (r'[ÃÂ]{2,}', 'UTF-8 double-encoding detected'),
        (r'Î[±-¾]', 'Greek character mojibake (common with special chars)'),
        (r'â€[™"œ]', 'Smart quote mojibake'),
        (r'Ã©|Ã¨|Ã¼|Ã¶|Ã¤', 'Accented character mojibake'),
        (r'Â[©®£°]', 'Latin-1 mojibake (Â© instead of ©)'),
    ]
    for pattern, desc in mojibake_patterns:
        if re.search(pattern, html_content):
            issues.append(f"ENCODING: {desc}")

    # 3. Hallucinated statistics — numbers that don't exist in the original content
    hallucination_patterns = [
        (r'\b\d+\+?\s*(?:years?\s+(?:of\s+)?experience)', 'Years of experience claim'),
        (r'\b(?:Est\.?|Established)\s*\d{4}', 'Establishment year claim'),
        (r'\$[\d,.]+[MBK]|\£[\d,.]+[MBK]', 'Large monetary figure'),
        (r'\b\d+[MBK]\+?\s*(?:clients?|customers?|projects?|assets?)', 'Client/project count'),
        (r'\b(?:offices?\s+in|hubs?\s+in|locations?\s+in)\s+[A-Z][a-z]+', 'Office location claim'),
    ]
    original_text = ' '.join(facts.get('all_content', []) + facts.get('headings', []))
    for pattern, desc in hallucination_patterns:
        matches = re.findall(pattern, html_content, re.I)
        for match in matches:
            # Check if this claim exists in the original content
            if match.lower() not in original_text.lower():
                issues.append(f"HALLUCINATION: '{match}' — {desc} (not in original site)")

    # 3b. Hallucinated contact details (phone numbers, emails not in original)
    # Extract any phone numbers from generated HTML
    generated_phones = re.findall(r'(?:\+\d{1,3}[\s-]?)?\(?\d{1,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', html_content)
    generated_emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', html_content)
    # Filter out false positives from CSS/font URLs (e.g., FILL@100..700 from Google Fonts)
    generated_emails = [e for e in generated_emails if not any(
        x in e.lower() for x in ['fill@', 'wght@', 'opsz@', 'grad@', 'googleapis', 'tailwindcss']
    )]
    for phone in generated_phones:
        phone_clean = re.sub(r'\s', '', phone)
        if len(phone_clean) >= 8 and phone_clean not in ' '.join(facts.get('all_content', [])):
            issues.append(f"HALLUCINATION: '{phone.strip()}' — Phone number not in original site")
            break  # Only flag once
    for email in generated_emails:
        if email not in ' '.join(facts.get('all_content', [])):
            issues.append(f"HALLUCINATION: '{email}' — Email address not in original site")
            break  # Only flag once

    # 3c. Hallucinated copyright year
    copyright_years = re.findall(r'©\s*(\d{4})', html_content)
    for year in copyright_years:
        if year not in ' '.join(facts.get('all_content', [])):
            issues.append(f"HALLUCINATION: '© {year}' — Copyright year not in original site")

    # 4. Missing original CTAs
    original_ctas = facts.get('original_ctas', [])
    if original_ctas:
        found_ctas = 0
        for cta in original_ctas:
            if cta.lower() in html_content.lower():
                found_ctas += 1
        if found_ctas == 0 and len(original_ctas) > 0:
            issues.append(f"DROPPED_CTA: None of the original CTAs preserved: {original_ctas}")

    # 5. Check for basic HTML structure
    if '<meta charset' not in html_content.lower() and 'charset=utf-8' not in html_content.lower():
        issues.append("MISSING_META: No charset meta tag")
    if 'viewport' not in html_content.lower():
        issues.append("MISSING_META: No viewport meta tag")

    # Determine severity
    critical = [i for i in issues if i.startswith(('HALLUCINATION', 'ICON_LIGATURE', 'ENCODING'))]
    warnings = [i for i in issues if i.startswith(('DROPPED_CTA', 'MISSING_META'))]

    if len(critical) >= 3:
        severity = 'FAIL'
    elif critical:
        severity = 'WARN'
    else:
        severity = 'PASS'

    return {
        'passed': severity != 'FAIL',
        'issues': issues,
        'severity': severity,
        'critical_count': len(critical),
        'warning_count': len(warnings),
    }


# --- Post-Generation HTML Fixes ---

def fix_output_html(html_content):
    """Apply automated fixes to Stitch-generated HTML.

    Fixes known issues:
    1. Missing Material Icons CDN → inject it (or replace ligatures with SVG)
    2. Missing UTF-8 charset
    3. Missing viewport meta
    4. Strip visible icon ligature text
    """
    # 1. Inject Material Icons CDN if ligatures are used
    has_ligatures = any(lig in html_content for lig in ICON_LIGATURES[:10])
    if has_ligatures and 'fonts.googleapis.com/icon' not in html_content:
        icon_cdn = '<link href="https://fonts.googleapis.com/icon?family=Material+Icons|Material+Icons+Outlined" rel="stylesheet">'
        if '<head>' in html_content:
            html_content = html_content.replace('<head>', f'<head>\n    {icon_cdn}', 1)
        elif '<HEAD>' in html_content:
            html_content = html_content.replace('<HEAD>', f'<HEAD>\n    {icon_cdn}', 1)

    # 2. Ensure UTF-8 charset
    if '<meta charset' not in html_content.lower():
        if '<head>' in html_content.lower():
            html_content = re.sub(
                r'(<head[^>]*>)',
                r'\1\n    <meta charset="UTF-8">',
                html_content, count=1, flags=re.I
            )

    # 3. Ensure viewport meta
    if 'viewport' not in html_content.lower():
        if '<head>' in html_content.lower():
            html_content = re.sub(
                r'(<head[^>]*>)',
                r'\1\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
                html_content, count=1, flags=re.I
            )

    # 4. Replace standalone ligature text with styled icon spans
    # Only replace ligatures that appear as standalone text content (between tags)
    for lig in ICON_LIGATURES:
        # Replace ">ligature_name<" with ">styled_icon<"
        pattern = rf'(>)\s*{re.escape(lig)}\s*(<)'
        html_content = re.sub(
            pattern,
            rf'\1<span class="material-icons">{lig}</span>\2',
            html_content
        )

    # 5. Fix double-nesting of material-icons spans (Stitch sometimes wraps + we wrap again)
    # Handle cases where outer span has additional classes like "material-icons text-zinc-900"
    html_content = re.sub(
        r'<span class="material-icons[^"]*"><span class="material-icons">([^<]+)</span></span>',
        r'<span class="material-icons">\1</span>',
        html_content
    )

    # 6. Strip hallucinated copyright years (replace with company name only)
    html_content = re.sub(r'©\s*\d{4}\s*', '© ', html_content)

    # 7. Fix common mojibake characters
    mojibake_fixes = {
        'Â©': '©', 'Â®': '®', 'Â£': '£', 'Â°': '°',
        'â€™': "'", 'â€œ': '"', 'â€\x9d': '"', 'â€"': '—', 'â€"': '–',
    }
    for bad, good in mojibake_fixes.items():
        html_content = html_content.replace(bad, good)

    return html_content


# --- Post-Generation Animation Enhancement ---

ANIMATION_CSS = """
<style>
/* Scroll-triggered animations */
[data-animate] {
    opacity: 0;
    transform: translateY(40px);
    transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1),
                transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}
[data-animate].visible {
    opacity: 1;
    transform: translateY(0);
}
[data-animate="fade-up"] { transform: translateY(40px); }
[data-animate="fade-in"] { transform: translateY(0) scale(0.98); }
[data-animate="slide-left"] { transform: translateX(-60px); opacity: 0; }
[data-animate="slide-left"].visible { transform: translateX(0); opacity: 1; }
[data-animate="slide-right"] { transform: translateX(60px); opacity: 0; }
[data-animate="slide-right"].visible { transform: translateX(0); opacity: 1; }

/* Staggered children */
[data-stagger] > * { opacity: 0; transform: translateY(30px);
    transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1),
                transform 0.6s cubic-bezier(0.16, 1, 0.3, 1); }
[data-stagger].visible > *:nth-child(1) { transition-delay: 0ms; }
[data-stagger].visible > *:nth-child(2) { transition-delay: 120ms; }
[data-stagger].visible > *:nth-child(3) { transition-delay: 240ms; }
[data-stagger].visible > *:nth-child(4) { transition-delay: 360ms; }
[data-stagger].visible > *:nth-child(5) { transition-delay: 480ms; }
[data-stagger].visible > * { opacity: 1; transform: translateY(0); }

/* Animated gradient background */
@keyframes gradient-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.animated-gradient {
    background-size: 200% 200%;
    animation: gradient-shift 8s ease infinite;
}

/* Parallax hero */
.parallax-hero {
    will-change: transform;
    transition: transform 0.1s linear;
}

/* Premium button shimmer */
@keyframes shimmer {
    0% { left: -100%; }
    100% { left: 200%; }
}
.btn-shimmer { position: relative; overflow: hidden; }
.btn-shimmer::after {
    content: '';
    position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
    animation: shimmer 3s ease-in-out infinite;
}

/* Smooth image reveal */
img { transition: opacity 0.6s ease, transform 0.6s ease; }
img:hover { transform: scale(1.02); }

/* Line draw animation */
@keyframes line-grow { from { width: 0; } to { width: 100%; } }
.line-reveal { overflow: hidden; }
.line-reveal.visible > div, .line-reveal.visible > span {
    animation: line-grow 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
"""

ANIMATION_JS = """
<script>
// Intersection Observer for scroll animations
document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' });

    document.querySelectorAll('[data-animate], [data-stagger]').forEach(el => {
        observer.observe(el);
    });

    // Parallax on hero
    const hero = document.querySelector('.parallax-hero');
    if (hero) {
        window.addEventListener('scroll', () => {
            const scroll = window.pageYOffset;
            hero.style.transform = `translateY(${scroll * 0.3}px)`;
        }, { passive: true });
    }

    // Add shimmer to primary CTA buttons
    document.querySelectorAll('button, a').forEach(el => {
        const text = el.textContent.trim().toLowerCase();
        if (el.classList.contains('bg-primary') || el.classList.contains('bg-accent') ||
            text.includes('risk talks') || text.includes('get started') || text.includes('contact')) {
            if (el.querySelector('span') || el.childNodes.length <= 3) {
                el.classList.add('btn-shimmer');
            }
        }
    });
});
</script>
"""


def enhance_with_animations(html_content):
    """Inject scroll animations, parallax, and premium effects into generated HTML.

    This is a deterministic post-processing step that always improves output.
    Uses Intersection Observer for scroll-triggered animations and CSS for effects.
    """
    # 1. Inject CSS before </head>
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', f'{ANIMATION_CSS}\n</head>', 1)
    elif '</HEAD>' in html_content:
        html_content = html_content.replace('</HEAD>', f'{ANIMATION_CSS}\n</HEAD>', 1)

    # 2. Inject JS before </body>
    if '</body>' in html_content:
        html_content = html_content.replace('</body>', f'{ANIMATION_JS}\n</body>', 1)
    elif '</BODY>' in html_content:
        html_content = html_content.replace('</BODY>', f'{ANIMATION_JS}\n</BODY>', 1)

    # 3. Add data-animate attributes to sections
    # Each <section> gets a fade-up animation
    section_count = 0
    def add_section_animation(match):
        nonlocal section_count
        section_count += 1
        tag = match.group(0)
        if 'data-animate' in tag or 'data-stagger' in tag:
            return tag  # Already has animation
        # Alternate animation types for visual variety
        anim = 'fade-up' if section_count % 3 != 0 else 'fade-in'
        return tag.rstrip('>') + f' data-animate="{anim}">'
    html_content = re.sub(r'<section[^>]*>', add_section_animation, html_content)

    # 4. Add stagger to grid containers (service cards, footer columns)
    def add_stagger(match):
        tag = match.group(0)
        if 'data-stagger' in tag:
            return tag
        return tag.rstrip('>') + ' data-stagger>'
    # Target grid parents (common Tailwind grid patterns)
    html_content = re.sub(
        r'<div[^>]*class="[^"]*(?:grid\s+(?:grid-cols|gap))[^"]*"[^>]*>',
        add_stagger, html_content
    )

    # 5. Add parallax to hero images
    # Find the first large image in the first section and add parallax class
    first_section = re.search(r'<section[^>]*>.*?</section>', html_content, re.S)
    if first_section:
        section_html = first_section.group(0)
        # Add parallax-hero class to the first img in hero
        modified = re.sub(
            r'(<img[^>]*class="[^"]*)',
            r'\1 parallax-hero',
            section_html, count=1
        )
        html_content = html_content.replace(section_html, modified, 1)

    # 6. Add slide animations to editorial split layouts (left/right columns)
    # Target lg:col-span patterns for editorial splits
    html_content = re.sub(
        r'(<div[^>]*class="[^"]*lg:col-span-[1-5][^"]*"[^>]*)>',
        lambda m: m.group(1) + ' data-animate="slide-left">' if 'col-span-5' in m.group(0) or 'col-span-4' in m.group(0)
        else m.group(1) + ' data-animate="slide-right">',
        html_content
    )

    return html_content


# --- Main redesign function ---

def generate_redesign(slug, prompt=None, branding_path=None, html_path=None, generator='stitch'):
    """Generate a redesign for a single website.

    Args:
        slug: URL-safe identifier (e.g., 'delta-vega')
        prompt: Optional custom prompt. If None, auto-generated from analysis.
        branding_path: Path to branding JSON. Defaults to .tmp/branding/{slug}.json
        html_path: Path to captured HTML. Defaults to .tmp/html/{slug}.html
        generator: 'stitch' (default) or 'v0'

    Returns:
        dict with paths to output files and metadata
    """
    if not branding_path:
        branding_path = f'.tmp/branding/{slug}.json'
    if not html_path:
        html_path = f'.tmp/html/{slug}.html'

    # Run analysis and extract facts
    facts = None
    if not prompt:
        if not os.path.exists(branding_path):
            raise FileNotFoundError(
                f"Branding file not found: {branding_path}\n"
                f"Run capture first: python execution/capture_website_screenshot.py --url ..."
            )
        prompt = build_prompt_from_branding(slug, branding_path, html_path)
    else:
        # Even with custom prompt, extract facts for QA
        if os.path.exists(branding_path):
            analysis = analyze_website(slug, branding_path, html_path)
            facts = extract_facts(slug, analysis)

    # Load facts for QA (may have been saved during prompt building)
    facts_path = f'.tmp/facts/{slug}-facts.json'
    if not facts and os.path.exists(facts_path):
        with open(facts_path, 'r', encoding='utf-8') as f:
            facts = json.load(f)

    print(f"  Generator: {generator}")
    print(f"  Prompt ({len(prompt)} chars): {prompt[:120]}...")

    os.makedirs('.tmp/redesigns', exist_ok=True)
    os.makedirs(f'.tmp/redesigns/history/{slug}', exist_ok=True)

    # --- Generate via selected backend ---
    start_time = time.time()

    if generator == 'v0':
        raw_html, screenshot_url, metadata = _generate_via_v0(slug, prompt)
    else:
        raw_html, screenshot_url, metadata = _generate_via_stitch(slug, prompt)

    elapsed = time.time() - start_time
    print(f"  Generated in {elapsed:.0f}s")

    # --- Post-generation fixes ---
    html_path_out = f'.tmp/redesigns/{slug}-redesign.html'
    fixed_html = fix_output_html(raw_html)
    fix_count = len(fixed_html) - len(raw_html)
    if fix_count != 0:
        print(f"  Applied HTML fixes ({'+' if fix_count > 0 else ''}{fix_count} chars)")

    # --- Animation enhancement ---
    enhanced_html = enhance_with_animations(fixed_html)
    anim_count = len(enhanced_html) - len(fixed_html)
    print(f"  Injected animations (+{anim_count} chars)")

    # --- Design polish (tokens, noise, gradient text, dividers, trust frame) ---
    try:
        from design_polish import polish_design
        pre_polish_len = len(enhanced_html)
        # Try to find original URL from branding or analysis
        original_url = ''
        branding_file = branding_path or f'.tmp/branding/{slug}.json'
        if os.path.exists(branding_file):
            with open(branding_file, 'r', encoding='utf-8') as f:
                bd = json.load(f)
            original_url = bd.get('url', bd.get('metadata', {}).get('sourceURL', ''))
        enhanced_html = polish_design(enhanced_html, slug, original_url=original_url)
        polish_delta = len(enhanced_html) - pre_polish_len
        print(f"  Design polish applied (+{polish_delta} chars)")
    except ImportError:
        print("  Warning: design_polish.py not found, skipping polish step")

    # --- Version history: always save a timestamped copy before overwriting ---
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    version_path = f'.tmp/redesigns/history/{slug}/{slug}-{generator}-{timestamp}.html'
    with open(version_path, 'w', encoding='utf-8') as f:
        f.write(enhanced_html)
    print(f"  Version saved: {version_path}")

    # Save as canonical output (this is the "latest" file for deploy)
    with open(html_path_out, 'w', encoding='utf-8') as f:
        f.write(enhanced_html)
    print(f"  HTML saved: {html_path_out}")

    # --- QA Gate ---
    qa_result = None
    if facts:
        qa_result = qa_check_output(enhanced_html, facts)
        print(f"\n  === QA Result: {qa_result['severity']} ===")
        if qa_result['issues']:
            for issue in qa_result['issues'][:10]:
                prefix = '  !!' if issue.startswith(('HALLUCINATION', 'ICON_LIGATURE', 'ENCODING')) else '  --'
                print(f"  {prefix} {issue}")
            if len(qa_result['issues']) > 10:
                print(f"  ... and {len(qa_result['issues']) - 10} more")
        else:
            print("  No issues found")

        # Save QA report
        os.makedirs('.tmp/qa', exist_ok=True)
        qa_path = f'.tmp/qa/{slug}-qa.json'
        with open(qa_path, 'w', encoding='utf-8') as f:
            json.dump(qa_result, f, indent=2)
        print(f"  QA report: {qa_path}")
    else:
        print("  QA skipped (no facts lock available)")

    # Download screenshot
    screenshot_path = f'.tmp/redesigns/{slug}-redesign.png'
    if screenshot_url:
        try:
            r2 = requests.get(screenshot_url, timeout=30)
            r2.raise_for_status()
            with open(screenshot_path, 'wb') as f:
                f.write(r2.content)
            print(f"  Screenshot saved: {screenshot_path} ({len(r2.content)} bytes)")
        except Exception as e:
            screenshot_path = None
            print(f"  Warning: Screenshot download failed: {e}")
    else:
        screenshot_path = None
        print("  Warning: No screenshot URL in response")

    return {
        'slug': slug,
        'html_path': html_path_out,
        'screenshot_path': screenshot_path,
        'prompt': prompt,
        'elapsed_seconds': elapsed,
        'metadata': metadata,
        'qa': qa_result,
        'generator': generator,
    }


def _generate_via_stitch(slug, prompt):
    """Generate HTML via Stitch MCP subprocess. Returns (html, screenshot_url, metadata)."""
    stitch = StitchMCP()
    stitch.start()
    try:
        print(f"  Creating Stitch project for {slug}...")
        project_id = stitch.create_project(f"{slug} Redesign")
        print(f"  Project ID: {project_id}")

        print(f"  Generating via Stitch (this takes ~90 seconds)...")
        html_url, screenshot_url, metadata = stitch.generate_screen(project_id, prompt)
        print(f"  Stitch done ({metadata.get('width')}x{metadata.get('height')})")

        # Download HTML from Stitch CDN URL
        r = requests.get(html_url, timeout=30)
        r.raise_for_status()
        raw_html = r.text
        print(f"  Raw HTML downloaded: {len(raw_html)} chars")

        return raw_html, screenshot_url, metadata
    finally:
        stitch.stop()


def _generate_via_v0(slug, prompt):
    """Generate HTML via v0 REST API. Returns (html, screenshot_url, metadata)."""
    print(f"  Generating via v0 API...")
    v0 = V0Generator()
    html_content, screenshot_url, metadata = v0.generate(prompt, timeout=180)
    print(f"  v0 done: {len(html_content)} chars, {metadata.get('file_count', '?')} files")
    return html_content, screenshot_url, metadata


# --- Multi-Variant Generation ---

def score_variant(html_content, facts):
    """Auto-score a generated variant on design quality + conversion + truth.

    Three scoring axes (max ~200):
    A. Design Quality (up to 100) — visual sophistication, layout, typography
    B. Conversion Structure (up to 60) — buyer questions answered, CTA clarity
    C. Proof Integrity (up to 40, with heavy penalties for fabrication)
    """
    design_score = 0
    conversion_score = 0
    integrity_score = 40  # Start at max, subtract for violations

    hl = html_content.lower()

    # === A. DESIGN QUALITY (up to 100) ===

    # Section count (more = richer layout)
    sections = len(re.findall(r'<section', html_content))
    design_score += min(sections * 5, 25)

    # HTML size (more content = more detailed)
    design_score += min(len(html_content) // 500, 15)

    # Image count
    images = len(re.findall(r'<img', html_content))
    design_score += min(images * 5, 10)

    # CSS sophistication
    if 'backdrop-filter' in hl:
        design_score += 8  # glassmorphism
    if '@keyframes' in html_content:
        design_score += 5  # custom animations
    if 'gradient' in hl:
        design_score += 4
    if 'blur' in hl:
        design_score += 3
    if 'clamp(' in hl:
        design_score += 3  # fluid typography

    # Grid usage (bento-style layouts)
    if 'col-span-2' in hl or 'col-span-3' in hl:
        design_score += 6
    if 'grid-cols-3' in hl or 'grid-cols-4' in hl:
        design_score += 4

    # Typography variety
    font_sizes = re.findall(r'text-(?:\d+xl|lg|sm|xs|huge)', html_content)
    design_score += min(len(set(font_sizes)) * 2, 8)

    # Font weight variety (mixing 300/400/700/800 = premium feel)
    font_weights = re.findall(r'font-(?:light|normal|medium|semibold|bold|extrabold)', hl)
    design_score += min(len(set(font_weights)) * 2, 6)

    # Negative space / padding signals (premium sites use generous spacing)
    if re.search(r'py-(?:16|20|24|32)', hl) or re.search(r'padding-(?:top|bottom):\s*(?:4|5|6|8)rem', hl):
        design_score += 4

    # Custom style block (not just Tailwind utility — shows sophistication)
    custom_styles = len(re.findall(r'<style[^>]*>.*?</style>', html_content, re.S))
    design_score += min(custom_styles * 3, 6)

    design_score = min(design_score, 100)

    # === B. CONVERSION STRUCTURE (up to 60) ===

    # Hero answers "What is this and why should I care?"
    first_section = re.search(r'<section[^>]*>.*?</section>', html_content, re.S)
    if first_section:
        hero = first_section.group(0).lower()
        # Has a heading
        if re.search(r'<h1', hero):
            conversion_score += 8
        # Has a CTA button
        if re.search(r'<(?:a|button)[^>]*(?:btn|cta|bg-)', hero):
            conversion_score += 8
        # Has a subheading or descriptive text
        if re.search(r'<(?:p|h2|span)[^>]*>[^<]{20,}', hero):
            conversion_score += 6

    # Services section answers "What exactly do I get?"
    if re.search(r'(?:service|offering|what we do|expertise|solution)', hl):
        conversion_score += 8
        # Has structured service items (cards/grid)
        if re.search(r'(?:grid|flex).*(?:service|offering)', hl, re.S):
            conversion_score += 4

    # Proof section answers "Why should I believe you?"
    proof_signals = ['publication', 'talk', 'training', 'client', 'case stud', 'credential',
                     'about us', 'about delta', 'who we', 'our approach', 'methodology']
    proof_found = sum(1 for s in proof_signals if s in hl)
    conversion_score += min(proof_found * 3, 10)

    # CTA section answers "What do I do next?"
    cta_buttons = re.findall(r'<(?:a|button)[^>]*>[^<]*(?:contact|talk|consult|book|get in touch|risk talks)[^<]*</(?:a|button)>', hl)
    conversion_score += min(len(cta_buttons) * 4, 12)

    # Penalty for vague positioning (generic buzzwords without specificity)
    vague_phrases = ['innovative solutions', 'cutting-edge', 'world-class', 'best-in-class',
                     'state-of-the-art', 'next-level', 'synergy', 'leverage our expertise',
                     'unlock your potential', 'transform your business']
    vague_count = sum(1 for v in vague_phrases if v in hl)
    conversion_score -= vague_count * 3

    conversion_score = max(0, min(conversion_score, 60))

    # === C. PROOF INTEGRITY (starts at 40, penalize fabrication) ===

    if facts:
        qa = qa_check_output(html_content, facts)

        # Heavy penalties for hallucination (trust-killing in B2B)
        hallucinations = [i for i in qa['issues'] if 'HALLUCINATION' in i]
        integrity_score -= len(hallucinations) * 15  # -15 per hallucinated claim

        # Moderate penalty for encoding/icon issues
        encoding_issues = [i for i in qa['issues'] if i.startswith(('ENCODING', 'ICON_LIGATURE'))]
        integrity_score -= len(encoding_issues) * 5

        # Penalty for dropped CTAs
        cta_issues = [i for i in qa['issues'] if 'DROPPED_CTA' in i]
        integrity_score -= len(cta_issues) * 10

    integrity_score = max(-30, integrity_score)  # Floor at -30 (net negative for terrible output)

    total = design_score + conversion_score + integrity_score
    return total


def generate_multi_variant(slug, num_variants=3, **kwargs):
    """Generate multiple variants and pick the best one.

    Runs Stitch N times, auto-scores each, keeps the best.
    Saves all variants for manual review if needed.
    """
    print(f"\n=== Multi-Variant Generation: {num_variants} variants ===\n")
    variants = []

    for i in range(num_variants):
        print(f"--- Variant {i+1}/{num_variants} ---")
        try:
            result = generate_redesign(slug, **kwargs)
            # Read back the HTML to score it
            with open(result['html_path'], 'r', encoding='utf-8') as f:
                html = f.read()

            # Load facts for scoring
            facts_path = f'.tmp/facts/{slug}-facts.json'
            facts = None
            if os.path.exists(facts_path):
                with open(facts_path, 'r', encoding='utf-8') as f:
                    facts = json.load(f)

            score = score_variant(html, facts)
            qa_severity = result.get('qa', {}).get('severity', '?')

            # Save variant with index
            variant_path = f'.tmp/redesigns/{slug}-variant-{i+1}.html'
            with open(variant_path, 'w', encoding='utf-8') as f:
                f.write(html)

            variants.append({
                'index': i + 1,
                'score': score,
                'qa_severity': qa_severity,
                'html_path': variant_path,
                'screenshot_path': result.get('screenshot_path'),
                'elapsed': result.get('elapsed_seconds', 0),
                'html_length': len(html),
            })
            print(f"  Score: {score} | QA: {qa_severity} | Size: {len(html)} chars\n")

        except Exception as e:
            print(f"  Variant {i+1} FAILED: {e}\n")

    if not variants:
        raise RuntimeError("All variants failed")

    # Pick the best
    best = max(variants, key=lambda v: v['score'])
    print(f"\n=== Best Variant: #{best['index']} (score: {best['score']}, QA: {best['qa_severity']}) ===")

    # Copy best to the canonical output path
    import shutil
    best_output = f'.tmp/redesigns/{slug}-redesign.html'
    shutil.copy2(best['html_path'], best_output)
    print(f"  Saved as: {best_output}")

    # Save variant comparison report
    report_path = f'.tmp/qa/{slug}-variants.json'
    os.makedirs('.tmp/qa', exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(variants, f, indent=2)
    print(f"  Variant report: {report_path}")

    return best


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
    parser.add_argument('--variants', type=int, default=1,
                        help='Number of variants to generate (picks best)')
    parser.add_argument('--reference-url', help='URL of a well-designed site to reference in prompt')
    parser.add_argument('--generator', choices=['stitch', 'v0'], default='stitch',
                        help='Which AI generator to use (default: stitch)')

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

        elif args.variants > 1:
            # Multi-variant mode
            print(f"Generating {args.variants} variants for: {args.slug}")

            # Append reference URL to prompt if provided
            prompt = args.prompt
            if args.reference_url and not prompt:
                # Build prompt from branding, then append reference
                prompt = build_prompt_from_branding(args.slug, branding_path, html_path)
                prompt += f"\n\nSTYLE REFERENCE: Match the visual quality and sophistication of {args.reference_url} — use it as a design benchmark for layout, typography, and polish."

            best = generate_multi_variant(
                args.slug, num_variants=args.variants,
                prompt=prompt, branding_path=args.branding, html_path=args.html,
                generator=args.generator,
            )
            print(f"\nDone! Best variant: #{best['index']} (score: {best['score']})")
            print(f"  HTML: .tmp/redesigns/{args.slug}-redesign.html")
            print(f"\nNext: deploy with:")
            print(f"  python execution/deploy_redesign.py --slug \"{args.slug}\" "
                  f"--html-file \".tmp/redesigns/{args.slug}-redesign.html\"")

        else:
            # Single redesign
            print(f"Generating redesign for: {args.slug}")

            # Append reference URL to prompt if provided
            prompt = args.prompt
            if args.reference_url and not prompt:
                prompt = build_prompt_from_branding(args.slug, branding_path, html_path)
                prompt += f"\n\nSTYLE REFERENCE: Match the visual quality and sophistication of {args.reference_url} — use it as a design benchmark for layout, typography, and polish."

            result = generate_redesign(
                slug=args.slug,
                prompt=prompt,
                branding_path=args.branding,
                html_path=args.html,
                generator=args.generator,
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
