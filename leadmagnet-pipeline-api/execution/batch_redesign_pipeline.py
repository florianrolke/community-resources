#!/usr/bin/env python3
"""
Batch Redesign Pipeline Orchestrator.

Chains the fully automated stages of the Stitch redesign lead magnet flow:
  1. screenshot  - Capture prospect website screenshots (Firecrawl)
  2. redesign    - Generate AI redesigns (Stitch MCP)
  3. deploy      - Push to GitHub + Coolify for live preview URLs
  4. comparison  - Create before/after comparison images (Pillow)
  5. outreach    - Send personalized emails with comparisons + preview links
  6. all         - Run all stages in sequence

Pipeline flow:
  new → screenshot_taken → redesign_done → deployed → comparison_ready → email_sent

Usage:
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --stage screenshot
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --stage redesign
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --stage deploy
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --stage comparison
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --stage outreach --review
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --stage all --review
    python execution/batch_redesign_pipeline.py --sheet-url "SHEET_URL" --status
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Add execution directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


def slugify(text):
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60]


def get_sheet_data(sheet_url, worksheet_name=None):
    """Read all records from the Google Sheet and return (records, worksheet, headers)."""
    from capture_website_screenshot import get_google_credentials
    import gspread

    creds = get_google_credentials()
    client = gspread.authorize(creds)

    sheet_id = sheet_url.split('/d/')[1].split('/')[0] if '/d/' in sheet_url else sheet_url
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    records = worksheet.get_all_records()
    headers = worksheet.row_values(1)
    return records, worksheet, headers


def show_status(sheet_url, worksheet_name=None):
    """Show pipeline status - count leads at each stage."""
    records, _, _ = get_sheet_data(sheet_url, worksheet_name)

    status_counts = {}
    for r in records:
        status = str(r.get('status', 'unknown')).strip().lower()
        status_counts[status] = status_counts.get(status, 0) + 1

    # Define the pipeline stages in order
    stages = [
        'new',
        'screenshot_taken',
        'redesign_done',
        'deployed',
        'comparison_ready',
        'email_sent',
        'replied',
        'purchased',
    ]

    print(f"\nPipeline Status ({len(records)} total leads)")
    print("=" * 50)

    for stage in stages:
        count = status_counts.pop(stage, 0)
        if count > 0:
            bar = "#" * min(count, 40)
            print(f"  {stage:20s} | {count:4d} {bar}")

    # Any other statuses
    for stage, count in sorted(status_counts.items()):
        if count > 0 and stage not in ('', 'unknown'):
            bar = "#" * min(count, 40)
            print(f"  {stage:20s} | {count:4d} {bar}")

    # Action items
    screenshot_ready = sum(1 for r in records if str(r.get('status', '')).strip().lower() == 'new')
    redesign_ready = sum(1 for r in records if str(r.get('status', '')).strip().lower() == 'screenshot_taken')
    deploy_ready = sum(1 for r in records if str(r.get('status', '')).strip().lower() == 'redesign_done')
    comparison_ready = sum(1 for r in records if str(r.get('status', '')).strip().lower() == 'deployed')
    outreach_ready = sum(1 for r in records if str(r.get('status', '')).strip().lower() == 'comparison_ready')

    print(f"\nNext actions:")
    if screenshot_ready:
        print(f"  -> {screenshot_ready} leads ready for SCREENSHOT (run --stage screenshot)")
    if redesign_ready:
        print(f"  -> {redesign_ready} leads ready for REDESIGN (run --stage redesign)")
    if deploy_ready:
        print(f"  -> {deploy_ready} leads ready for DEPLOY (run --stage deploy)")
    if comparison_ready:
        print(f"  -> {comparison_ready} leads ready for COMPARISON IMAGE (run --stage comparison)")
    if outreach_ready:
        print(f"  -> {outreach_ready} leads ready for OUTREACH EMAIL (run --stage outreach)")
    if not any([screenshot_ready, redesign_ready, deploy_ready, comparison_ready, outreach_ready]):
        print(f"  -> No pending actions. Add more leads with status='new' to continue.")

    print()


def run_stage_screenshot(sheet_url, batch_size=25, worksheet_name=None):
    """Run the screenshot capture stage."""
    from capture_website_screenshot import process_batch_from_sheet
    print("\n" + "=" * 60)
    print("STAGE 1: Website Screenshot Capture (Firecrawl)")
    print("=" * 60)
    process_batch_from_sheet(sheet_url, batch_size, worksheet_name)


def run_stage_redesign(sheet_url, batch_size=10, worksheet_name=None):
    """Run the Stitch MCP redesign stage for leads with status=screenshot_taken."""
    from generate_redesign import generate_redesign
    print("\n" + "=" * 60)
    print("STAGE 2: AI Redesign (Stitch MCP)")
    print("=" * 60)

    records, worksheet, headers = get_sheet_data(sheet_url, worksheet_name)
    leads = [(i, r) for i, r in enumerate(records)
             if str(r.get('status', '')).strip().lower() == 'screenshot_taken']

    if not leads:
        print("No leads with status='screenshot_taken' found.")
        return

    leads = leads[:batch_size]
    print(f"Processing {len(leads)} leads for redesign")
    print("-" * 60)

    success = 0
    errors = 0

    for idx, (record_idx, lead) in enumerate(leads):
        company = lead.get('company', lead.get('Company', f'lead_{record_idx}'))
        slug = slugify(company)

        print(f"\n[{idx + 1}/{len(leads)}] {company} (slug: {slug})")

        try:
            result = generate_redesign(slug=slug)
            print(f"  Redesign generated in {result['elapsed_seconds']:.0f}s")
            success += 1

            # Update sheet
            sheet_row = record_idx + 2
            updates = [
                ("status", "redesign_done"),
                ("redesign_html", result['html_path']),
            ]
            if result.get('screenshot_path'):
                updates.append(("screenshot_after", os.path.basename(result['screenshot_path'])))

            for col_name, value in updates:
                if col_name in headers:
                    col_idx = headers.index(col_name) + 1
                    worksheet.update_cell(sheet_row, col_idx, str(value))

        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"REDESIGN COMPLETE: {success} success, {errors} errors out of {len(leads)} leads")


def run_stage_deploy(sheet_url, worksheet_name=None):
    """Run the deploy stage for leads with status=redesign_done."""
    from deploy_redesign import deploy_single_html
    print("\n" + "=" * 60)
    print("STAGE 3: Deploy to Live Preview (GitHub + Coolify)")
    print("=" * 60)

    records, worksheet, headers = get_sheet_data(sheet_url, worksheet_name)
    leads = [(i, r) for i, r in enumerate(records)
             if str(r.get('status', '')).strip().lower() == 'redesign_done']

    if not leads:
        print("No leads with status='redesign_done' found.")
        return

    print(f"Deploying {len(leads)} sites...")
    print("-" * 60)

    success = 0
    errors = 0

    for idx, (record_idx, lead) in enumerate(leads):
        company = lead.get('company', lead.get('Company', f'lead_{record_idx}'))
        slug = slugify(company)

        # Find redesign HTML
        html_path = lead.get('redesign_html', f'.tmp/redesigns/{slug}-redesign.html')
        if not os.path.exists(html_path):
            html_path = f'.tmp/redesigns/{slug}-redesign.html'

        if not os.path.exists(html_path):
            print(f"  [{idx+1}/{len(leads)}] SKIP {company} - no redesign HTML at {html_path}")
            errors += 1
            continue

        print(f"  [{idx+1}/{len(leads)}] Deploying {company}...")
        try:
            preview_url = deploy_single_html(slug, html_path)
            print(f"    LIVE: {preview_url}")
            success += 1

            # Update sheet
            sheet_row = record_idx + 2
            for col_name, value in [("status", "deployed"), ("preview_url", preview_url)]:
                if col_name in headers:
                    col_idx = headers.index(col_name) + 1
                    worksheet.update_cell(sheet_row, col_idx, str(value))

        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"DEPLOY COMPLETE: {success} success, {errors} errors out of {len(leads)} leads")


def run_stage_comparison(sheet_url, worksheet_name=None):
    """Run the comparison image creation stage for leads with status=deployed."""
    from create_comparison_image import create_comparison
    print("\n" + "=" * 60)
    print("STAGE 4: Before/After Comparison Images (Pillow)")
    print("=" * 60)

    records, worksheet, headers = get_sheet_data(sheet_url, worksheet_name)
    leads = [(i, r) for i, r in enumerate(records)
             if str(r.get('status', '')).strip().lower() == 'deployed']

    if not leads:
        print("No leads with status='deployed' found.")
        return

    print(f"Processing {len(leads)} leads for comparison images")
    print("-" * 60)

    os.makedirs('.tmp/comparisons', exist_ok=True)
    success = 0
    errors = 0

    for idx, (record_idx, lead) in enumerate(leads):
        company = lead.get('company', lead.get('Company', f'lead_{idx}'))
        slug = slugify(company)

        # Find before screenshot
        before_file = lead.get('screenshot_before', '')
        if before_file:
            before_path = os.path.join('.tmp/screenshots', before_file)
        else:
            before_path = f'.tmp/screenshots/{slug}_before.png'

        # Find after screenshot (Stitch redesign screenshot)
        after_file = lead.get('screenshot_after', '')
        if after_file:
            after_path = os.path.join('.tmp/screenshots', after_file) if not os.path.dirname(after_file) else after_file
        else:
            after_path = f'.tmp/redesigns/{slug}-redesign.png'

        output_path = f'.tmp/comparisons/{slug}_comparison.jpg'

        print(f"\n[{idx + 1}/{len(leads)}] {company}")
        print(f"  Before: {before_path} ({'OK' if os.path.exists(before_path) else 'MISSING'})")
        print(f"  After:  {after_path} ({'OK' if os.path.exists(after_path) else 'MISSING'})")

        if not os.path.exists(before_path):
            print(f"  SKIP: before screenshot not found")
            errors += 1
            continue

        if not os.path.exists(after_path):
            print(f"  SKIP: after screenshot not found")
            errors += 1
            continue

        result = create_comparison(
            before_path=before_path,
            after_path=after_path,
            output_path=output_path,
            company_name=company,
        )

        if result:
            success += 1
            # Update sheet
            sheet_row = record_idx + 2
            for col_name, value in [("status", "comparison_ready")]:
                if col_name in headers:
                    col_idx = headers.index(col_name) + 1
                    worksheet.update_cell(sheet_row, col_idx, value)
        else:
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"COMPARISON COMPLETE: {success} success, {errors} errors out of {len(leads)} leads")


def run_stage_outreach(sheet_url, worksheet_name=None, review_mode=True, offer_price="249"):
    """Run the outreach email stage."""
    from send_redesign_outreach import process_batch_from_sheet
    print("\n" + "=" * 60)
    print("STAGE 5: Outreach Emails (Gmail)")
    print("=" * 60)
    process_batch_from_sheet(sheet_url, worksheet_name, review_mode, offer_price)


def main():
    parser = argparse.ArgumentParser(description="Batch redesign pipeline orchestrator")
    parser.add_argument("--sheet-url", required=True, help="Google Sheet URL")
    parser.add_argument("--stage",
                        choices=["screenshot", "redesign", "deploy", "comparison", "outreach", "all", "status"],
                        default="status", help="Pipeline stage to run (default: status)")
    parser.add_argument("--worksheet", help="Worksheet name (default: first sheet)")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size for screenshot/redesign stage")
    parser.add_argument("--review", action="store_true", default=True, help="Review emails before sending")
    parser.add_argument("--auto", action="store_true", help="Auto-send without review")
    parser.add_argument("--price", default="249", help="Offer price (default: 249)")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")

    args = parser.parse_args()

    if args.status or args.stage == "status":
        show_status(args.sheet_url, args.worksheet)
        return 0

    review_mode = not args.auto

    if args.stage == "screenshot":
        run_stage_screenshot(args.sheet_url, args.batch_size, args.worksheet)

    elif args.stage == "redesign":
        run_stage_redesign(args.sheet_url, args.batch_size, args.worksheet)

    elif args.stage == "deploy":
        run_stage_deploy(args.sheet_url, args.worksheet)

    elif args.stage == "comparison":
        run_stage_comparison(args.sheet_url, args.worksheet)

    elif args.stage == "outreach":
        run_stage_outreach(args.sheet_url, args.worksheet, review_mode, args.price)

    elif args.stage == "all":
        print("\nRunning FULL AUTOMATED pipeline")
        print("new -> screenshot -> redesign -> deploy -> comparison -> outreach\n")

        # Stage 1: Screenshots
        run_stage_screenshot(args.sheet_url, args.batch_size, args.worksheet)

        # Stage 2: Redesign (Stitch MCP)
        run_stage_redesign(args.sheet_url, args.batch_size, args.worksheet)

        # Stage 3: Deploy to live preview
        run_stage_deploy(args.sheet_url, args.worksheet)

        # Stage 4: Comparison images
        run_stage_comparison(args.sheet_url, args.worksheet)

        # Stage 5: Outreach emails
        run_stage_outreach(args.sheet_url, args.worksheet, review_mode, args.price)

    # Final status
    show_status(args.sheet_url, args.worksheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
