#!/usr/bin/env python3
"""
Chamber Form Outreach — Submit personalized messages via chamber contact forms.

Uses Playwright in visible mode so the user can click reCAPTCHA checkboxes.
The automation fills the form; the human supervises and handles CAPTCHA.

Usage:
    # Single submission
    python -X utf8 outreach/chamber_form_outreach.py \
        --url "https://local.meadowlands.org/Business-Services/NJMC-Business-Accelerator-1609" \
        --name "Your Name" --email "you@example.com" \
        --message "Hi, I saw your listing in the Meadowlands Chamber..."

    # Batch from JSON
    python -X utf8 outreach/chamber_form_outreach.py --batch leads/weekly_chamber_outreach.json --limit 5

    # Dry run (fill but don't submit)
    python -X utf8 outreach/chamber_form_outreach.py --batch leads/weekly_chamber_outreach.json --dry-run
"""

import asyncio
import argparse
import json
import os

import sys
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
LOG_FILE = PROJECT_DIR / ".tmp" / "outreach_log.json"
SCREENSHOT_DIR = PROJECT_DIR / ".tmp" / "outreach_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / ".tmp").mkdir(parents=True, exist_ok=True)

# Default sender info (override with --name, --email)
DEFAULT_SENDER_NAME = os.environ.get("OUTREACH_NAME", "Your Name")
DEFAULT_SENDER_EMAIL = os.environ.get("OUTREACH_EMAIL", "you@example.com")


def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


async def solve_captcha_with_capsolver(page):
    """Use CapSolver API to solve reCAPTCHA v2 server-side. Returns True if solved."""
    import capsolver

    api_key = os.environ.get("CAPSOLVER_API_KEY") or os.environ.get("Capsolver_API_KEY")
    if not api_key:
        print("    [CAPSOLVER] No CAPSOLVER_API_KEY in .env")
        return False

    capsolver.api_key = api_key

    # Extract the reCAPTCHA site key from the page
    site_key = await page.evaluate(r"""() => {
        const el = document.querySelector('[data-sitekey]');
        if (el) return el.getAttribute('data-sitekey');
        const iframe = document.querySelector('iframe[src*="recaptcha"]');
        if (iframe) {
            const match = iframe.src.match(/[?&]k=([^&]+)/);
            if (match) return match[1];
        }
        return null;
    }""")

    if not site_key:
        print("    [CAPSOLVER] Could not find reCAPTCHA site key on page")
        return False

    page_url = page.url
    print(f"    [CAPSOLVER] Site key: {site_key[:20]}...")
    print(f"    [CAPSOLVER] Sending to CapSolver API...")

    try:
        # Run blocking capsolver.solve() in a thread so it doesn't kill the Playwright connection
        import concurrent.futures
        def _solve():
            return capsolver.solve({
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            })
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            solution = await loop.run_in_executor(pool, _solve)

        token = solution.get("gRecaptchaResponse", "")
        if not token:
            print("    [CAPSOLVER] No token in response")
            return False

        print(f"    [CAPSOLVER] Got token ({len(token)} chars) — injecting...")

        # Inject token into all g-recaptcha-response textareas on the page
        injected = await page.evaluate("""(token) => {
            let count = 0;
            const textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"], #g-recaptcha-response');
            textareas.forEach(ta => { ta.value = token; count++; });
            // Also set via ID pattern (ASP.NET pages use generated IDs)
            document.querySelectorAll('textarea[id*="recaptcha-response"]').forEach(ta => {
                ta.value = token; count++;
            });
            // Try triggering the callback if available
            try {
                if (typeof ___grecaptcha_cfg !== 'undefined') {
                    const clients = ___grecaptcha_cfg.clients;
                    for (const cid in clients) {
                        const c = clients[cid];
                        // Walk the client object tree to find callback
                        const walk = (obj, depth) => {
                            if (depth > 5 || !obj) return;
                            for (const k in obj) {
                                if (typeof obj[k] === 'function' && k === 'callback') {
                                    obj[k](token);
                                }
                                if (typeof obj[k] === 'object') walk(obj[k], depth + 1);
                            }
                        };
                        walk(c, 0);
                    }
                }
            } catch(e) {}
            return count;
        }""", token)

        print(f"    [CAPSOLVER] Token injected into {injected} field(s)")
        await page.wait_for_timeout(1000)
        return True

    except Exception as e:
        print(f"    [CAPSOLVER] Error: {str(e)[:200]}")
        return False


