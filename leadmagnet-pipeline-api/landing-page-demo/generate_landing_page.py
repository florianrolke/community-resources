#!/usr/bin/env python3
"""
Generate a custom landing page from a research brief.

Reads the research brief (from research_client.py), builds a conversion-focused
prompt, generates HTML via v0, and saves the deployable output.

Usage:
    python landing-page-demo/generate_landing_page.py --slug delta-vega
    python landing-page-demo/generate_landing_page.py --slug delta-vega --generator stitch
"""

import os
import sys
import json
import re
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Add execution/ to path so we can import post-processing functions
sys.path.insert(0, str(Path(__file__).parent.parent / 'execution'))

OUTPUT_DIR = Path(__file__).parent / "output"
RESEARCH_DIR = Path(__file__).parent / "output"


# ---------------------------------------------------------------------------
# V0 Generator (copy from execution/generate_redesign.py — standalone)
# ---------------------------------------------------------------------------

class V0Generator:
    """Generate UI via v0.dev Platform API."""

    API_URL = "https://api.v0.dev/v1/chats"

    def __init__(self):
        self.api_key = os.getenv('V0_API_KEY')
        if not self.api_key:
            raise ValueError("V0_API_KEY not found in .env")

    def generate(self, prompt, timeout=180):
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

        messages = data.get('messages', [])
        assistant_msg = None
        for msg in messages:
            if msg.get('role') == 'assistant':
                assistant_msg = msg.get('content', '')
                break

        if not assistant_msg:
            raise RuntimeError("v0 returned no assistant message")

        html_content = None
        code_blocks = re.findall(r'```(?:html)?\s*\n(.*?)```', assistant_msg, re.S)
        for block in code_blocks:
            block = block.strip()
            if '<!DOCTYPE' in block.upper() or '<html' in block.lower() or '<div' in block.lower():
                html_content = block
                break

        if not html_content and '<html' in assistant_msg.lower():
            match = re.search(r'(<!DOCTYPE[^>]*>.*</html>)', assistant_msg, re.S | re.I)
            if match:
                html_content = match.group(1)

        if not html_content:
            raise RuntimeError(
                f"v0 response contained no HTML code block. "
                f"Response preview: {assistant_msg[:300]}..."
            )

        return html_content, {
            'chat_url': data.get('webUrl', data.get('url', '')),
            'chat_id': data.get('id', ''),
            'generated_by': 'v0',
        }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_landing_page_prompt(brief):
    """Build a conversion-focused landing page prompt from the research brief."""

    company = brief.get('company_name', 'Company')
    url = brief.get('url', '')
    logo_url = brief.get('logo_url', '')
    colors = brief.get('colors', {})
    branding = brief.get('branding', {})
    site_info = brief.get('site_info', {})
    research = brief.get('perplexity_research', '')
    ctas = site_info.get('ctas', [])

    # Extract useful bits
    headings = site_info.get('headings', [])
    contact = site_info.get('contact_info', {})
    about = site_info.get('about_text', '')

    # --- Brand fonts ---
    fonts = branding.get('fonts', [])
    font_names = []
    for f in fonts:
        if isinstance(f, dict):
            font_names.append(f.get('family', ''))
        elif isinstance(f, str):
            font_names.append(f)
    font_names = [f for f in font_names if f]

    if font_names:
        heading_font = font_names[0]
        body_font = font_names[1] if len(font_names) > 1 else font_names[0]
        google_import = '+'.join(f.replace(' ', '+') for f in font_names[:2])
        font_instruction = (
            f'FONTS: Use "{heading_font}" for headings, "{body_font}" for body. '
            f'Include: <link href="https://fonts.googleapis.com/css2?family='
            f'{google_import}:wght@300;400;600;700;800&display=swap" rel="stylesheet">. '
            f'Configure in both CSS and Tailwind config.'
        )
    else:
        font_instruction = "FONTS: Use Inter for all text."

    # --- Brand colors ---
    primary = colors.get('primary', branding.get('colors', {}).get('primary', ''))
    accent = colors.get('accent', branding.get('colors', {}).get('accent', ''))
    bg = colors.get('background', branding.get('colors', {}).get('background', '#FFFFFF'))
    text_color = colors.get('textPrimary', '#FFFFFF' if bg and bg.lower().startswith('#0') else '#000000')
    is_dark = bg.lower() in ('#000', '#000000', '#000103', '#111', '#1a1a1a', '#0d0d0d') if bg else False

    # --- Button style ---
    btn = branding.get('components', {}).get('buttonPrimary', {})
    btn_bg = btn.get('background', accent or primary)
    btn_text = btn.get('textColor', text_color)
    btn_radius = btn.get('borderRadius', '8px')

    # --- Favicon ---
    favicon = branding.get('images', {}).get('favicon', '')
    favicon_line = f'- Favicon: include <link rel="icon" href="{favicon}">' if favicon else ''

    # --- CTA ---
    hero_cta = ctas[0] if ctas else "Request a Demo"

    # --- Contact ---
    contact_parts = []
    if contact.get('email'):
        contact_parts.append(f"Email: {contact['email']}")
    if contact.get('phone'):
        contact_parts.append(f"Phone: {contact['phone']}")
    contact_block = ", ".join(contact_parts) if contact_parts else "No contact info found"

    prompt = f"""Design a premium, high-converting landing page for "{company}" ({url}).
This must look like a £15,000 agency build — think Pentagram or DesignStudio quality.

## Company Research
{research if research else f"Company website content: {about}"}

## Brand Identity (MUST MATCH EXACTLY)
- {font_instruction}
- COLORS: primary={primary}, accent={accent}, background={bg}, text={text_color}. Configure in Tailwind config extend.colors.
- BUTTONS: background {btn_bg}, text {btn_text}, border-radius {btn_radius}. Secondary: outline with border {accent}.
- LOGO: {"<img src='" + logo_url + "' alt='" + company + " logo' class='h-10 w-auto'>" if logo_url else "'" + company + "' as styled text in heading font"}
{favicon_line}

## Content from their site
Headings: {', '.join(headings[:8]) if headings else 'None'}
About: {about[:300] if about else 'Not available'}
Contact: {contact_block}

## Page Structure

### 1. Navigation
- {"Logo image" if logo_url else "Company name as text logo"}, horizontal nav: Home, About, Services, Contact
- Sticky with backdrop blur, mobile hamburger

### 2. Hero — "What is this and why should I care?"
- Full viewport, {"dark background" if is_dark else "light with dark accents"}
- Oversized heading (80-120px, font-extrabold, tight tracking)
- Subtitle: one benefit sentence from research
- CTA: "{hero_cta}" with brand button style + glow
- Visual: gradient orb or abstract shapes (NO stock photos)

### 3. About / Trust — "Why should I trust them?"
- Editorial: bold heading left, real text right
- ONLY facts from research — NO invented stats, years, clients, testimonials

### 4. Services — "What exactly do I get?"
- Bento grid, 3-4 services from research
- Each: SVG icon + title + 1 sentence
- Cards: {"glassmorphism (backdrop-blur + bg-white/5)" if is_dark else "elevated shadow-2xl"}, hover lift

### 5. CTA — "What do I do next?"
- Full-width accent section, invitation headline, "{hero_cta}" button
- {"Contact: " + contact.get('email', '') if contact.get('email') else ""}

### 6. Footer
- Company name + nav links
- {f"Contact: {contact_block}" if contact_parts else "No invented contact details"}

## Premium Design Language (non-negotiable)
- TYPE SCALE: Hero heading clamp(44px, 5vw, 96px) font-extrabold. H2 clamp(28px, 2.5vw, 48px). Body clamp(15px, 1.1vw, 18px). Mix weights: 800 for headings, 300 for subheads, 400 for body.
- SPACING: Section padding clamp(56px, 7vw, 112px). Never less than 48px between sections.
- SURFACES: Cards use backdrop-filter:blur(10px) + rgba background + 1px border rgba(255,255,255,0.08). Hover: translateY(-4px) + deeper shadow.
- BACKGROUNDS: Alternate {"dark/slightly-lighter" if is_dark else "light/dark"} sections for visual rhythm. Dark sections use subtle radial gradient highlight behind content.
- COLOR DISCIPLINE: Max 3 colors visible at once. Accent ONLY on CTAs and key highlights.
- Scroll-triggered fade-in animations (IntersectionObserver)
- NO placeholder images, NO fabricated content
- NO Material Icons ligatures (use inline SVG only)
- Fully responsive (mobile-first Tailwind)
"""

    return prompt


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Generate a landing page from research brief')
    parser.add_argument('--slug', required=True, help='Site identifier (e.g., delta-vega)')
    parser.add_argument('--generator', default='v0', choices=['v0', 'stitch'],
                        help='Generator to use (default: v0)')
    args = parser.parse_args()

    print(f"\n=== Generating landing page for: {args.slug} ===\n")

    # Step 1: Load research brief
    brief_path = RESEARCH_DIR / args.slug / "research-brief.json"
    if not brief_path.exists():
        print(f"  Error: No research brief found at {brief_path}")
        print(f"  Run first: python landing-page-demo/research_client.py --url <URL> --slug {args.slug}")
        sys.exit(1)

    with open(brief_path, 'r', encoding='utf-8') as f:
        brief = json.load(f)
    print(f"  Loaded research brief: {brief_path}")
    print(f"  Company: {brief.get('company_name', 'Unknown')}")

    # Step 2: Build prompt
    prompt = build_landing_page_prompt(brief)
    print(f"  Prompt built: {len(prompt)} chars")

    # Step 3: Generate
    print(f"\n  Generating via {args.generator}...")
    start = time.time()

    if args.generator == 'v0':
        gen = V0Generator()
        html, metadata = gen.generate(prompt)
    else:
        print("  Stitch generator not implemented for landing pages yet. Use --generator v0")
        sys.exit(1)

    elapsed = time.time() - start
    print(f"  Generated in {elapsed:.1f}s ({len(html)} chars)")

    # Step 4: Inject logo if we have one and it's not already in the HTML
    logo_url = brief.get('logo_url', '')
    if logo_url and logo_url not in html:
        # Try to find a text-only logo placeholder and replace with img
        company = brief.get('company_name', '')
        if company.upper() in html:
            # Replace the first occurrence of the company name in nav with logo img
            html = html.replace(
                f'>{company.upper()}<',
                f'><img src="{logo_url}" alt="{company}" class="h-8 w-auto"> {company.upper()}<',
                1
            )
            print(f"  Injected logo image into HTML")

    # Step 4b: Post-processing (same chain as UC1 redesigns)
    try:
        from generate_redesign import fix_output_html, enhance_with_animations, qa_check_output

        # Fix HTML issues (meta tags, mojibake, icon ligatures)
        raw_len = len(html)
        html = fix_output_html(html)
        fix_delta = len(html) - raw_len
        if fix_delta != 0:
            print(f"  Applied HTML fixes ({'+' if fix_delta > 0 else ''}{fix_delta} chars)")

        # Inject scroll animations
        pre_anim_len = len(html)
        html = enhance_with_animations(html)
        anim_delta = len(html) - pre_anim_len
        print(f"  Injected animations (+{anim_delta} chars)")

        # QA gate
        facts_path = Path(f'.tmp/facts/{args.slug}-facts.json')
        if facts_path.exists():
            with open(facts_path, 'r', encoding='utf-8') as f:
                facts = json.load(f)
            qa_result = qa_check_output(html, facts)
            print(f"  QA: {qa_result['severity']} ({qa_result['critical_count']} critical, {qa_result['warning_count']} warnings)")
            if qa_result['issues']:
                for issue in qa_result['issues'][:5]:
                    print(f"    {'!!' if 'HALLUCINATION' in issue else '--'} {issue}")
        else:
            print(f"  QA skipped (no facts lock at {facts_path})")

    except ImportError as e:
        print(f"  Warning: Could not import post-processing functions: {e}")
        print(f"  Landing page will ship without HTML fixes or animations.")

    # Step 4c: Design polish (tokens, noise, gradient text, dividers, trust frame)
    try:
        from design_polish import polish_design
        pre_polish_len = len(html)
        original_url = brief.get('url', '')
        html = polish_design(html, args.slug, original_url=original_url)
        polish_delta = len(html) - pre_polish_len
        print(f"  Design polish applied (+{polish_delta} chars)")
    except ImportError as e:
        print(f"  Warning: Could not import design_polish: {e}")

    # Step 5: Save output
    output_dir = OUTPUT_DIR / args.slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save with timestamp to history
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    history_dir = output_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"landing-{args.generator}-{timestamp}.html"
    with open(history_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  History saved: {history_path}")

    # Save canonical output
    canonical_path = output_dir / "index.html"
    with open(canonical_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Output saved: {canonical_path}")

    # Save generation metadata
    meta = {
        'slug': args.slug,
        'generator': args.generator,
        'timestamp': timestamp,
        'elapsed_seconds': round(elapsed, 1),
        'html_size': len(html),
        'prompt_size': len(prompt),
        'logo_url': logo_url,
        **metadata,
    }
    meta_path = output_dir / "generation-meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    print(f"\n=== Done! ===")
    print(f"  Preview: open {canonical_path} in browser")
    print(f"  Deploy:  python execution/deploy_redesign.py --slug \"{args.slug}\" --html-file \"{canonical_path}\"")
    print(f"  Live at: https://{args.slug}.client.of.florianrolke.com")


if __name__ == '__main__':
    main()
