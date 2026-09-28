#!/usr/bin/env python3
"""Magazine Report Builder — HTML Output

Generates a polished HTML report with card layout for each advertiser.
Features:
- Stats banner (total leads, owners found, LinkedIn count, email count)
- Per-lead card: business name, industry, page number, ad type, website, phone
- Owner name + title, LinkedIn URL (clickable), email with verification badge
- Ad image thumbnail (base64 embedded)
- Meta description display
- Modern CSS styling with responsive layout
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import json
import base64
from pathlib import Path
from html import escape


def encode_image_base64(image_path: str) -> str:
    """Encode an image file as base64 data URI for HTML embedding."""
    try:
        path = Path(image_path)
        if not path.exists():
            return ""
        if path.stat().st_size > 2_000_000:  # Skip files > 2MB
            return ""
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        suffix = path.suffix.lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
        media_type = mime.get(suffix.lstrip("."), "image/png")
        return f"data:{media_type};base64,{data}"
    except Exception:
        return ""


def load_page_images(pages_dir: str) -> dict:
    """Load and crop page images as base64 for embedding in reports.

    Args:
        pages_dir: Path to directory containing page_NNN.png files

    Returns:
        Dict mapping page_num (int) -> base64-encoded PNG string
    """
    import io
    page_images = {}
    pages_path = Path(pages_dir)
    if not pages_path.exists():
        return page_images

    for page_path in sorted(pages_path.glob("page_*.png")):
        try:
            page_num = int(page_path.stem.split("_")[1])
            # Skip very large files (> 2MB) to keep report size manageable
            if page_path.stat().st_size > 2_000_000:
                continue
            data_uri = encode_image_base64(str(page_path))
            if data_uri:
                # Strip the data URI prefix to store just base64
                page_images[page_num] = data_uri
        except (ValueError, IndexError):
            continue

    return page_images


def build_html_report(advertisers: list, output_path: Path, edition_name: str,
                      month_name: str, year: int, flag_data: dict = None,
                      pages_dir: str = None):
    """Build an HTML report for enriched magazine advertisers.

    Args:
        advertisers: List of enriched advertiser dicts
        output_path: Where to save the HTML file
        edition_name: Human-readable edition name
        month_name: Month name (e.g., "march")
        year: Year
        flag_data: Optional dict with "status" key per business (NEW/SEEN)
        pages_dir: Optional path to page images directory for embedding page thumbnails
    """
    # Compute stats
    total = len(advertisers)
    owners = sum(1 for a in advertisers if a.get("owner_name"))
    linkedin = sum(1 for a in advertisers if a.get("linkedin_url"))
    emails = sum(1 for a in advertisers if a.get("email") or a.get("email_candidates"))
    websites = sum(1 for a in advertisers if a.get("website"))

    flag_data = flag_data or {}

    # Load page images for embedding if pages_dir provided
    page_images = load_page_images(pages_dir) if pages_dir else {}

    # Build cards HTML
    cards_html = []
    for ad in advertisers:
        name = escape(ad.get("business_name", "Unknown"))
        ad_type = escape(ad.get("ad_type", "unknown"))
        page_num = ad.get("page_num", "?")
        website = ad.get("website", "")
        phone = ad.get("phone", "")
        owner_name = ad.get("owner_name", "")
        owner_title = ad.get("owner_title", "")
        linkedin_url = ad.get("linkedin_url", "")
        email = ad.get("email", "")
        email_verified = ad.get("email_verified", False)
        email_candidates = ad.get("email_candidates", [])
        meta_desc = ad.get("meta_description", "")
        source_image = ad.get("source_image", "")

        # Flag badge
        flag_info = flag_data.get(name.lower(), {})
        flag_status = flag_info.get("status", "")
        flag_source = flag_info.get("first_seen", "")
        opacity = "0.45" if flag_status == "SEEN" else "1.0"

        badge_html = ""
        if flag_status == "NEW":
            badge_html = '<span class="badge badge-new">NEW</span>'
        elif flag_status == "SEEN":
            badge_html = f'<span class="badge badge-seen">ALREADY IN: {escape(flag_source)}</span>'

        # Image thumbnail — prefer source_image (ad crop), fall back to full page image
        img_html = ""
        if source_image:
            data_uri = encode_image_base64(source_image)
            if data_uri:
                img_html = f'<img src="{data_uri}" class="ad-thumb" alt="Ad from page {page_num}">'
        if not img_html and page_num != "?" and page_images.get(int(page_num) if str(page_num).isdigit() else 0):
            page_data_uri = page_images.get(int(page_num))
            if page_data_uri:
                img_html = f'<img src="{page_data_uri}" class="ad-thumb" alt="Page {page_num}">'

        # Contact details
        contact_parts = []
        if website:
            display_url = website.replace("https://", "").replace("http://", "").rstrip("/")
            contact_parts.append(f'<a href="{escape(website)}" target="_blank">{escape(display_url)}</a>')
        if phone:
            contact_parts.append(f'<span class="phone">{escape(phone)}</span>')

        # Owner section
        owner_html = ""
        if owner_name:
            owner_html = f'<div class="owner"><strong>{escape(owner_name)}</strong>'
            if owner_title:
                owner_html += f' <span class="title">- {escape(owner_title)}</span>'
            owner_html += '</div>'
        if linkedin_url:
            owner_html += f'<div class="linkedin"><a href="{escape(linkedin_url)}" target="_blank">LinkedIn Profile</a></div>'

        # Email section
        email_html = ""
        if email:
            verify_badge = ' <span class="verified">VERIFIED</span>' if email_verified else ''
            email_html = f'<div class="email">{escape(email)}{verify_badge}</div>'
        elif email_candidates:
            candidates_str = ", ".join(escape(e) for e in email_candidates[:3])
            email_html = f'<div class="email candidates">Candidates: {candidates_str}</div>'

        # Meta description
        meta_html = ""
        if meta_desc:
            meta_html = f'<div class="meta-desc">{escape(meta_desc)}</div>'

        card = f"""
        <div class="card" style="opacity: {opacity}">
            {badge_html}
            <div class="card-header">
                <h3>{name}</h3>
                <span class="ad-info">Page {page_num} | {ad_type.replace('_', ' ').title()}</span>
            </div>
            <div class="card-body">
                {img_html}
                <div class="details">
                    <div class="contact">{' | '.join(contact_parts)}</div>
                    {owner_html}
                    {email_html}
                    {meta_html}
                </div>
            </div>
        </div>"""
        cards_html.append(card)

    cards_joined = "\n".join(cards_html)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(edition_name)} - {month_name.title()} {year} | Magazine Leads</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
        .header {{ text-align: center; padding: 30px 20px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; border-radius: 12px; margin-bottom: 24px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .subtitle {{ font-size: 16px; opacity: 0.85; }}
        .stats {{ display: flex; justify-content: center; gap: 32px; flex-wrap: wrap; margin: 24px 0; }}
        .stat {{ text-align: center; }}
        .stat .number {{ font-size: 32px; font-weight: 700; color: #0f3460; }}
        .stat .label {{ font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }}
        .card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: box-shadow 0.2s; }}
        .card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.15); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }}
        .card-header h3 {{ font-size: 18px; color: #1a1a2e; }}
        .ad-info {{ font-size: 12px; color: #888; white-space: nowrap; padding-left: 12px; }}
        .card-body {{ display: flex; gap: 16px; }}
        .ad-thumb {{ width: 120px; height: 80px; object-fit: cover; border-radius: 6px; border: 1px solid #eee; flex-shrink: 0; }}
        .details {{ flex: 1; }}
        .contact {{ margin-bottom: 8px; font-size: 14px; }}
        .contact a {{ color: #0f3460; text-decoration: none; }}
        .contact a:hover {{ text-decoration: underline; }}
        .phone {{ color: #555; }}
        .owner {{ margin-bottom: 4px; font-size: 14px; }}
        .owner .title {{ color: #888; }}
        .linkedin a {{ color: #0077b5; font-size: 13px; text-decoration: none; }}
        .linkedin a:hover {{ text-decoration: underline; }}
        .email {{ font-size: 13px; color: #555; margin-top: 4px; }}
        .email.candidates {{ color: #888; font-style: italic; }}
        .verified {{ background: #22c55e; color: white; font-size: 10px; padding: 2px 6px; border-radius: 10px; font-weight: 600; }}
        .meta-desc {{ font-size: 12px; color: #888; margin-top: 8px; line-height: 1.4; border-top: 1px solid #f0f0f0; padding-top: 8px; }}
        .badge {{ display: inline-block; font-size: 11px; padding: 3px 10px; border-radius: 12px; font-weight: 700; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .badge-new {{ background: #dcfce7; color: #166534; }}
        .badge-seen {{ background: #f3f4f6; color: #6b7280; }}
        .footer {{ text-align: center; padding: 24px; color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{escape(edition_name)} Magazine Leads</h1>
        <div class="subtitle">{month_name.title()} {year} Issue</div>
    </div>

    <div class="stats">
        <div class="stat">
            <div class="number">{total}</div>
            <div class="label">Total Leads</div>
        </div>
        <div class="stat">
            <div class="number">{owners}</div>
            <div class="label">Owners Found</div>
        </div>
        <div class="stat">
            <div class="number">{linkedin}</div>
            <div class="label">LinkedIn</div>
        </div>
        <div class="stat">
            <div class="number">{emails}</div>
            <div class="label">Emails</div>
        </div>
        <div class="stat">
            <div class="number">{websites}</div>
            <div class="label">Websites</div>
        </div>
    </div>

    <div class="cards">
        {cards_joined}
    </div>

    <div class="footer">
        Generated by Magazine Advertiser Pipeline | {total} advertisers from {escape(edition_name)} {month_name.title()} {year}
    </div>
</body>
</html>"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report saved: {output_path} ({len(html) // 1024}KB)")
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build HTML report from enriched advertisers")
    parser.add_argument("--input", required=True, help="JSON file with enriched advertisers")
    parser.add_argument("--output", default="leads/magazine_report.html")
    parser.add_argument("--edition", default="Magazine")
    parser.add_argument("--month", default="unknown")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--pages-dir", help="Path to page images for embedding in report")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        advertisers = json.load(f)

    build_html_report(advertisers, Path(args.output), args.edition, args.month, args.year,
                      pages_dir=args.pages_dir)
    print(f"Done: {len(advertisers)} advertisers in report")
