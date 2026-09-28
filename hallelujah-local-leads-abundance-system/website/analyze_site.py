#!/usr/bin/env python3
"""
Analyze a website's design quality and identify improvement gaps.

Scores the site across 10 categories (0-10 each):
- Visual hierarchy, layout, CTA, typography, color, social proof,
  content quality, modern features, imagery, mobile readiness

Outputs actionable gaps and strengths for redesign targeting.

Usage:
    python website/analyze_site.py --html .tmp/captures/example/page.html
    python website/analyze_site.py --html .tmp/captures/example/page.html --branding .tmp/captures/example/branding.json
    python website/analyze_site.py --html .tmp/captures/example/page.html --output .tmp/analysis/example.json
"""

import os
import sys
import re
import json
import argparse
from collections import Counter

# Windows UTF-8 fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.safe_io import safe_json_write

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 required. Run: pip install beautifulsoup4")
    sys.exit(1)


# Page builder signatures
BUILDER_SIGNATURES = {
    'brizy': 'brz-',
    'elementor': 'elementor-',
    'divi': 'et_pb_',
    'wpbakery': 'vc_row',
    'squarespace': 'sqs-',
    'wix': 'wixui_',
    'webflow': 'w-',
    'wordpress': 'wp-block-',
}

# CTA keywords for button detection
CTA_KEYWORDS = [
    'get started', 'contact', 'book', 'schedule', 'call', 'free',
    'learn more', 'sign up', 'subscribe', 'buy', 'order', 'apply',
    'request', 'demo', 'trial', 'quote', 'consultation', 'start',
]


def parse_html(html_content):
    """Parse HTML and extract structural analysis."""
    soup = BeautifulSoup(html_content, 'html.parser')

    analysis = {
        'sections': 0,
        'headings': [],
        'cta_buttons': [],
        'images_count': 0,
        'images_with_alt': 0,
        'has_hero': False,
        'has_testimonials': False,
        'has_pricing': False,
        'has_footer': False,
        'has_contact_info': False,
        'has_social_links': False,
        'has_meta_description': False,
        'has_viewport_meta': False,
        'nav_items': [],
        'has_form': False,
        'link_count': 0,
        'uses_page_builder': False,
        'builder_name': '',
        'word_count': 0,
        'has_animations': False,
        'font_count': 0,
    }

    # Page builder detection
    html_str = str(soup)
    for builder, marker in BUILDER_SIGNATURES.items():
        if marker in html_str:
            analysis['uses_page_builder'] = True
            analysis['builder_name'] = builder
            break

    # Sections
    sections = soup.find_all('section')
    analysis['sections'] = len(sections)
    if not sections:
        # Count major divs as pseudo-sections
        main = soup.find('main')
        if main:
            analysis['sections'] = len(main.find_all('div', recursive=False))

    # Headings
    for tag in ['h1', 'h2', 'h3', 'h4']:
        for heading in soup.find_all(tag):
            text = heading.get_text(strip=True)[:100]
            if text:
                analysis['headings'].append({'tag': tag, 'text': text})

    # Hero detection
    hero_selectors = ['header', '.hero', '#hero', '[class*="hero"]', '[class*="banner"]']
    for sel in hero_selectors:
        if soup.select(sel):
            analysis['has_hero'] = True
            break

    # CTA buttons
    for btn in soup.find_all(['a', 'button']):
        text = btn.get_text(strip=True).lower()
        classes = ' '.join(btn.get('class', [])).lower()
        if any(kw in text for kw in CTA_KEYWORDS) or 'btn' in classes or 'cta' in classes:
            analysis['cta_buttons'].append(btn.get_text(strip=True)[:50])

    # Images
    images = soup.find_all('img')
    analysis['images_count'] = len(images)
    analysis['images_with_alt'] = sum(1 for img in images if img.get('alt', '').strip())

    # Testimonials
    testimonial_markers = ['testimonial', 'review', 'quote', 'client-say', 'feedback']
    for marker in testimonial_markers:
        if marker in html_str.lower():
            analysis['has_testimonials'] = True
            break

    # Pricing
    if 'pricing' in html_str.lower() or '$' in html_str:
        analysis['has_pricing'] = True

    # Footer
    analysis['has_footer'] = bool(soup.find('footer'))

    # Contact info
    contact_patterns = [
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',  # phone
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # email
    ]
    for pattern in contact_patterns:
        if re.search(pattern, html_str):
            analysis['has_contact_info'] = True
            break

    # Social links
    social_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com']
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').lower()
        if any(domain in href for domain in social_domains):
            analysis['has_social_links'] = True
            break

    # Meta tags
    if soup.find('meta', attrs={'name': 'description'}):
        analysis['has_meta_description'] = True
    if soup.find('meta', attrs={'name': 'viewport'}):
        analysis['has_viewport_meta'] = True

    # Navigation
    nav = soup.find('nav')
    if nav:
        for link in nav.find_all('a'):
            text = link.get_text(strip=True)
            if text and len(text) < 30:
                analysis['nav_items'].append(text)

    # Forms
    analysis['has_form'] = bool(soup.find('form'))

    # Links
    analysis['link_count'] = len(soup.find_all('a'))

    # Word count (body text only)
    body = soup.find('body')
    if body:
        text = body.get_text(separator=' ', strip=True)
        analysis['word_count'] = len(text.split())

    # Animations
    animation_markers = ['animation', 'transition', 'keyframes', 'animate', 'aos-', 'wow ']
    for marker in animation_markers:
        if marker in html_str.lower():
            analysis['has_animations'] = True
            break

    # Font count
    font_families = set()
    for match in re.findall(r"font-family\s*:\s*['\"]?([^;'\"}{]+)", html_str):
        first = match.split(',')[0].strip().strip("'\"").lower()
        if first not in ('inherit', 'sans-serif', 'serif', 'monospace', 'initial'):
            font_families.add(first)
    analysis['font_count'] = len(font_families)

    return analysis


