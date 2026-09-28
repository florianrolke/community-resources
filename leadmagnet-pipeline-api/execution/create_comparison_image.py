#!/usr/bin/env python3
"""
Before/After Comparison Image Creator using Pillow.

Creates side-by-side comparison images from before/after website screenshots
for the Stitch redesign lead magnet pipeline.

Usage:
    # Single comparison
    python execution/create_comparison_image.py --before "before.png" --after "after.png" --output "comparison.jpg"

    # Batch from Google Sheet
    python execution/create_comparison_image.py --sheet-url "SHEET_URL"
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Layout settings
VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 900
IMAGE_WIDTH = 700       # Each side of the comparison
IMAGE_HEIGHT = 500      # Height of each screenshot panel
DIVIDER_WIDTH = 4       # Width of center divider line
PADDING = 30            # Outer padding
LABEL_HEIGHT = 40       # Height of BEFORE/AFTER label area
FOOTER_HEIGHT = 60      # Height of branding footer
LABEL_FONT_SIZE = 22
FOOTER_FONT_SIZE = 16
CTA_FONT_SIZE = 14

# Colors
BG_COLOR = (245, 245, 245)          # Light gray background
DIVIDER_COLOR = (200, 200, 200)     # Gray divider
BEFORE_LABEL_COLOR = (180, 60, 60)  # Muted red for BEFORE
AFTER_LABEL_COLOR = (60, 140, 80)   # Green for AFTER
TEXT_COLOR = (50, 50, 50)           # Dark text
FOOTER_BG = (35, 35, 45)           # Dark footer
FOOTER_TEXT = (220, 220, 220)       # Light footer text
WATERMARK_COLOR = (255, 255, 255, 80)  # Semi-transparent white


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font, falling back to default if system fonts aren't available."""
    font_names = [
        "segoeui.ttf", "segoeuib.ttf",  # Windows
        "Arial.ttf", "ArialBold.ttf",   # Windows alt
        "Helvetica.ttc",                 # Mac
        "DejaVuSans.ttf",               # Linux
    ]
    if bold:
        font_names = [
            "segoeuib.ttf", "ArialBold.ttf",
            "Helvetica-Bold.ttf", "DejaVuSans-Bold.ttf",
        ] + font_names

    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue

    # Fallback to default
    return ImageFont.load_default()


