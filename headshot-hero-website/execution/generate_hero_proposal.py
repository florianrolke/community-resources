#!/usr/bin/env python3
"""
Skill 2: Hero Clone + Personalized Proposal Page

Extracts the hero/header section from a captured website and builds
a personalized proposal page: their exact hero on top + custom pitch below.

Output: .tmp/proposals/{slug}-proposal.html

Usage:
    python execution/generate_hero_proposal.py \\
        --slug example \\
        --first-name "John" \\
        --company-name "Example Corp" \\
        --pain-point "Your website doesn't convert visitors" \\
        --opportunity "A premium web presence that drives leads" \\
        --offer "Complete website redesign with conversion optimization" \\
        --cta-link "https://calendly.com/you/discovery"

    # Template mode (placeholders preserved for batch processing):
    python execution/generate_hero_proposal.py --slug example --template-mode
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

HTML_DIR = ".tmp/html"
BRANDING_DIR = ".tmp/branding"
PROPOSAL_DIR = ".tmp/proposals"


def extract_hero_section(html: str) -> tuple:
    """
    Extract the hero/header section from HTML.
    Returns (hero_html, head_content) tuple.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'html.parser')

    # Extract <head> content (styles, fonts, meta)
    head = soup.find('head')
    head_content = str(head) if head else "<head><meta charset='UTF-8'></head>"

    # Strategy 1: Look for <header> tag
    hero = soup.find('header')

    # Strategy 2: Look for section with hero-like class
    if not hero:
        for section in soup.find_all(['section', 'div']):
            classes = ' '.join(section.get('class', []))
            if any(kw in classes.lower() for kw in ['hero', 'banner', 'jumbotron', 'masthead', 'landing']):
                hero = section
                break

    # Strategy 3: First section or div that's a direct child of body
    if not hero:
        body = soup.find('body')
        if body:
            for child in body.children:
                if hasattr(child, 'name') and child.name in ['section', 'div', 'header', 'main']:
                    hero = child
                    break

    # Strategy 4: Just take the nav + first section
    if not hero:
        nav = soup.find('nav')
        first_section = soup.find('section')
        if nav and first_section:
            hero_html = str(nav) + '\n' + str(first_section)
            return hero_html, head_content

    if hero:
        # Also grab the nav if it exists before the hero
        nav = soup.find('nav')
        nav_html = str(nav) + '\n' if nav and hero != nav else ''
        return nav_html + str(hero), head_content

    # Fallback: return first 30% of body content
    body = soup.find('body')
    if body:
        body_str = str(body)
        cutoff = len(body_str) // 3
        return body_str[:cutoff], head_content

    return "<div>Hero section not found</div>", head_content


