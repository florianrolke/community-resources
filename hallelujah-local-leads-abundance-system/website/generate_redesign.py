#!/usr/bin/env python3
"""
Generate a luxury website redesign using Claude API + component library.

Reads the prospect's site analysis, selects matching components from the
catalog, and generates a complete HTML redesign via Claude.

Flow:
  1. Load analysis (scores + gaps) from analyze_site.py output
  2. Select industry palette + inspiration recipe
  3. Build targeted Claude prompt with component code
  4. Generate single-file HTML (Tailwind CSS via CDN)

Usage:
    python website/generate_redesign.py --slug example-corp --analysis .tmp/analysis/example.json
    python website/generate_redesign.py --slug example-corp --industry finance --style delta-vega
    python website/generate_redesign.py --slug example-corp --industry tech --output .tmp/redesigns/example.html
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path

# Windows UTF-8 fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from lib.safe_io import safe_json_write, safe_json_read

# Industry → palette filename mapping
INDUSTRY_MAP = {
    'finance': 'finance-law', 'law': 'finance-law', 'consulting': 'finance-law',
    'accounting': 'finance-law', 'insurance': 'finance-law', 'wealth': 'finance-law',
    'real-estate': 'real-estate', 'property': 'real-estate', 'mortgage': 'real-estate',
    'tech': 'tech-saas', 'saas': 'tech-saas', 'software': 'tech-saas', 'ai': 'tech-saas',
    'construction': 'construction', 'roofing': 'construction', 'trades': 'construction',
    'hvac': 'construction', 'plumbing': 'construction', 'electric': 'construction',
    'restaurant': 'hospitality', 'food': 'hospitality', 'hotel': 'hospitality',
    'cafe': 'hospitality', 'bar': 'hospitality', 'catering': 'hospitality',
    'medspa': 'medspa', 'beauty': 'medspa', 'wellness': 'medspa',
    'dental': 'medspa', 'spa': 'medspa', 'aesthetic': 'medspa',
}

# Inspiration style → filename mapping
INSPIRATION_MAP = {
    'populon': 'populon',
    'dunkertons': 'dunkertons',
    'driveby': 'driveby',
    'delta-vega': 'delta-vega-luxury',
    'teamsiok': 'teamsiok-luxury',
    'ezhomes': 'ezhomesfast-luxury',
}

# Default component selections by industry
DEFAULT_COMPONENTS = {
    'finance-law': ['scroll-reveal', 'glassmorphism', 'gradient-text', 'gold-gradient-line',
                    'sticky-blur-nav', 'pill-glow', 'counter-stats'],
    'real-estate': ['scroll-reveal', 'bento-grid', 'numbered-feature', 'metallic-shimmer',
                    'ghost-outline', 'counter-stats', 'pill-glow'],
    'tech-saas': ['scroll-reveal', 'dot-rhombus', 'gradient-text', 'glassmorphism',
                  'sticky-blur-nav', 'pill-glow', 'marquee-ticker'],
    'construction': ['scroll-reveal', 'hover-lift', 'pill-glow', 'counter-stats',
                     'diagonal-clip', 'ghost-outline'],
    'hospitality': ['scroll-reveal', 'image-hero-kenburns', 'wave-svg',
                    'environmental-bleed', 'marquee-ticker', 'pill-glow'],
    'medspa': ['scroll-reveal', 'glassmorphism', 'gradient-text', 'gold-gradient-line',
               'pill-glow', 'ghost-outline'],
}

WEBSITE_DIR = os.path.dirname(__file__)


def find_component_file(name):
    """Find a component markdown file by name across all subdirectories."""
    components_dir = os.path.join(WEBSITE_DIR, 'components')
    for root, dirs, files in os.walk(components_dir):
        for f in files:
            if f.replace('.md', '') == name:
                return os.path.join(root, f)
    return None


def load_component(name):
    """Load a component's markdown content. Returns the full text."""
    path = find_component_file(name)
    if not path or not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def load_palette(industry):
    """Load an industry palette markdown file."""
    palette_name = INDUSTRY_MAP.get(industry, industry)
    path = os.path.join(WEBSITE_DIR, 'components', 'industry-palettes', f'{palette_name}.md')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def load_inspiration(style):
    """Load an inspiration recipe markdown file."""
    filename = INSPIRATION_MAP.get(style, style)
    path = os.path.join(WEBSITE_DIR, 'inspirations', f'{filename}.md')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def select_components(industry, gaps=None):
    """Select components based on industry and identified gaps."""
    palette_name = INDUSTRY_MAP.get(industry, 'tech-saas')
    components = list(DEFAULT_COMPONENTS.get(palette_name, DEFAULT_COMPONENTS['tech-saas']))

    if gaps:
        gap_text = ' '.join(gaps).lower()
        if 'testimonial' in gap_text or 'social proof' in gap_text:
            if 'counter-stats' not in components:
                components.append('counter-stats')
        if 'animation' in gap_text or 'static' in gap_text:
            if 'scroll-reveal' not in components:
                components.insert(0, 'scroll-reveal')
        if 'hero' in gap_text:
            if 'image-hero-kenburns' not in components:
                components.insert(0, 'image-hero-kenburns')

    return components