def score_website(analysis, branding=None):
    """Score website across 10 design categories (0-10 each)."""
    scores = {}

    # 1. Visual Hierarchy
    h_tags = [h['tag'] for h in analysis['headings']]
    h_count = len(h_tags)
    h_variety = len(set(h_tags))
    score = min(h_count * 1.5, 8) + min(h_variety, 2)
    if 'h1' not in h_tags:
        score = max(score - 3, 0)
    scores['visual_hierarchy'] = round(min(score, 10), 1)

    # 2. Layout
    sections = analysis['sections']
    scores['layout'] = round(min(sections * 2.5, 10), 1)

    # 3. CTA
    cta_count = len(analysis['cta_buttons'])
    scores['cta'] = round(min(cta_count * 3, 10), 1)

    # 4. Typography
    fc = analysis['font_count']
    if fc == 0:
        scores['typography'] = 2
    elif fc == 1:
        scores['typography'] = 5
    elif fc == 2:
        scores['typography'] = 8
    elif fc == 3:
        scores['typography'] = 6
    else:
        scores['typography'] = 4  # too many fonts

    # 5. Color
    if branding and branding.get('all_colors'):
        unique_colors = len(branding['all_colors'])
        scores['color'] = round(min(unique_colors * 1.5, 10), 1)
    else:
        scores['color'] = 5  # can't assess without branding

    # 6. Social Proof
    scores['social_proof'] = 8 if analysis['has_testimonials'] else 2

    # 7. Content Quality
    wc = analysis['word_count']
    if wc >= 500:
        scores['content'] = 8
    elif wc >= 200:
        scores['content'] = 7
    elif wc >= 50:
        scores['content'] = 5
    else:
        scores['content'] = 3

    # 8. Modern Features
    mf = 3  # base
    if analysis['has_animations']:
        mf += 2
    if analysis['has_viewport_meta']:
        mf += 2
    if analysis['has_meta_description']:
        mf += 1
    if analysis['has_form']:
        mf += 1
    scores['modern_features'] = round(min(mf, 10), 1)

    # 9. Imagery
    img_count = analysis['images_count']
    if img_count >= 5:
        scores['imagery'] = 7
    elif img_count >= 2:
        scores['imagery'] = 5
    else:
        scores['imagery'] = 3

    # 10. Overall
    all_scores = [v for k, v in scores.items()]
    scores['overall'] = round(sum(all_scores) / len(all_scores), 1)

    return scores