def load_branding(slug: str) -> dict:
    """Load branding data if available."""
    branding_path = os.path.join(BRANDING_DIR, f"{slug}.json")
    if os.path.exists(branding_path):
        with open(branding_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Also check clone directory
    clone_branding = os.path.join(".tmp/clones", slug, "branding.json")
    if os.path.exists(clone_branding):
        with open(clone_branding, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def build_proposal_html(
    hero_html: str,
    head_content: str,
    branding: dict,
    first_name: str = "{{first_name}}",
    company_name: str = "{{company_name}}",
    pain_point: str = "{{pain_point}}",
    opportunity: str = "{{opportunity}}",
    offer: str = "{{offer}}",
    cta_link: str = "{{cta_link}}",
) -> str:
    """Build the complete proposal page: hero + personalized sections."""

    # Extract brand colors
    colors = branding.get('colors', {})
    primary = colors.get('primary', '#1a1a2e')
    accent = colors.get('accent', '#e94560')
    background = colors.get('background', '#ffffff')
    text_color = colors.get('textPrimary', colors.get('text', '#333333'))

    # Extract fonts — handle Firecrawl's nested structure
    typography = branding.get('typography', {})
    font_families = typography.get('fontFamilies', {}) if isinstance(typography, dict) else {}
    heading_font = font_families.get('heading', 'Inter')
    body_font = font_families.get('primary', font_families.get('body', 'Inter'))

    # Fallback: parse fonts list
    if heading_font == 'Inter' and branding.get('fonts'):
        fonts_list = branding['fonts']
        if isinstance(fonts_list, list):
            for f in fonts_list:
                if isinstance(f, dict):
                    if f.get('role') == 'heading':
                        heading_font = f.get('family', heading_font)
                    elif f.get('role') == 'body':
                        body_font = f.get('family', body_font)

    proposal_html = f"""<!DOCTYPE html>
<html lang="en">
{head_content}
<style>
  /* Proposal section styling — uses brand colors */
  .proposal-section {{
    font-family: '{body_font}', 'Inter', -apple-system, sans-serif;
    color: {text_color};
    background: {background};
  }}
  .proposal-container {{
    max-width: 720px;
    margin: 0 auto;
    padding: 80px 24px;
  }}
  .proposal-divider {{
    width: 60px;
    height: 3px;
    background: {accent};
    margin: 0 auto 48px auto;
    border-radius: 2px;
  }}
  .proposal-hook {{
    font-family: '{heading_font}', 'Inter', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 16px;
    color: {primary};
  }}
  .proposal-subhook {{
    font-size: 1.15rem;
    line-height: 1.7;
    margin-bottom: 40px;
    color: {text_color};
    opacity: 0.85;
  }}
  .proposal-h3 {{
    font-family: '{heading_font}', 'Inter', sans-serif;
    font-size: 1.4rem;
    font-weight: 600;
    margin-bottom: 12px;
    color: {primary};
  }}
  .proposal-text {{
    font-size: 1.05rem;
    line-height: 1.8;
    margin-bottom: 32px;
    color: {text_color};
    opacity: 0.8;
  }}
  .proposal-cta-section {{
    text-align: center;
    padding: 48px 0;
    margin-top: 32px;
    border-top: 1px solid rgba(0,0,0,0.08);
  }}
  .proposal-cta-btn {{
    display: inline-block;
    padding: 16px 40px;
    background: {accent};
    color: white;
    font-family: '{heading_font}', 'Inter', sans-serif;
    font-weight: 600;
    font-size: 1.1rem;
    text-decoration: none;
    border-radius: 999px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }}
  .proposal-cta-btn:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  }}
  .proposal-footer {{
    text-align: center;
    padding: 24px;
    font-size: 0.85rem;
    color: {text_color};
    opacity: 0.4;
  }}
</style>
<body>

  <!-- ===== HERO SECTION (Exact Clone) ===== -->
  {hero_html}

  <!-- ===== PERSONALIZED PROPOSAL ===== -->
  <div class="proposal-section">
    <div class="proposal-container">
      <div class="proposal-divider"></div>

      <h2 class="proposal-hook">A Quick Idea for {company_name}</h2>
      <p class="proposal-subhook">
        Hi {first_name} &mdash; I took a close look at your current website and noticed something.
      </p>

      <h3 class="proposal-h3">What I Noticed</h3>
      <p class="proposal-text">
        {pain_point}
      </p>

      <h3 class="proposal-h3">The Opportunity</h3>
      <p class="proposal-text">
        {opportunity}
      </p>

      <h3 class="proposal-h3">How We Could Work Together</h3>
      <p class="proposal-text">
        {offer}
      </p>

      <div class="proposal-cta-section">
        <a href="{cta_link}" class="proposal-cta-btn">
          Let's Explore This Together
        </a>
        <p style="margin-top: 16px; font-size: 0.9rem; opacity: 0.5;">
          No commitment &mdash; just a quick 15-minute conversation.
        </p>
      </div>
    </div>

    <div class="proposal-footer">
      This page was personalized for {company_name}
    </div>
  </div>

</body>
</html>"""

    return proposal_html


def generate_hero_proposal(
    slug: str,
    first_name: str = "{{first_name}}",
    company_name: str = "{{company_name}}",
    pain_point: str = "{{pain_point}}",
    opportunity: str = "{{opportunity}}",
    offer: str = "{{offer}}",
    cta_link: str = "{{cta_link}}",
    deploy: bool = False,
) -> dict:
    """
    Generate a hero clone + personalized proposal page.

    Returns dict with: html_path, error
    """
    result = {"html_path": None, "error": None}

    # Load captured HTML
    html_path = os.path.join(HTML_DIR, f"{slug}.html")
    clone_path = os.path.join(".tmp/clones", slug, "index.html")

    source_path = html_path if os.path.exists(html_path) else clone_path
    if not os.path.exists(source_path):
        result["error"] = f"No captured HTML found at {html_path} or {clone_path}. Run capture first."
        print(f"ERROR: {result['error']}")
        return result

    with open(source_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    print(f"Loaded {len(html)} chars from {source_path}")

    # Extract hero section
    hero_html, head_content = extract_hero_section(html)
    print(f"Extracted hero section: {len(hero_html)} chars")

    # Load branding
    branding = load_branding(slug)
    if branding:
        print(f"Loaded branding: {list(branding.keys())}")

    # Build proposal page
    proposal = build_proposal_html(
        hero_html=hero_html,
        head_content=head_content,
        branding=branding,
        first_name=first_name,
        company_name=company_name,
        pain_point=pain_point,
        opportunity=opportunity,
        offer=offer,
        cta_link=cta_link,
    )

    # Save
    os.makedirs(PROPOSAL_DIR, exist_ok=True)
    output_path = os.path.join(PROPOSAL_DIR, f"{slug}-proposal.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(proposal)
    result["html_path"] = output_path
    print(f"Saved proposal: {output_path}")

    # Deploy if requested
    if deploy:
        print(f"\n  Deploying {slug}-proposal to live server...")
        import subprocess
        deploy_cmd = [
            sys.executable, "execution/deploy_redesign.py",
            "--slug", f"{slug}-proposal",
            "--html-file", output_path,
            "--type", "landing",
        ]
        proc = subprocess.run(deploy_cmd, capture_output=True, text=True, timeout=300,
                              encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            print(f"  Deployed to: {slug}-proposal.client.of.florianrolke.com")
        else:
            print(f"  Deploy failed: {proc.stderr[:500]}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate hero clone + personalized proposal page")
    parser.add_argument("--slug", required=True, help="Slug (must match captured HTML)")
    parser.add_argument("--first-name", default="{{first_name}}", help="Prospect's first name")
    parser.add_argument("--company-name", default="{{company_name}}", help="Company name")
    parser.add_argument("--pain-point", default="{{pain_point}}", help="Observed pain point")
    parser.add_argument("--opportunity", default="{{opportunity}}", help="Growth opportunity")
    parser.add_argument("--offer", default="{{offer}}", help="Your offer/partnership angle")
    parser.add_argument("--cta-link", default="{{cta_link}}", help="Calendar/booking link")
    parser.add_argument("--template-mode", action="store_true", help="Keep all placeholders intact")
    parser.add_argument("--deploy", action="store_true", help="Deploy to live server")

    args = parser.parse_args()

    generate_hero_proposal(
        slug=args.slug,
        first_name=args.first_name,
        company_name=args.company_name,
        pain_point=args.pain_point,
        opportunity=args.opportunity,
        offer=args.offer,
        cta_link=args.cta_link,
        deploy=args.deploy,
    )
