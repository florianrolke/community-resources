#!/usr/bin/env python3
"""
Website Capture using Firecrawl API.

Captures screenshot, HTML, markdown, and branding data from prospect websites
in a single API call - no local browser needed.

Outputs:
  - .tmp/screenshots/{slug}_before.png  (viewport screenshot)
  - .tmp/screenshots/{slug}_before_full.png  (full-page screenshot)
  - .tmp/html/{slug}.html  (cleaned HTML)
  - .tmp/branding/{slug}.json  (brand colors, fonts, logo, UI components)

Usage:
    # Single URL
    python execution/capture_website_screenshot.py --url "https://example.com"

    # Batch from Google Sheet
    python execution/capture_website_screenshot.py --sheet-url "SHEET_URL" --batch-size 25

    # Batch from JSON file
    python execution/capture_website_screenshot.py --batch-file ".tmp/leads.json"
"""

import os
import sys
import json
import re
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Add execution directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Output directories
SCREENSHOT_DIR = ".tmp/screenshots"
HTML_DIR = ".tmp/html"
BRANDING_DIR = ".tmp/branding"

# ---------------------------------------------------------------------------
# Google Sheets helpers (adapted from read_sheet.py / update_sheet.py)
# ---------------------------------------------------------------------------

def get_google_credentials():
    """Get OAuth2 credentials for Google Sheets API."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = None

    if os.path.exists('token.json'):
        try:
            with open('token.json', 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data, scopes)
        except Exception as e:
            print(f"Error loading token: {e}", file=sys.stderr)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())

    return creds


def read_leads_from_sheet(sheet_url, worksheet_name=None, status_filter="new"):
    """Read leads from Google Sheet, optionally filtering by status."""
    import gspread

    creds = get_google_credentials()
    client = gspread.authorize(creds)

    sheet_id = sheet_url.split('/d/')[1].split('/')[0] if '/d/' in sheet_url else sheet_url
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    records = worksheet.get_all_records()
    if status_filter:
        records = [r for r in records if str(r.get('status', '')).strip().lower() == status_filter.lower()]

    print(f"Read {len(records)} leads with status='{status_filter}' from sheet")
    return records, worksheet


def update_lead_in_sheet(worksheet, row_index, updates: dict):
    """Update specific cells for a lead row in the sheet.

    Args:
        worksheet: gspread worksheet object
        row_index: 1-based row index (header = row 1, first data = row 2)
        updates: dict of {column_name: value}
    """
    headers = worksheet.row_values(1)
    for col_name, value in updates.items():
        if col_name in headers:
            col_idx = headers.index(col_name) + 1  # 1-based
            worksheet.update_cell(row_index, col_idx, str(value))


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60]


# ---------------------------------------------------------------------------
# Firecrawl capture
# ---------------------------------------------------------------------------

def capture_website(
    url: str,
    lead_id: str = None,
    screenshot_dir: str = SCREENSHOT_DIR,
    html_dir: str = HTML_DIR,
    branding_dir: str = BRANDING_DIR,
    full_page: bool = True,
    wait_ms: int = 3000,
) -> dict:
    """
    Capture screenshot, HTML, markdown, and branding from a website using Firecrawl.

    One API call gets everything - no local browser needed.

    Args:
        url: Website URL to capture
        lead_id: Identifier for file naming (defaults to slugified domain)
        screenshot_dir: Directory to save screenshots
        html_dir: Directory to save HTML files
        branding_dir: Directory to save branding JSON
        full_page: Whether to capture full-page screenshot (vs viewport only)
        wait_ms: Milliseconds to wait for JS rendering before capture

    Returns:
        dict with keys: screenshot_path, fullpage_path, html_path, branding_path,
                        branding_data, title, markdown, error
    """
    import requests
    from firecrawl import Firecrawl
    from firecrawl.v2.types import ScreenshotFormat

    # Ensure output directories exist
    for d in [screenshot_dir, html_dir, branding_dir]:
        os.makedirs(d, exist_ok=True)

    # Generate lead_id from domain if not provided
    if not lead_id:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        lead_id = slugify(parsed.netloc.replace('www.', ''))

    result = {
        "screenshot_path": None,
        "fullpage_path": None,
        "html_path": None,
        "branding_path": None,
        "branding_data": None,
        "title": None,
        "markdown": None,
        "error": None,
    }

    try:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            result["error"] = "FIRECRAWL_API_KEY not set in .env"
            return result

        firecrawl = Firecrawl(api_key=api_key)

        # Build format list - get everything in one call
        # Use ScreenshotFormat model for full-page screenshot option
        screenshot_fmt = ScreenshotFormat(type="screenshot", full_page=full_page)
        formats = ["html", "markdown", "branding", screenshot_fmt]

        # Single API call: screenshot + HTML + markdown + branding
        start_time = time.time()
        scrape_result = firecrawl.scrape(
            url=url,
            formats=formats,
            only_main_content=False,  # Full page for redesign context
            timeout=120000,
            wait_for=wait_ms,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        # --- Screenshot ---
        # scrape_result is a Pydantic Document model - use attribute access
        screenshot_url = scrape_result.screenshot
        if screenshot_url:
            # Download screenshot from Firecrawl CDN
            img_response = requests.get(screenshot_url, timeout=30)
            img_response.raise_for_status()

            if full_page:
                fullpage_path = os.path.join(screenshot_dir, f"{lead_id}_before_full.png")
                with open(fullpage_path, 'wb') as f:
                    f.write(img_response.content)
                result["fullpage_path"] = fullpage_path

                # Also create a viewport-cropped version (1440x900) for comparison images
                try:
                    from PIL import Image
                    from io import BytesIO
                    img = Image.open(BytesIO(img_response.content))
                    viewport_crop = img.crop((0, 0, min(img.width, 1440), min(img.height, 900)))
                    viewport_path = os.path.join(screenshot_dir, f"{lead_id}_before.png")
                    viewport_crop.save(viewport_path)
                    result["screenshot_path"] = viewport_path
                except Exception as crop_err:
                    # If crop fails, just use the full-page as the main screenshot
                    result["screenshot_path"] = fullpage_path
                    print(f"    Viewport crop warning: {crop_err}")
            else:
                viewport_path = os.path.join(screenshot_dir, f"{lead_id}_before.png")
                with open(viewport_path, 'wb') as f:
                    f.write(img_response.content)
                result["screenshot_path"] = viewport_path

        # --- HTML ---
        html_content = scrape_result.html
        if html_content:
            html_path = os.path.join(html_dir, f"{lead_id}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            result["html_path"] = html_path

        # --- Markdown ---
        result["markdown"] = scrape_result.markdown

        # --- Branding ---
        branding_obj = scrape_result.branding
        if branding_obj:
            # Convert Pydantic model to dict for JSON serialization
            branding_data = branding_obj.model_dump(exclude_none=True) if hasattr(branding_obj, 'model_dump') else dict(branding_obj)
            branding_path = os.path.join(branding_dir, f"{lead_id}.json")
            with open(branding_path, 'w', encoding='utf-8') as f:
                json.dump(branding_data, f, indent=2, ensure_ascii=False)
            result["branding_path"] = branding_path
            result["branding_data"] = branding_data

        # --- Metadata ---
        metadata = scrape_result.metadata_dict if hasattr(scrape_result, 'metadata_dict') else {}
        result["title"] = metadata.get("title", "")
        result["load_time_ms"] = elapsed_ms

    except Exception as e:
        result["error"] = f"Firecrawl error: {str(e)[:300]}"

    return result


def format_branding_summary(branding: dict) -> str:
    """Format branding data into a concise summary for Stitch prompts."""
    if not branding:
        return "No branding data available"

    parts = []

    # Colors
    colors = branding.get("colors", {})
    if colors:
        color_items = []
        for key in ["primary", "secondary", "accent", "background", "text"]:
            if key in colors:
                color_items.append(f"{key}: {colors[key]}")
        if color_items:
            parts.append(f"Colors: {', '.join(color_items)}")

    # Fonts
    fonts = branding.get("fonts", [])
    if fonts:
        font_names = [f.get("family", f.get("name", str(f))) if isinstance(f, dict) else str(f) for f in fonts[:3]]
        parts.append(f"Fonts: {', '.join(font_names)}")

    typography = branding.get("typography", {})
    font_families = typography.get("fontFamilies", {})
    if font_families:
        fam_items = []
        for key in ["primary", "heading", "code"]:
            if key in font_families:
                fam_items.append(f"{key}: {font_families[key]}")
        if fam_items:
            parts.append(f"Font families: {', '.join(fam_items)}")

    # Logo
    logo = branding.get("logo")
    if logo:
        parts.append(f"Logo: {logo}")

    # Personality
    personality = branding.get("personality", {})
    if personality:
        tone = personality.get("tone", "")
        audience = personality.get("targetAudience", "")
        if tone:
            parts.append(f"Tone: {tone}")
        if audience:
            parts.append(f"Audience: {audience}")

    return "\n".join(parts) if parts else "Minimal branding detected"


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def load_checkpoint(checkpoint_path: str) -> dict:
    """Load checkpoint file if it exists."""
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            return json.load(f)
    return {"processed": 0, "results": [], "errors": []}


def save_checkpoint(checkpoint_path: str, data: dict):
    """Save checkpoint data."""
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_batch_from_sheet(sheet_url, batch_size=25, worksheet_name=None):
    """Process leads from Google Sheet in batches with checkpoints."""
    leads, worksheet = read_leads_from_sheet(sheet_url, worksheet_name, status_filter="new")

    if not leads:
        print("No leads with status='new' found.")
        return

    checkpoint_path = ".tmp/checkpoints/screenshot_pipeline.json"
    checkpoint = load_checkpoint(checkpoint_path)
    start_idx = checkpoint["processed"]

    total = len(leads)
    print(f"\nProcessing {total} leads (starting from #{start_idx + 1})")
    print(f"Batch size: {batch_size}")
    print(f"Using Firecrawl API (screenshot + HTML + branding per call)")
    print("=" * 60)

    # We need row indices. get_all_records returns data rows; header is row 1.
    all_records = worksheet.get_all_records()
    status_col_values = [str(r.get('status', '')).strip().lower() for r in all_records]
    new_indices = [i for i, s in enumerate(status_col_values) if s == 'new']

    for batch_start in range(start_idx, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = leads[batch_start:batch_end]
        batch_num = (batch_start // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"\n[Batch {batch_num}/{total_batches}] Processing leads {batch_start + 1}-{batch_end}/{total}")

        for i, lead in enumerate(batch):
            idx = batch_start + i
            company = lead.get('company', lead.get('Company', f'lead_{idx}'))
            url = lead.get('website_url', lead.get('Website', lead.get('website', '')))

            if not url:
                print(f"  [{idx + 1}/{total}] SKIP {company} - no website URL")
                checkpoint["errors"].append({"company": company, "error": "no URL"})
                continue

            # Ensure URL has protocol
            if not url.startswith('http'):
                url = f"https://{url}"

            lead_slug = slugify(company) if company else slugify(url)
            print(f"  [{idx + 1}/{total}] {company} -> {url}")

            result = capture_website(url, lead_id=lead_slug)

            if result["error"]:
                print(f"    ERROR: {result['error']}")
                checkpoint["errors"].append({"company": company, "url": url, "error": result["error"]})
            else:
                title = result.get("title", "")
                elapsed = result.get("load_time_ms", 0)
                has_branding = "yes" if result.get("branding_data") else "no"
                print(f"    OK: {title} ({elapsed}ms) | branding: {has_branding}")

                # Print branding summary if available
                if result.get("branding_data"):
                    summary = format_branding_summary(result["branding_data"])
                    for line in summary.split('\n')[:3]:  # First 3 lines only
                        print(f"      {line}")

                checkpoint["results"].append({
                    "company": company,
                    "url": url,
                    "screenshot_path": result["screenshot_path"],
                    "fullpage_path": result.get("fullpage_path"),
                    "html_path": result.get("html_path"),
                    "branding_path": result.get("branding_path"),
                    "title": title,
                    "load_time_ms": elapsed,
                })

                # Update sheet
                if idx < len(new_indices):
                    sheet_row = new_indices[idx] + 2  # +2: header row + 0-based index
                    try:
                        update_data = {
                            "status": "screenshot_taken",
                            "screenshot_before": os.path.basename(result["screenshot_path"]) if result["screenshot_path"] else "",
                        }
                        update_lead_in_sheet(worksheet, sheet_row, update_data)
                    except Exception as e:
                        print(f"    Sheet update warning: {e}")

            # Small delay between Firecrawl calls (rate limiting courtesy)
            if i < len(batch) - 1:
                time.sleep(1)

        checkpoint["processed"] = batch_end
        save_checkpoint(checkpoint_path, checkpoint)
        print(f"  Checkpoint saved: {batch_end}/{total} processed")

    # Summary
    success = len(checkpoint["results"])
    errors = len(checkpoint["errors"])
    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {success} success, {errors} errors out of {total} leads")
    print(f"Screenshots: {SCREENSHOT_DIR}/")
    print(f"HTML files:  {HTML_DIR}/")
    print(f"Branding:    {BRANDING_DIR}/")

    # Clean up checkpoint on completion
    if checkpoint["processed"] >= total:
        os.remove(checkpoint_path)
        print("Checkpoint cleared (batch complete)")

    return checkpoint


def process_single(url, output=None, lead_id=None):
    """Process a single URL."""
    if not url.startswith('http'):
        url = f"https://{url}"

    if not lead_id:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        lead_id = slugify(parsed.netloc.replace('www.', ''))

    screenshot_dir = os.path.dirname(output) if output else SCREENSHOT_DIR
    if output:
        lead_id = Path(output).stem.replace('_before', '').replace('_before_full', '')

    result = capture_website(url, lead_id=lead_id, screenshot_dir=screenshot_dir)

    if result["error"]:
        print(f"ERROR: {result['error']}")
        return 1
    else:
        print(f"OK: {result['title']}")
        if result["screenshot_path"]:
            print(f"  Screenshot:  {result['screenshot_path']}")
        if result.get("fullpage_path"):
            print(f"  Full-page:   {result['fullpage_path']}")
        if result.get("html_path"):
            print(f"  HTML:        {result['html_path']}")
        if result.get("branding_path"):
            print(f"  Branding:    {result['branding_path']}")
        if result.get("load_time_ms"):
            print(f"  Capture time: {result['load_time_ms']}ms")

        # Print branding summary
        if result.get("branding_data"):
            print(f"\n  Brand Identity:")
            summary = format_branding_summary(result["branding_data"])
            for line in summary.split('\n'):
                print(f"    {line}")

        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Capture website data via Firecrawl for lead magnet pipeline")
    parser.add_argument("--url", help="Single website URL to capture")
    parser.add_argument("--output", "-o", help="Output path for single URL mode")
    parser.add_argument("--lead-id", help="Lead identifier for file naming")
    parser.add_argument("--sheet-url", help="Google Sheet URL for batch processing")
    parser.add_argument("--worksheet", help="Worksheet name (default: first sheet)")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size for processing (default: 25)")
    parser.add_argument("--batch-file", help="JSON file with leads to process")
    parser.add_argument("--no-fullpage", action="store_true", help="Skip full-page screenshot (viewport only)")

    args = parser.parse_args()

    if args.url:
        return process_single(args.url, args.output, args.lead_id)
    elif args.sheet_url:
        process_batch_from_sheet(args.sheet_url, args.batch_size, args.worksheet)
        return 0
    elif args.batch_file:
        with open(args.batch_file, 'r') as f:
            leads = json.load(f)
        for lead in leads:
            url = lead.get('website_url', lead.get('url', ''))
            company = lead.get('company', '')
            if url:
                lead_slug = slugify(company) if company else None
                result = capture_website(url, lead_id=lead_slug)
                status = "OK" if not result["error"] else f"ERROR: {result['error']}"
                print(f"  {company or url}: {status}")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