async def detect_form_type(page):
    """Detect what kind of contact form is on the page."""
    return await page.evaluate(r"""() => {
        const body = document.body.innerHTML.toLowerCase();
        const result = {
            has_contact_form: false,
            has_recaptcha: false,
            has_mailto: false,
            platform: 'unknown',
            form_fields: {},
        };

        // Check for reCAPTCHA
        if (document.querySelector('iframe[src*="recaptcha"]') ||
            document.querySelector('.g-recaptcha') ||
            document.querySelector('[data-sitekey]') ||
            body.includes('recaptcha')) {
            result.has_recaptcha = true;
        }

        // Check for mailto links
        const mailtoLinks = document.querySelectorAll('a[href^="mailto:"]');
        if (mailtoLinks.length > 0) {
            result.has_mailto = true;
            result.mailto_email = mailtoLinks[0].href.replace('mailto:', '').split('?')[0];
        }

        // Detect form fields
        const forms = document.querySelectorAll('form');
        const inputs = document.querySelectorAll('input[type="text"], input[type="email"], textarea');

        if (forms.length > 0 || inputs.length > 1) {
            result.has_contact_form = true;

            // Find name/email/subject/phone fields — only text-like inputs
            for (const el of document.querySelectorAll('input')) {
                // Skip non-fillable input types
                const inputType = (el.type || 'text').toLowerCase();
                if (['submit', 'button', 'hidden', 'checkbox', 'radio', 'file', 'image', 'reset'].includes(inputType)) continue;

                const n = (el.name || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const ph = (el.placeholder || '').toLowerCase();
                // Get label from nearby elements
                const label = el.closest('label')?.textContent?.toLowerCase() || '';
                const prevLabel = el.previousElementSibling?.textContent?.toLowerCase() || '';
                // Use only the LAST segment of the ID (after last _ or $) to avoid
                // ASP.NET parent control IDs like "EmailForm1" polluting detection
                const idSegment = id.split(/[_$]/).pop() || '';
                const nameSegment = n.split(/[_$]/).pop() || '';
                // Short context = field's own identifiers (not parent container IDs)
                const fieldContext = idSegment + ' ' + nameSegment + ' ' + ph + ' ' + label + ' ' + prevLabel;
                const isDisabled = el.disabled || el.readOnly;
                const sel = el.id ? '#' + el.id : `input[name="${el.name}"]`;

                if (fieldContext.includes('name') && !fieldContext.includes('email') && !fieldContext.includes('company')) {
                    result.form_fields.name = { selector: sel, disabled: isDisabled };
                }
                if (fieldContext.includes('email') || inputType === 'email') {
                    result.form_fields.email = { selector: sel, disabled: isDisabled };
                }
                if (fieldContext.includes('subject') || fieldContext.includes('subj')) {
                    result.form_fields.subject = { selector: sel, disabled: isDisabled };
                }
                if (fieldContext.includes('phone') || fieldContext.includes('tel')) {
                    result.form_fields.phone = { selector: sel, disabled: isDisabled };
                }
            }

            // Find message textarea (exclude reCAPTCHA hidden textareas)
            const textareas = document.querySelectorAll('textarea');
            for (const ta of textareas) {
                const taId = (ta.id || '').toLowerCase();
                const taName = (ta.name || '').toLowerCase();
                // Skip reCAPTCHA response textareas
                if (taId.includes('recaptcha') || taName.includes('recaptcha')) continue;
                // Skip hidden textareas
                if (ta.offsetHeight === 0 && ta.offsetWidth === 0) continue;
                result.form_fields.message = {
                    selector: ta.id ? '#' + ta.id : (ta.name ? `textarea[name="${ta.name}"]` : 'textarea:not([name*="recaptcha"])')
                };
                break;
            }

            // Find submit button
            const btns = document.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type])');
            for (const btn of btns) {
                const text = btn.textContent?.toLowerCase() || btn.value?.toLowerCase() || '';
                if (text.includes('send') || text.includes('submit') || text.includes('contact')) {
                    result.form_fields.submit = {
                        selector: btn.id ? '#' + btn.id : 'button[type="submit"], input[type="submit"]',
                        text: btn.textContent?.trim() || btn.value || 'Submit'
                    };
                    break;
                }
            }
            // Fallback: any submit-type button
            if (!result.form_fields.submit && btns.length > 0) {
                result.form_fields.submit = { selector: 'button[type="submit"], input[type="submit"]' };
            }
        }

        // Detect platform
        if (body.includes('chamberdata') || body.includes('cc-assist') || body.includes('cca.')) {
            result.platform = 'CCA/ChamberData';
        } else if (body.includes('growthzone') || body.includes('gz-')) {
            result.platform = 'GrowthZone';
        } else if (body.includes('chambermaster') || body.includes('micronetonline')) {
            result.platform = 'ChamberMaster';
        } else if (body.includes('locable') || body.includes('local.')) {
            result.platform = 'Locable';
        } else if (body.includes('atlas') || body.includes('wl-listing')) {
            result.platform = 'Atlas';
        } else if (body.includes('wordpress') || body.includes('wp-content') || body.includes('wpcf7')) {
            result.platform = 'WordPress';
        }

        return result;
    }""")