def create_comparison(
    before_path: str,
    after_path: str,
    output_path: str,
    company_name: str = "",
    branding_name: str = "Will Coates",
    cta_text: str = "Want this for your website? Reply to find out more.",
) -> str:
    """
    Create a side-by-side before/after comparison image.

    Args:
        before_path: Path to the before screenshot
        after_path: Path to the after screenshot
        output_path: Path to save the comparison image
        company_name: Company name for personalization
        branding_name: Name to show in footer
        cta_text: Call-to-action text in footer

    Returns:
        Output path on success, None on failure
    """
    # Load images
    try:
        before_img = Image.open(before_path).convert('RGB')
    except Exception as e:
        print(f"Error loading before image: {e}", file=sys.stderr)
        return None

    try:
        after_img = Image.open(after_path).convert('RGB')
    except Exception as e:
        print(f"Error loading after image: {e}", file=sys.stderr)
        return None

    # Resize both to consistent dimensions
    before_img = before_img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)
    after_img = after_img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)

    # Calculate canvas dimensions
    canvas_width = PADDING + IMAGE_WIDTH + DIVIDER_WIDTH + IMAGE_WIDTH + PADDING
    canvas_height = PADDING + LABEL_HEIGHT + IMAGE_HEIGHT + PADDING + FOOTER_HEIGHT

    # Create canvas
    canvas = Image.new('RGB', (canvas_width, canvas_height), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # Fonts
    label_font = get_font(LABEL_FONT_SIZE, bold=True)
    footer_font = get_font(FOOTER_FONT_SIZE, bold=True)
    cta_font = get_font(CTA_FONT_SIZE)

    # --- Draw BEFORE label ---
    before_label_x = PADDING + IMAGE_WIDTH // 2
    before_label_y = PADDING + LABEL_HEIGHT // 2
    draw.text(
        (before_label_x, before_label_y),
        "BEFORE",
        fill=BEFORE_LABEL_COLOR,
        font=label_font,
        anchor="mm"
    )

    # --- Draw AFTER label ---
    after_label_x = PADDING + IMAGE_WIDTH + DIVIDER_WIDTH + IMAGE_WIDTH // 2
    after_label_y = PADDING + LABEL_HEIGHT // 2
    draw.text(
        (after_label_x, after_label_y),
        "AFTER",
        fill=AFTER_LABEL_COLOR,
        font=label_font,
        anchor="mm"
    )

    # --- Paste screenshots ---
    img_y = PADDING + LABEL_HEIGHT

    # Before image (left side)
    canvas.paste(before_img, (PADDING, img_y))

    # After image (right side)
    canvas.paste(after_img, (PADDING + IMAGE_WIDTH + DIVIDER_WIDTH, img_y))

    # --- Draw divider ---
    divider_x = PADDING + IMAGE_WIDTH
    draw.rectangle(
        [divider_x, img_y, divider_x + DIVIDER_WIDTH, img_y + IMAGE_HEIGHT],
        fill=DIVIDER_COLOR
    )

    # --- Add subtle border around screenshots ---
    border_color = (180, 180, 180)
    # Before border
    draw.rectangle(
        [PADDING - 1, img_y - 1, PADDING + IMAGE_WIDTH, img_y + IMAGE_HEIGHT],
        outline=border_color, width=1
    )
    # After border
    draw.rectangle(
        [PADDING + IMAGE_WIDTH + DIVIDER_WIDTH - 1, img_y - 1,
         PADDING + IMAGE_WIDTH + DIVIDER_WIDTH + IMAGE_WIDTH, img_y + IMAGE_HEIGHT],
        outline=border_color, width=1
    )

    # --- Draw footer ---
    footer_y = PADDING + LABEL_HEIGHT + IMAGE_HEIGHT + PADDING
    draw.rectangle(
        [0, footer_y, canvas_width, canvas_height],
        fill=FOOTER_BG
    )

    # Footer text: branding name on left, CTA on right
    footer_text_y = footer_y + FOOTER_HEIGHT // 2
    draw.text(
        (PADDING, footer_text_y),
        branding_name,
        fill=FOOTER_TEXT,
        font=footer_font,
        anchor="lm"
    )
    draw.text(
        (canvas_width - PADDING, footer_text_y),
        cta_text,
        fill=FOOTER_TEXT,
        font=cta_font,
        anchor="rm"
    )

    # --- Add watermark on AFTER image ---
    # Create a subtle "PREVIEW" watermark diagonally
    watermark = Image.new('RGBA', (IMAGE_WIDTH, IMAGE_HEIGHT), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(watermark)
    wm_font = get_font(48, bold=True)
    wm_draw.text(
        (IMAGE_WIDTH // 2, IMAGE_HEIGHT // 2),
        "PREVIEW",
        fill=WATERMARK_COLOR,
        font=wm_font,
        anchor="mm"
    )

    # Paste watermark on after image area
    after_area_x = PADDING + IMAGE_WIDTH + DIVIDER_WIDTH
    canvas_rgba = canvas.convert('RGBA')
    canvas_rgba.paste(watermark, (after_area_x, img_y), watermark)
    canvas = canvas_rgba.convert('RGB')

    # --- Save ---
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
        canvas.save(output_path, 'JPEG', quality=90, optimize=True)
    else:
        canvas.save(output_path, 'PNG', optimize=True)

    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"  Comparison saved: {output_path} ({file_size_kb:.0f}KB)")
    return output_path


# ---------------------------------------------------------------------------
# Google Sheets helpers (same pattern as capture_website_screenshot.py)
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


def process_batch_from_sheet(sheet_url, worksheet_name=None):
    """Process leads with status='redesign_done' from Google Sheet."""
    import gspread

    creds = get_google_credentials()
    client = gspread.authorize(creds)

    sheet_id = sheet_url.split('/d/')[1].split('/')[0] if '/d/' in sheet_url else sheet_url
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    all_records = worksheet.get_all_records()
    headers = worksheet.row_values(1)

    # Filter for redesign_done
    leads = [(i, r) for i, r in enumerate(all_records)
             if str(r.get('status', '')).strip().lower() == 'redesign_done']

    if not leads:
        print("No leads with status='redesign_done' found.")
        return

    print(f"Processing {len(leads)} leads for comparison images")
    print("=" * 60)

    success = 0
    errors = 0

    for idx, (record_idx, lead) in enumerate(leads):
        company = lead.get('company', lead.get('Company', f'lead_{idx}'))
        before_file = lead.get('screenshot_before', '')
        after_file = lead.get('screenshot_after', '')

        before_path = os.path.join('.tmp/screenshots', before_file) if before_file else ''
        after_path = os.path.join('.tmp/screenshots', after_file) if after_file else ''

        print(f"\n[{idx + 1}/{len(leads)}] {company}")

        if not before_path or not os.path.exists(before_path):
            print(f"  SKIP: before screenshot not found ({before_file})")
            errors += 1
            continue

        if not after_path or not os.path.exists(after_path):
            print(f"  SKIP: after screenshot not found ({after_file})")
            errors += 1
            continue

        # Create slug for output
        import re
        slug = re.sub(r'[^\w\s-]', '', company.lower().strip())
        slug = re.sub(r'[\s_]+', '-', slug)[:60]

        output_path = f".tmp/comparisons/{slug}_comparison.jpg"

        result = create_comparison(
            before_path=before_path,
            after_path=after_path,
            output_path=output_path,
            company_name=company,
        )

        if result:
            success += 1
            # Update sheet
            sheet_row = record_idx + 2  # header row + 0-based
            try:
                for col_name, value in [("status", "comparison_ready")]:
                    if col_name in headers:
                        col_idx = headers.index(col_name) + 1
                        worksheet.update_cell(sheet_row, col_idx, value)
            except Exception as e:
                print(f"  Sheet update warning: {e}")
        else:
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {success} success, {errors} errors out of {len(leads)} leads")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Create before/after comparison images")
    parser.add_argument("--before", help="Path to before screenshot")
    parser.add_argument("--after", help="Path to after screenshot")
    parser.add_argument("--output", "-o", help="Output path for comparison image")
    parser.add_argument("--company", help="Company name for personalization")
    parser.add_argument("--sheet-url", help="Google Sheet URL for batch processing")
    parser.add_argument("--worksheet", help="Worksheet name (default: first sheet)")

    args = parser.parse_args()

    if args.before and args.after:
        output = args.output or ".tmp/comparisons/comparison.jpg"
        result = create_comparison(
            before_path=args.before,
            after_path=args.after,
            output_path=output,
            company_name=args.company or "",
        )
        return 0 if result else 1
    elif args.sheet_url:
        process_batch_from_sheet(args.sheet_url, args.worksheet)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
