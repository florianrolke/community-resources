#!/usr/bin/env python3
"""
Deep research on a prospect's business for landing page generation.

1. Firecrawl: scrape site for logo, branding, content
2. Perplexity: deep research on company, industry, pain points
3. Aggregate into a research brief for landing page generation

Usage:
    python landing-page-demo/research_client.py --url https://delta-vega.com --slug delta-vega
"""

import os
import sys
import json
import re
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"


def scrape_with_firecrawl(url):
    """Scrape site with Firecrawl for logo, branding, and content."""
    print(f"  Scraping {url} with Firecrawl...")

    from firecrawl import Firecrawl
    from firecrawl.v2.types import ScreenshotFormat

    api_key = os.getenv('FIRECRAWL_API_KEY')
    client = Firecrawl(api_key=api_key)

    result = client.scrape(
        url=url,
        formats=['html', 'markdown', 'branding', ScreenshotFormat(type='screenshot', full_page=True)],
        only_main_content=False,
        timeout=120000,
    )

    data = {
        'url': url,
        'html': getattr(result, 'html', ''),
        'markdown': getattr(result, 'markdown', ''),
        'screenshot_url': getattr(result, 'screenshot', ''),
    }

    # Extract branding
    branding = getattr(result, 'branding', None)
    if branding:
        brand_dict = branding.model_dump(exclude_none=True) if hasattr(branding, 'model_dump') else {}
        data['branding'] = brand_dict

        # Extract logo URL
        logo = brand_dict.get('logo', '')
        if logo:
            data['logo_url'] = logo
            print(f"  Logo found: {logo[:80]}...")

        # Extract colors
        colors = brand_dict.get('colors', {})
        if colors:
            data['colors'] = colors
            print(f"  Colors: {colors}")

    print(f"  Scraped: {len(data.get('markdown', ''))} chars markdown, {len(data.get('html', ''))} chars HTML")
    return data


def extract_key_info_from_markdown(markdown):
    """Extract company info from scraped markdown content."""
    info = {
        'headings': [],
        'services': [],
        'about_text': '',
        'contact_info': {},
        'ctas': [],
    }

    lines = markdown.split('\n')
    for line in lines:
        line = line.strip()
        # Headings
        if line.startswith('#'):
            heading = line.lstrip('#').strip()
            if heading and len(heading) > 2:
                info['headings'].append(heading)
        # Email
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', line)
        for email in emails:
            if not any(x in email for x in ['fill@', 'wght@', 'googleapis']):
                info['contact_info']['email'] = email
        # Phone
        phones = re.findall(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', line)
        if phones:
            info['contact_info']['phone'] = phones[0]

    # About text: first paragraph that's 50+ chars
    paragraphs = [p.strip() for p in markdown.split('\n\n') if len(p.strip()) > 50]
    if paragraphs:
        info['about_text'] = paragraphs[0][:500]

    return info


def research_with_perplexity(company_name, url, site_info):
    """Deep research on the company using Perplexity API."""
    print(f"  Researching {company_name} via Perplexity...")

    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        print("  Warning: No PERPLEXITY_API_KEY — skipping deep research")
        return None

    # Build a focused research query
    query = f"""Research the company "{company_name}" ({url}). I need:

1. What exactly does this company do? What are their core services/products?
2. Who is their target audience / ideal customer?
3. What industry are they in and what are the top 3 pain points for businesses in this space?
4. What would make a compelling landing page for this company? What should be highlighted?
5. What tone and style would resonate with their audience?

Be specific and factual. If you can't find information, say so."""

    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "sonar",
            "messages": [
                {"role": "user", "content": query}
            ],
            "max_tokens": 1500,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  Perplexity error: {resp.status_code} - {resp.text[:200]}")
        return None

    data = resp.json()
    research = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    print(f"  Research complete: {len(research)} chars")
    return research


def download_logo(logo_url, slug):
    """Download the logo image and save it locally."""
    if not logo_url:
        return None

    print(f"  Downloading logo...")
    try:
        resp = requests.get(logo_url, timeout=15)
        resp.raise_for_status()

        # Determine extension
        content_type = resp.headers.get('Content-Type', '')
        ext = '.png'
        if 'svg' in content_type:
            ext = '.svg'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'

        logo_dir = OUTPUT_DIR / slug
        logo_dir.mkdir(parents=True, exist_ok=True)
        logo_path = logo_dir / f"logo{ext}"
        with open(logo_path, 'wb') as f:
            f.write(resp.content)
        print(f"  Logo saved: {logo_path} ({len(resp.content)} bytes)")
        return str(logo_path), logo_url
    except Exception as e:
        print(f"  Logo download failed: {e}")
        return None, logo_url


def main():
    parser = argparse.ArgumentParser(description='Research a prospect for landing page generation')
    parser.add_argument('--url', required=True, help='Prospect website URL')
    parser.add_argument('--slug', required=True, help='Site identifier')
    args = parser.parse_args()

    print(f"\n=== Researching: {args.slug} ({args.url}) ===\n")

    # Step 1: Firecrawl scrape
    scrape_data = scrape_with_firecrawl(args.url)

    # Step 2: Extract key info
    markdown = scrape_data.get('markdown', '')
    site_info = extract_key_info_from_markdown(markdown)

    # Derive company name
    from urllib.parse import urlparse
    domain = urlparse(args.url).netloc.replace('www.', '')
    company_name = domain.split('.')[0].replace('-', ' ').title()

    # Step 3: Download logo
    logo_url = scrape_data.get('logo_url', '')
    logo_local, logo_remote = None, logo_url
    if logo_url:
        logo_local, logo_remote = download_logo(logo_url, args.slug)

    # Step 4: Perplexity deep research
    research = research_with_perplexity(company_name, args.url, site_info)

    # Step 5: Aggregate research brief
    brief = {
        'slug': args.slug,
        'url': args.url,
        'company_name': company_name,
        'logo_url': logo_remote,
        'logo_local': logo_local,
        'colors': scrape_data.get('colors', {}),
        'branding': scrape_data.get('branding', {}),
        'site_info': site_info,
        'markdown_preview': markdown[:2000],
        'perplexity_research': research,
        'screenshot_url': scrape_data.get('screenshot_url', ''),
    }

    # Save brief
    brief_dir = OUTPUT_DIR / args.slug
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief_path = brief_dir / "research-brief.json"
    with open(brief_path, 'w', encoding='utf-8') as f:
        json.dump(brief, f, indent=2, default=str)
    print(f"\n  Research brief saved: {brief_path}")

    # Summary
    print(f"\n=== Research Summary ===")
    print(f"  Company: {company_name}")
    print(f"  Logo: {'Found' if logo_url else 'Not found'}")
    print(f"  Colors: {scrape_data.get('colors', 'None')}")
    print(f"  Contact: {site_info.get('contact_info', {})}")
    print(f"  Perplexity: {'Done' if research else 'Skipped'}")
    print(f"\n  Next: python landing-page-demo/generate_landing_page.py --slug {args.slug}")


if __name__ == '__main__':
    main()