async def fill_and_submit_form(page, sender_name, sender_email, subject, message, dry_run=False):
    """Fill the contact form and optionally submit it."""
    form_info = await detect_form_type(page)

    print(f"    [DEBUG] Platform: {form_info.get('platform')} | reCAPTCHA: {form_info.get('has_recaptcha')}")
    print(f"    [DEBUG] Fields detected: {list(form_info.get('form_fields', {}).keys())}")
    for fname, fdata in form_info.get("form_fields", {}).items():
        print(f"    [DEBUG]   {fname}: selector={fdata.get('selector','?')}, disabled={fdata.get('disabled',False)}")

    if not form_info.get("has_contact_form"):
        if form_info.get("has_mailto"):
            return {
                "status": "skip_mailto",
                "mailto": form_info.get("mailto_email", ""),
                "note": "No form — has mailto link. Use email draft instead."
            }
        return {"status": "no_form", "note": "No contact form found on page"}

    fields = form_info.get("form_fields", {})
    filled = []

    # Helper to fill a field
    async def fill_field(field_name, value):
        field = fields.get(field_name)
        if not field:
            return
        selector = field["selector"]
        # Check if field has pre-filled content we should preserve (like auto-subject)
        if field.get("disabled"):
            existing_value = await page.evaluate(f"""() => {{
                const el = document.querySelector('{selector}');
                return el ? el.value : '';
            }}""")
            if existing_value and len(existing_value) > 3:
                print(f"    [INFO] {field_name} pre-filled: '{existing_value[:60]}' — keeping")
                filled.append(f"{field_name}(prefilled)")
                return
            # Enable the field via JS so we can fill it
            await page.evaluate(f"""() => {{
                const el = document.querySelector('{selector}');
                if (el) {{ el.disabled = false; el.readOnly = false; }}
            }}""")
        try:
            await page.fill(selector, value)
            filled.append(field_name)
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"    [WARN] Could not fill {field_name}: {e}")

    await fill_field("name", sender_name)
    await fill_field("email", sender_email)
    await fill_field("subject", subject)
    await fill_field("message", message)

    result = {
        "status": "filled",
        "fields_filled": filled,
        "has_recaptcha": form_info.get("has_recaptcha", False),
        "platform": form_info.get("platform", "unknown"),
    }

    # In dry run, skip captcha and submission
    if dry_run:
        result["status"] = "dry_run"
        result["note"] = "Form filled but NOT submitted (dry run mode)"
        return result

    # Handle reCAPTCHA — solve via CapSolver API (server-side, no clicking needed)
    if form_info.get("has_recaptcha"):
        print("    [CAPTCHA] reCAPTCHA detected — solving via CapSolver...")
        captcha_solved = await solve_captcha_with_capsolver(page)
        if not captcha_solved:
            result["status"] = "captcha_failed"
            result["note"] = "CapSolver could not solve reCAPTCHA"
            return result
        print("    [CAPTCHA] Solved!")

    if fields.get("submit"):
        try:
            await page.click(fields["submit"]["selector"])
            await page.wait_for_timeout(5000)
            result["status"] = "submitted"
        except Exception as e:
            result["status"] = "submit_error"
            result["note"] = str(e)[:200]
            return result
    else:
        # Try pressing Enter on the last field
        try:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(5000)
            result["status"] = "submitted_enter"
        except Exception:
            result["status"] = "no_submit_button"
            return result

    # Verify submission — look for confirmation message
    verification = await page.evaluate(r"""() => {
        const body = document.body.innerText.toLowerCase();
        const successPatterns = [
            'thank you', 'thanks for', 'message sent', 'submission received',
            'successfully submitted', 'we will get back', "we'll get back",
            'form submitted', 'request received', 'inquiry received',
            'been received', 'reach out soon', 'contact you soon',
            'message has been', 'form has been', 'successfully sent',
            'has been sent', 'email sent'
        ];
        for (const pat of successPatterns) {
            if (body.includes(pat)) {
                return { confirmed: true, type: 'success_text', match: pat };
            }
        }
        const errorPatterns = [
            'please fill', 'required field', 'invalid', 'is required',
            'oops', 'something went wrong', 'error', 'failed'
        ];
        for (const pat of errorPatterns) {
            if (body.includes(pat)) {
                return { confirmed: false, type: 'validation_error', match: pat };
            }
        }
        return { confirmed: null, type: 'unknown', match: 'no confirmation detected' };
    }""")

    print(f"    [VERIFY] {verification.get('type')}: \"{verification.get('match', '')}\"")

    if verification.get("confirmed") is True:
        result["status"] = "confirmed"
        result["confirmation"] = verification
    elif verification.get("confirmed") is False:
        result["status"] = "failed_validation"
        result["confirmation"] = verification

    return result