def identify_gaps(analysis, scores):
    """Identify specific weaknesses to fix in the redesign."""
    gaps = []

    if not analysis['has_hero']:
        gaps.append("No hero section — needs a compelling above-the-fold visual")

    if scores['visual_hierarchy'] < 5:
        gaps.append("Weak visual hierarchy — missing H1 or insufficient heading structure")

    if len(analysis['cta_buttons']) < 2:
        gaps.append(f"Only {len(analysis['cta_buttons'])} CTA button(s) — needs primary CTA in hero + secondary CTAs throughout")

    if not analysis['has_testimonials']:
        gaps.append("No testimonials or social proof — missing trust signals")

    if analysis['uses_page_builder']:
        gaps.append(f"Built with {analysis['builder_name']} page builder — template-looking design")

    if not analysis['has_animations']:
        gaps.append("No animations or transitions — feels static and dated")

    if analysis['font_count'] < 2:
        gaps.append("Single font or no custom fonts — needs heading/body font pairing")

    if not analysis['has_contact_info']:
        gaps.append("No visible contact information — needs phone/email prominently displayed")

    if not analysis['has_social_links']:
        gaps.append("No social media links — missing credibility signals")

    if analysis['images_count'] < 3:
        gaps.append("Too few images — needs more visual content")

    if not analysis['has_viewport_meta']:
        gaps.append("No viewport meta tag — site may not be mobile-responsive")

    if analysis['sections'] < 3:
        gaps.append("Too few content sections — needs more depth (services, about, testimonials, CTA)")

    if not analysis['has_form']:
        gaps.append("No contact form — needs a lead capture mechanism")

    return gaps


def identify_strengths(analysis):
    """Identify things to preserve in the redesign."""
    strengths = []

    if analysis['has_hero']:
        strengths.append("Has hero section with call-to-action")

    if analysis['sections'] >= 4:
        strengths.append(f"Good page structure with {analysis['sections']} sections")

    if analysis['has_testimonials']:
        strengths.append("Testimonials/social proof present")

    if analysis['has_contact_info']:
        strengths.append("Contact information present")

    if analysis['has_social_links']:
        strengths.append("Social media links present")

    if analysis['has_form']:
        strengths.append("Lead capture form present")

    if analysis['word_count'] >= 200:
        strengths.append(f"Good content depth ({analysis['word_count']} words)")

    if analysis['images_count'] >= 5:
        strengths.append(f"Strong visual content ({analysis['images_count']} images)")

    if analysis['has_animations']:
        strengths.append("Has animations/transitions")

    return strengths


def analyze_website(html_path, branding_path=None):
    """Full analysis pipeline.

    Returns dict with description, scores, gaps, strengths, html_analysis.
    """
    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        html_content = f.read()

    branding = None
    if branding_path and os.path.exists(branding_path):
        with open(branding_path, 'r', encoding='utf-8') as f:
            branding = json.load(f)

    # Parse HTML structure
    analysis = parse_html(html_content)

    # Score
    scores = score_website(analysis, branding)

    # Gaps and strengths
    gaps = identify_gaps(analysis, scores)
    strengths = identify_strengths(analysis)

    # Build description
    slug = os.path.splitext(os.path.basename(html_path))[0]
    builder_note = f" Built with {analysis['builder_name']} page builder." if analysis['uses_page_builder'] else ""
    desc = (
        f"{slug} — {analysis['sections']} content sections, "
        f"{analysis['images_count']} images, {len(analysis['cta_buttons'])} CTA buttons.{builder_note} "
        f"Nav: {', '.join(analysis['nav_items'][:5]) or 'none detected'}. "
        f"{analysis['font_count']} font(s). {analysis['word_count']} words."
    )

    return {
        'description': desc,
        'scores': scores,
        'gaps': gaps,
        'strengths': strengths,
        'html_analysis': analysis,
        'branding': branding,
    }


def main():
    parser = argparse.ArgumentParser(description='Analyze a website\'s design quality')
    parser.add_argument('--html', required=True, help='Path to captured HTML file')
    parser.add_argument('--branding', help='Path to branding.json (from capture_site.py)')
    parser.add_argument('--output', help='Output JSON path (default: prints to stdout)')

    args = parser.parse_args()

    if not os.path.exists(args.html):
        print(f"ERROR: HTML file not found: {args.html}")
        sys.exit(1)

    print(f"Analyzing: {args.html}")
    result = analyze_website(args.html, args.branding)

    print(f"  Overall score: {result['scores']['overall']}/10")
    print(f"  Gaps: {len(result['gaps'])}")
    for gap in result['gaps']:
        print(f"    - {gap}")
    print(f"  Strengths: {len(result['strengths'])}")
    for s in result['strengths']:
        print(f"    + {s}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        safe_json_write(args.output, result)
        print(f"\nSaved: {args.output}")
    else:
        print(f"\n{json.dumps(result, indent=2, default=str)}")


if __name__ == '__main__':
    main()
