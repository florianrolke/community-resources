#!/usr/bin/env python3
"""
Send Redesign Outreach Emails via Gmail API.

Sends personalized emails with embedded before/after comparison images
for the Stitch redesign lead magnet pipeline.

Usage:
    # Batch from Google Sheet (review mode - approves each email)
    python execution/send_redesign_outreach.py --sheet-url "SHEET_URL" --review

    # Single email test
    python execution/send_redesign_outreach.py --to "test@example.com" --name "John" --company "Acme" --image ".tmp/comparisons/acme_comparison.jpg"
"""

import os
import sys
import json
import argparse
import base64
import time
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# ---------------------------------------------------------------------------
# Email template
# ---------------------------------------------------------------------------

EMAIL_SUBJECT_TEMPLATE = "I redesigned {company}'s website - thought you'd want to see"

EMAIL_HTML_TEMPLATE = """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 620px; margin: 0 auto; color: #333; line-height: 1.6;">
    <p>Hi {first_name},</p>

    <p>I came across {company}'s website and thought I'd show you what a modern refresh could look like.</p>

    <div style="margin: 24px 0; text-align: center;">
        <img src="cid:comparison" alt="Before and After comparison of {company}'s website" style="max-width: 100%; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />
    </div>

    <p>No obligation - I just enjoy this kind of work. If you like what you see, I can make it live for <strong>{price}</strong>. Takes about 48 hours.</p>

    {live_preview_section}

    <p>Either way, hope this gives you some ideas.</p>

    <p>Best,<br/>
    Will</p>
</div>
"""

LIVE_PREVIEW_SECTION = """
    <p><a href="{url}" style="color: #2563eb; text-decoration: none; font-weight: 500;">See the interactive preview here &rarr;</a></p>
"""

# ---------------------------------------------------------------------------
# Gmail API helpers (adapted from welcome_client_emails.py)
# ---------------------------------------------------------------------------

def get_gmail_service():
    """Get authenticated Gmail API service."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_path = Path("token.json")
    if not token_path.exists():
        print("ERROR: token.json not found. Run read_sheet.py first to authenticate.", file=sys.stderr)
        sys.exit(1)

    with open(token_path) as f:
        token_data = json.load(f)

    scopes = token_data.get("scopes", [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ])

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=scopes,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token
        with open(token_path, 'w') as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_outreach_email(
    to_email: str,
    first_name: str,
    company_name: str,
    comparison_image_path: str,
    offer_price: str = "249",
    currency_symbol: str = "\u00a3",
    live_preview_url: str = None,
    from_name: str = "Will Coates",
    gmail_service=None,
) -> dict:
    """
    Send a personalized outreach email with embedded comparison image.

    Returns:
        dict with status, message_id, error
    """
    if not gmail_service:
        gmail_service = get_gmail_service()

    # Build email
    msg = MIMEMultipart('related')
    msg['Subject'] = EMAIL_SUBJECT_TEMPLATE.format(company=company_name)
    msg['To'] = to_email
    msg['From'] = from_name

    # Format price
    price_str = f"{currency_symbol}{offer_price}"

    # Live preview section
    live_section = ""
    if live_preview_url:
        live_section = LIVE_PREVIEW_SECTION.format(url=live_preview_url)

    # HTML body
    html = EMAIL_HTML_TEMPLATE.format(
        first_name=first_name,
        company=company_name,
        price=price_str,
        live_preview_section=live_section,
    )

    html_part = MIMEText(html, 'html')
    msg.attach(html_part)

    # Attach comparison image inline
    if comparison_image_path and os.path.exists(comparison_image_path):
        with open(comparison_image_path, 'rb') as img_file:
            img_data = img_file.read()

        ext = Path(comparison_image_path).suffix.lower()
        subtype = 'jpeg' if ext in ('.jpg', '.jpeg') else 'png'
        img_attachment = MIMEImage(img_data, _subtype=subtype)
        img_attachment.add_header('Content-ID', '<comparison>')
        img_attachment.add_header('Content-Disposition', 'inline', filename=f'redesign-comparison.{subtype}')
        msg.attach(img_attachment)
    else:
        print(f"  WARNING: Comparison image not found: {comparison_image_path}", file=sys.stderr)

    # Send
    try:
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = gmail_service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()

        return {
            "status": "sent",
            "message_id": result.get("id"),
            "to": to_email,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "message_id": None,
            "to": to_email,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

def get_google_credentials():
    """Get OAuth2 credentials for Google Sheets API."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/gmail.send',
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