def build_prompt(slug, analysis=None, palette_content=None, component_contents=None,
                 inspiration_content=None, company_name=None):
    """Build the Claude prompt for generating the redesign HTML."""
    company = company_name or slug.replace('-', ' ').title()

    prompt_parts = [
        "Generate a COMPLETE, standalone HTML file for a luxury website redesign.",
        f"Company: {company}",
        "",
        "CRITICAL REQUIREMENTS:",
        "- Output a single HTML file with inline CSS and JS",
        '- Include <script src="https://cdn.tailwindcss.com"></script> in <head>',
        "- Dark background (#0a0a0f or similar deep color)",
        "- Mobile responsive (use Tailwind responsive classes)",
        "- Sections: sticky nav, hero, features/services, social proof/stats, about, CTA, footer",
        "- Professional copy (use realistic placeholder text, not lorem ipsum)",
        "- Return ONLY the HTML code — no explanation text",
        "",
    ]

    # Add palette
    if palette_content:
        prompt_parts.append("INDUSTRY PALETTE (use these exact CSS variables):")
        prompt_parts.append(palette_content[:2000])
        prompt_parts.append("")

    # Add analysis context
    if analysis:
        scores = analysis.get('scores', {})
        gaps = analysis.get('gaps', [])
        strengths = analysis.get('strengths', [])

        prompt_parts.append(f"CURRENT SITE SCORE: {scores.get('overall', '?')}/10")
        if gaps:
            prompt_parts.append("GAPS TO FIX (prioritize these):")
            for gap in gaps[:6]:
                prompt_parts.append(f"  - {gap}")
        if strengths:
            prompt_parts.append("STRENGTHS TO PRESERVE:")
            for s in strengths[:4]:
                prompt_parts.append(f"  + {s}")
        prompt_parts.append("")

    # Add inspiration recipe
    if inspiration_content:
        prompt_parts.append("INSPIRATION RECIPE (follow this component layout):")
        prompt_parts.append(inspiration_content[:3000])
        prompt_parts.append("")

    # Add component code
    if component_contents:
        prompt_parts.append("COMPONENT CODE (inject these into the appropriate sections):")
        for name, content in component_contents.items():
            if content:
                # Extract just the code blocks from the component markdown
                code_blocks = re.findall(r'```(?:html|css|js)?\s*\n(.*?)```', content, re.S)
                if code_blocks:
                    prompt_parts.append(f"\n--- {name} ---")
                    for block in code_blocks[:2]:  # max 2 blocks per component
                        prompt_parts.append(block.strip()[:1500])
        prompt_parts.append("")

    return '\n'.join(prompt_parts)


def generate_html_via_claude(prompt, max_tokens=8000):
    """Call Claude API to generate HTML."""
    import anthropic

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    print("  Calling Claude API...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": prompt
        }],
        system="You are an expert luxury web designer. Generate complete, production-ready HTML. Output ONLY the HTML code, no explanation."
    )

    # Extract text content
    text = ''
    for block in response.content:
        if block.type == 'text':
            text += block.text

    # Extract HTML from response (may be wrapped in code blocks)
    html = text
    code_blocks = re.findall(r'```(?:html)?\s*\n(.*?)```', text, re.S)
    for block in code_blocks:
        if '<!DOCTYPE' in block.upper() or '<html' in block.lower():
            html = block
            break

    # Fallback: extract raw HTML
    if '<html' not in html.lower():
        match = re.search(r'(<!DOCTYPE[^>]*>.*</html>)', text, re.S | re.I)
        if match:
            html = match.group(1)

    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    print(f"  Generated {len(html):,} chars ({tokens_used:,} tokens)")

    return html


def generate_redesign(slug, analysis_path=None, industry=None, style=None,
                      company=None, output_path=None):
    """Full redesign generation pipeline.

    Returns dict with html_path, tokens_used, components_used.
    """
    # Load analysis if provided
    analysis = None
    if analysis_path and os.path.exists(analysis_path):
        analysis = safe_json_read(analysis_path)
        print(f"  Loaded analysis: {analysis_path}")

    # Determine industry
    if not industry:
        industry = 'tech'  # default

    # Load palette
    palette_content = load_palette(industry)
    palette_name = INDUSTRY_MAP.get(industry, industry)
    print(f"  Palette: {palette_name}")

    # Load inspiration if specified
    inspiration_content = None
    if style:
        inspiration_content = load_inspiration(style)
        if inspiration_content:
            print(f"  Inspiration: {style}")

    # Select and load components
    gaps = analysis.get('gaps', []) if analysis else []
    component_names = select_components(industry, gaps)
    component_contents = {}
    for name in component_names:
        content = load_component(name)
        if content:
            component_contents[name] = content

    print(f"  Components: {len(component_contents)}/{len(component_names)} loaded")

    # Build prompt
    prompt = build_prompt(
        slug, analysis, palette_content, component_contents,
        inspiration_content, company
    )

    # Generate HTML
    html = generate_html_via_claude(prompt)

    # Save output
    if not output_path:
        output_path = f'.tmp/redesigns/{slug}-redesign.html'
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  Saved: {output_path} ({os.path.getsize(output_path):,} bytes)")

    return {
        'html_path': output_path,
        'components_used': list(component_contents.keys()),
        'palette': palette_name,
        'industry': industry,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate a luxury website redesign')
    parser.add_argument('--slug', required=True, help='Project slug')
    parser.add_argument('--analysis', help='Path to analysis JSON from analyze_site.py')
    parser.add_argument('--industry', help='Industry: finance, tech, construction, hospitality, medspa, real-estate')
    parser.add_argument('--style', help='Inspiration: populon, delta-vega, driveby, dunkertons, teamsiok, ezhomes')
    parser.add_argument('--company', help='Company name (default: derived from slug)')
    parser.add_argument('--output', help='Output HTML path')

    args = parser.parse_args()

    print(f"Generating redesign: {args.slug}")
    result = generate_redesign(
        slug=args.slug,
        analysis_path=args.analysis,
        industry=args.industry,
        style=args.style,
        company=args.company,
        output_path=args.output,
    )

    print(f"\nRedesign complete:")
    print(f"  HTML: {result['html_path']}")
    print(f"  Components: {', '.join(result['components_used'])}")
    print(f"  Palette: {result['palette']}")


if __name__ == '__main__':
    main()