async def process_single(page, url, sender_name, sender_email, subject, message,
                         company_name="", dry_run=False):
    """Process a single contact form submission."""
    slug = company_name.replace(" ", "_")[:30] or "single"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n  {'='*50}")
    print(f"  Company: {company_name or 'N/A'}")
    print(f"  URL: {url[:80]}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  [ERROR] Failed to load page: {e}")
        return {"status": "load_error", "url": url, "error": str(e)[:200]}

    # Scroll to form area (look for form or textarea)
    await page.evaluate("""() => {
        const form = document.querySelector('form') || document.querySelector('textarea');
        if (form) { form.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        else { window.scrollTo(0, document.body.scrollHeight * 0.4); }
    }""")
    await page.wait_for_timeout(1500)

    # Screenshot before
    before_path = SCREENSHOT_DIR / f"{slug}_{timestamp}_before.png"
    await page.screenshot(path=str(before_path), full_page=False)

    # Fill and submit
    result = await fill_and_submit_form(page, sender_name, sender_email, subject, message, dry_run)

    # Screenshot after (may fail if browser closed)
    after_path = SCREENSHOT_DIR / f"{slug}_{timestamp}_after.png"
    try:
        await page.screenshot(path=str(after_path), full_page=False)
    except Exception:
        pass  # Browser may have closed or navigated

    result["url"] = url
    result["company_name"] = company_name
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    result["screenshot_before"] = str(before_path)
    result["screenshot_after"] = str(after_path)

    status_icon = {
        "submitted": "OK",
        "submitted_enter": "OK",
        "dry_run": "DRY",
        "skip_mailto": "MAIL",
        "no_form": "SKIP",
        "captcha_timeout": "WAIT",
        "load_error": "ERR",
        "submit_error": "ERR",
    }.get(result["status"], "???")

    print(f"  [{status_icon}] {result['status']} | Fields: {', '.join(result.get('fields_filled', []))}")
    if result.get("note"):
        print(f"        {result['note']}")

    return result