def process_batch_from_sheet(sheet_url, worksheet_name=None, review_mode=True, offer_price="249"):
    """Process leads with status='comparison_ready' from Google Sheet."""
    import gspread

    creds = get_google_credentials()
    client = gspread.authorize(creds)

    sheet_id = sheet_url.split('/d/')[1].split('/')[0] if '/d/' in sheet_url else sheet_url
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    all_records = worksheet.get_all_records()
    headers = worksheet.row_values(1)

    # Filter for comparison_ready
    leads = [(i, r) for i, r in enumerate(all_records)
             if str(r.get('status', '')).strip().lower() == 'comparison_ready']

    if not leads:
        print("No leads with status='comparison_ready' found.")
        return

    gmail_service = get_gmail_service()

    print(f"Processing {len(leads)} leads for outreach")
    if review_mode:
        print("REVIEW MODE: You will approve each email before sending")
    print("=" * 60)

    sent = 0
    skipped = 0
    errors = 0

    for idx, (record_idx, lead) in enumerate(leads):
        company = lead.get('company', lead.get('Company', ''))
        contact_name = lead.get('contact_name', lead.get('Contact Name', ''))
        contact_email = lead.get('contact_email', lead.get('Contact Email', lead.get('email', '')))
        first_name = contact_name.split()[0] if contact_name else 'there'
        live_url = lead.get('preview_url', '') or lead.get('redesign_live_url', '')

        # Find comparison image
        import re
        slug = re.sub(r'[^\w\s-]', '', company.lower().strip())
        slug = re.sub(r'[\s_]+', '-', slug)[:60]
        comparison_path = f".tmp/comparisons/{slug}_comparison.jpg"

        if not os.path.exists(comparison_path):
            # Try PNG
            comparison_path = f".tmp/comparisons/{slug}_comparison.png"

        print(f"\n[{idx + 1}/{len(leads)}] {company}")
        print(f"  To: {first_name} <{contact_email}>")
        print(f"  Subject: {EMAIL_SUBJECT_TEMPLATE.format(company=company)}")
        print(f"  Image: {comparison_path} ({'EXISTS' if os.path.exists(comparison_path) else 'MISSING'})")
        if live_url:
            print(f"  Preview: {live_url}")

        if not contact_email:
            print("  SKIP: No email address")
            skipped += 1
            continue

        if not os.path.exists(comparison_path):
            print("  SKIP: Comparison image not found")
            skipped += 1
            continue

        # Review mode
        if review_mode:
            while True:
                choice = input("  Send this email? [y/n/s(kip)]: ").strip().lower()
                if choice in ('y', 'yes'):
                    break
                elif choice in ('n', 'no', 's', 'skip'):
                    print("  SKIPPED by user")
                    skipped += 1
                    break
            else:
                continue
            if choice not in ('y', 'yes'):
                continue

        # Send
        result = send_outreach_email(
            to_email=contact_email,
            first_name=first_name,
            company_name=company,
            comparison_image_path=comparison_path,
            offer_price=offer_price,
            live_preview_url=live_url if live_url else None,
            gmail_service=gmail_service,
        )

        if result["status"] == "sent":
            print(f"  SENT: Message ID {result['message_id']}")
            sent += 1

            # Update sheet
            sheet_row = record_idx + 2
            try:
                for col_name, value in [
                    ("status", "email_sent"),
                    ("email_sent_at", datetime.now().isoformat()),
                    ("offer_price", offer_price),
                ]:
                    if col_name in headers:
                        col_idx = headers.index(col_name) + 1
                        worksheet.update_cell(sheet_row, col_idx, value)
            except Exception as e:
                print(f"  Sheet update warning: {e}")

            # Anti-spam delay
            delay = 20
            print(f"  Waiting {delay}s before next email...")
            time.sleep(delay)
        else:
            print(f"  ERROR: {result['error']}")
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {sent} sent, {skipped} skipped, {errors} errors out of {len(leads)} leads")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Send redesign outreach emails")
    parser.add_argument("--to", help="Single recipient email")
    parser.add_argument("--name", help="Recipient first name")
    parser.add_argument("--company", help="Company name")
    parser.add_argument("--image", help="Path to comparison image")
    parser.add_argument("--price", default="249", help="Offer price (default: 249)")
    parser.add_argument("--preview-url", help="Live preview URL")
    parser.add_argument("--sheet-url", help="Google Sheet URL for batch processing")
    parser.add_argument("--worksheet", help="Worksheet name (default: first sheet)")
    parser.add_argument("--review", action="store_true", default=True, help="Review each email before sending (default)")
    parser.add_argument("--auto", action="store_true", help="Auto-send without review (use with caution)")

    args = parser.parse_args()

    if args.to:
        # Single email mode
        result = send_outreach_email(
            to_email=args.to,
            first_name=args.name or "there",
            company_name=args.company or "your company",
            comparison_image_path=args.image or "",
            offer_price=args.price,
            live_preview_url=args.preview_url,
        )
        if result["status"] == "sent":
            print(f"Email sent! Message ID: {result['message_id']}")
            return 0
        else:
            print(f"Failed: {result['error']}")
            return 1
    elif args.sheet_url:
        review = not args.auto
        process_batch_from_sheet(args.sheet_url, args.worksheet, review_mode=review, offer_price=args.price)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