async def main():
    parser = argparse.ArgumentParser(description="Chamber contact form outreach via Playwright")
    parser.add_argument("--url", help="Single URL to submit to")
    parser.add_argument("--name", default=DEFAULT_SENDER_NAME, help="Sender name")
    parser.add_argument("--email", default=DEFAULT_SENDER_EMAIL, help="Sender email")
    parser.add_argument("--subject", default="", help="Email subject (auto-generated if empty)")
    parser.add_argument("--message", default="", help="Message body")
    parser.add_argument("--batch", help="Path to JSON file with batch of leads")
    parser.add_argument("--limit", type=int, default=5, help="Max submissions per run (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Fill forms but don't submit")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between submissions")
    args = parser.parse_args()

    if not args.url and not args.batch:
        parser.error("Either --url or --batch is required")

    from playwright.async_api import async_playwright

    # Load batch data if provided
    leads = []
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            leads = json.load(f)
        leads = leads[:args.limit]
        print(f"\n  Loaded {len(leads)} leads from {args.batch}")
    elif args.url:
        leads = [{"contact_form_url": args.url, "company_name": "", "message": args.message}]

    async with async_playwright() as p:
        # Use persistent context with anti-detection to pass reCAPTCHA
        user_data_dir = str(PROJECT_DIR / ".tmp" / "browser_profile")
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
        )
        # Remove webdriver flag so reCAPTCHA doesn't detect automation
        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        # persistent context doesn't use separate browser object

        log = load_log()
        results = []

        print(f"\n{'='*60}")
        print(f"  CHAMBER FORM OUTREACH")
        print(f"  Leads: {len(leads)} | Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
        print(f"  Sender: {args.name} <{args.email}>")
        print(f"{'='*60}")

        for i, lead in enumerate(leads):
            url = lead.get("contact_form_url") or lead.get("detail_url") or lead.get("url", "")
            company = lead.get("company_name", "")
            chamber = lead.get("chamber_name", "Chamber")
            msg = lead.get("message", args.message)

            if not msg:
                msg = (f"Hi, I came across your listing in the {chamber} directory. "
                       f"I help business owners like you grow through proven coaching "
                       f"and strategic advisory. Would you be open to a brief conversation "
                       f"about your business goals? I'd love to learn more about what you do.")

            subject = args.subject or f"Referral from {chamber} - {datetime.now().strftime('%m/%d/%Y')}"

            if not url:
                print(f"\n  [{i+1}/{len(leads)}] SKIP {company} — no URL")
                continue

            result = await process_single(
                page, url, args.name, args.email, subject, msg,
                company_name=company, dry_run=args.dry_run
            )
            results.append(result)
            log.append(result)

            # Save log after each submission
            save_log(log)

            # Delay between submissions
            if i < len(leads) - 1:
                print(f"    Waiting {args.delay}s before next submission...")
                await asyncio.sleep(args.delay)

        await context.close()

    # Summary
    submitted = sum(1 for r in results if r["status"] in ("submitted", "submitted_enter"))
    dry = sum(1 for r in results if r["status"] == "dry_run")
    skipped = sum(1 for r in results if r["status"] in ("no_form", "skip_mailto"))
    errors = sum(1 for r in results if "error" in r["status"])
    captcha = sum(1 for r in results if r["status"] == "captcha_timeout")

    print(f"\n{'='*60}")
    print(f"  OUTREACH COMPLETE")
    print(f"{'='*60}")
    print(f"  Submitted:      {submitted}")
    if dry: print(f"  Dry run:        {dry}")
    print(f"  Skipped:        {skipped}")
    print(f"  Errors:         {errors}")
    if captcha: print(f"  Captcha timeout: {captcha}")
    print(f"  Log saved to:   {LOG_FILE.name}")
    print(f"  Screenshots:    {SCREENSHOT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
