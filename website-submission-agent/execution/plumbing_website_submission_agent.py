#!/usr/bin/env python3
"""
Plumbing/HVAC Website Submission Agent - submit partnership messages through
prospect websites directly.

Instead of cold email, navigate to the prospect's own website, find the contact
page, fill the form, solve any CAPTCHA via CapSolver, and submit. The prospect
sees it as an inbound inquiry — not spam.

Usage:
    # Single website
    python -X utf8 website-submission-agent/execution/plumbing_website_submission_agent.py \
        --url "https://www.comfortsquadair.com/" \
        --target-company "Comfort Squad Heating & Cooling" \
        --location "Sugar Land, TX" \
        --niche "HVAC contractor" \
        --dry-run

    # Dry run (detect form but don't submit)
    python -X utf8 website-submission-agent/execution/plumbing_website_submission_agent.py \
        --batch website-submission-agent/data/sample-plumbing-companies.csv --dry-run

    # Batch from CSV or JSON
    python -X utf8 website-submission-agent/execution/plumbing_website_submission_agent.py \
        --batch website-submission-agent/data/sample-plumbing-companies.csv --limit 5
"""

import asyncio
import argparse
import base64
import csv
import json
import os
import re
import sys
import concurrent.futures
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(PROJECT_DIR / ".env", override=False)
load_dotenv(PROJECT_DIR.parent / ".env", override=False)
LOG_FILE = PROJECT_DIR / ".tmp" / "plumbing_website_submission_log.json"
SCREENSHOT_DIR = PROJECT_DIR / ".tmp" / "plumbing_website_submission_screenshots"
REVIEW_SCREENSHOT_DIR = PROJECT_DIR / "review-screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / ".tmp").mkdir(parents=True, exist_ok=True)

# Contact page URL patterns to try
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact-us/", "/contact/",
    "/get-in-touch", "/reach-us", "/inquiry", "/request-service",
    "/schedule-service", "/book-online", "/quote", "/free-estimate",
    "/estimate", "/request-a-quote", "/service-request",
    "/about/contact", "/about-us/contact",
    "/#contact", "/contactus",
]

DEFAULT_SENDER_NAME = os.environ.get("WEBSITE_SUBMISSION_SENDER_NAME", "")
DEFAULT_SENDER_EMAIL = os.environ.get("WEBSITE_SUBMISSION_SENDER_EMAIL", "")
DEFAULT_SENDER_PHONE = os.environ.get("WEBSITE_SUBMISSION_SENDER_PHONE", "")
DEFAULT_PROPERTY_ADDRESS = "1455 Clearview Drive"
DEFAULT_PROPERTY_POSTAL_CODE = "75072"

SERVICE_POSITIVE_TERMS = (
    "plumber", "plumbing", "drain", "sewer", "water heater", "leak",
    "pipe", "piping", "hvac", "air conditioning", "heating", "mechanical", "rooter",
)
SERVICE_NEGATIVE_TERMS = (
    "supply store", "supplier", "wholesale", "distributor", "parts",
    "showroom", "manufacturer", "factory", "outlet", "union", "local ",
    "school", "training", "association", "retail", "store",
)


def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def normalize_website(url):
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def domain_key(url):
    try:
        return urlparse(normalize_website(url)).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def score_service_lead(lead):
    """Score whether a row is likely an actual plumbing/HVAC service company."""
    name = lead_value(lead, "company_name", "company", "name").lower()
    category = lead_value(lead, "categoryName", "category_name", "categories", "niche").lower()
    website = lead_value(lead, "website", "url").lower()
    text = f"{name} {category} {website}"

    score = 0
    reasons = []
    for term in SERVICE_POSITIVE_TERMS:
        if term in text:
            score += 15
            reasons.append(f"+{term}")
    for term in SERVICE_NEGATIVE_TERMS:
        if term in text:
            score -= 20
            reasons.append(f"-{term.strip()}")

    if any(term in name for term in ("plumbing", "plumber", "rooter", "drain", "hvac")):
        score += 20
        reasons.append("+service_name")
    if "supply" in name or "supply" in category:
        score -= 35
        reasons.append("-supply")
    if "facebook.com" in website or "google.com" in website:
        score -= 25
        reasons.append("-directory/social")
    if not website:
        score -= 100
        reasons.append("-no_website")

    return score, reasons[:8]


def lead_value(lead, *keys, default=""):
    for key in keys:
        value = lead.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def split_location(location):
    parts = [part.strip() for part in (location or "").split(",") if part.strip()]
    city = parts[0] if parts else ""
    state = parts[1] if len(parts) > 1 else ""
    return city, state


def lead_first_name(lead):
    for key in ("owner_first_name", "first_name", "contact_first_name"):
        value = lead_value(lead, key)
        if value:
            return value.split()[0].strip(",")

    for key in ("owner_name", "contact_name", "person_name"):
        value = lead_value(lead, key)
        if value:
            return value.split()[0].strip(",")

    company = lead_value(lead, "company_name", "company", "name")
    if company:
        person_match = re.search(r"\b([A-Z][a-z]{2,})\s+[A-Z][a-z]{2,}\b", company)
        if person_match:
            return person_match.group(1)
    return ""


def generate_exact_case_study_message(lead):
    first_name = lead_first_name(lead)
    greeting = f"Hello {first_name}," if first_name else "Hello,"
    return (
        f"{greeting}\n\n"
        "We just finished a case study about a client in Michigan, a pre-owned manufactured home dealer and reseller. \n\n"
        "So I wanted to greet you. \n\n"
        "They had a record February with us and the best March since 2014 - I can send you their case study if you’d like.\n\n"
        "Blessings,  \n"
        "Florian"
    )


def generate_exact_charley_hayden_message(lead):
    company = lead_value(lead, "company_name", "company", "name", default="[Company Name]")
    return (
        f"Hello {company},\n\n"
        "We’re a mitigation company serving Greater Houston and are looking to partner with a few more plumbing companies that want to create additional revenue streams from the service calls they’re already running.\n\n"
        "For the past several years, we’ve quietly worked alongside some of Houston’s leading plumbing companies, providing mitigation services when water damage is identified during a service call. These partnerships help plumbers create additional revenue streams while ensuring their customers receive immediate, professional support.\n\n"
        "We’re now looking to expand our partnership network and connect with a few more plumbing companies throughout Greater Houston.\n\n"
        "Would you be available for a 10-minute call next week to see if there’s a good fit?"
    )


def generate_charley_round2_message(lead):
    company = lead_value(lead, "company_name", "company", "name", default="[Company Name]")
    return (
        f"Hello {company},\n\n"
        "We’re a local mitigation company based right here in Greater Houston, and we’re looking to partner with a few more plumbing companies that want to create additional revenue streams from the service calls they’re already running.\n\n"
        "For the past several years, we’ve quietly worked alongside some of Houston’s leading plumbing companies, providing mitigation services when water damage is identified during a service call. These partnerships help plumbers create additional revenue streams while ensuring their customers receive immediate, professional support.\n\n"
        "We’re now looking to expand our partnership network and connect with a few more plumbing companies throughout Greater Houston.\n\n"
        "Since we’re local, I’d love to swing by with a coffee and introduce myself in person — no pressure, just five minutes to see if there’s a good fit. Or if it’s easier, would you be available for a quick 10-minute call next week?"
    )


def infer_niche(lead):
    text = " ".join([
        lead_value(lead, "niche", "categoryName"),
        lead_value(lead, "categories"),
        lead_value(lead, "notes"),
    ]).lower()
    if "plumb" in text or "drain" in text or "water heater" in text:
        return "plumbing"
    if "hvac" in text or "air conditioning" in text or "heating" in text:
        return "HVAC"
    return lead_value(lead, "niche", "categoryName", "categories", default="home services")


def generate_partnership_message(lead):
    company = lead_value(lead, "company_name", "company", "name", default="your team")
    city = lead_value(lead, "city")
    state = lead_value(lead, "state")
    location = lead_value(lead, "location", default=", ".join(x for x in [city, state] if x))
    niche = infer_niche(lead)
    notes = lead_value(lead, "notes", default="")

    local_phrase = f" in {location}" if location else ""
    service_phrase = "plumbing/HVAC" if "home services" in niche.lower() else niche
    angle = "water damage referrals"
    if "hvac" in niche.lower() and "plumb" not in niche.lower():
        angle = "water-damage referrals from AC leaks, drain line backups, and related service calls"

    note_sentence = f" I noticed {notes.rstrip('.')}." if notes else ""

    return (
        f"Hi {company} team, I came across {company} while looking at local {service_phrase} companies"
        f"{local_phrase}.{note_sentence} We help mitigation and restoration partners build referral relationships "
        f"with local service companies so {angle} do not get missed when they show up during normal service calls. "
        "A lot of the larger companies already have partnerships like this in place because it can increase revenue "
        "per service call without adding more ad spend. If it is relevant, would you be open to a quick conversation "
        "this week to see whether a simple mitigation partnership could make sense locally?"
    )


def generic_required_text_value(label, message):
    label_lower = (label or "").lower()
    if any(word in label_lower for word in ("service", "request", "needed")):
        return "Mitigation partnership inquiry"
    if any(word in label_lower for word in ("system", "unit", "description", "details", "issue")):
        return "Business partnership inquiry regarding water damage mitigation referral relationships."
    if any(word in label_lower for word in ("question", "comment", "message")):
        return message
    return "Business partnership inquiry"


def normalize_lead(raw):
    company = lead_value(raw, "company_name", "company", "name")
    city = lead_value(raw, "city")
    state = lead_value(raw, "state")
    location = lead_value(raw, "location", default=", ".join(x for x in [city, state] if x))
    lead = dict(raw)
    lead["company_name"] = company
    lead["website"] = normalize_website(lead_value(raw, "website", "url"))
    lead["location"] = location
    lead["niche"] = lead_value(raw, "niche", "categoryName", "categories")
    lead["message"] = lead_value(raw, "message", default=generate_partnership_message(lead))
    return lead


def load_leads(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return [normalize_lead(row) for row in csv.DictReader(f)]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [normalize_lead(row) for row in data]


def validate_sender_config(name, email):
    missing = []
    if not name.strip():
        missing.append("--name or WEBSITE_SUBMISSION_SENDER_NAME")
    if not email.strip():
        missing.append("--email or WEBSITE_SUBMISSION_SENDER_EMAIL")
    if missing:
        raise SystemExit(
            "Missing required sender config: "
            + ", ".join(missing)
            + ". Set values in website-submission-agent/.env or pass CLI flags."
        )


async def set_field_value(page, selector, value):
    """Use the browser-native value setter first; fallback to Playwright fill."""
    return await page.evaluate(r"""(args) => {
        const [selector, val] = args;
        const el = document.querySelector(selector);
        if (!el) return false;
        let value = String(val);
        if (el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'number') {
            value = value.replace(/\\D/g, '');
        }
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.focus();
        const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        try {
            if (setter) setter.call(el, value);
            else el.value = value;
        } catch (e) {
            el.value = value;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        return String(el.value) === value;
    }""", [selector, value])


async def type_field_value(page, selector, value):
    """Fallback for masked fields that ignore direct JS value assignment."""
    locator = page.locator(selector).first
    await locator.scroll_into_view_if_needed(timeout=5000)
    await locator.click(timeout=5000)
    await locator.press("Control+A")
    await locator.type(str(value), delay=20)
    return await page.evaluate(r"""(args) => {
        const [selector, expected] = args;
        const el = document.querySelector(selector);
        if (!el) return false;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        const actual = String(el.value || '').replace(/\D/g, '');
        const wanted = String(expected || '').replace(/\D/g, '');
        return String(el.value || '').trim().length > 0 && (!wanted || actual.endsWith(wanted.slice(-7)));
    }""", [selector, value])


async def fill_common_form_fallbacks(page, name, email, phone, address, city, state, postal_code):
    """Fill duplicate/hidden Gravity fields that validation can require after submit."""
    return await page.evaluate(r"""(args) => {
        const [fullName, email, phone, address, city, state, postalCode] = args;
        const [firstName, ...lastParts] = fullName.split(/\\s+/);
        const lastName = lastParts.join(' ') || '';
        const phoneDigits = String(phone || '').replace(/\\D/g, '');
        const values = { fullName, firstName, lastName, email, phone, phoneDigits, address, city, state, postalCode };
        let count = 0;

        function setValue(el, val) {
            if (!el || val == null || val === '') return false;
            const elName = (el.name || '').toLowerCase();
            const elId = (el.id || '').toLowerCase();
            if (elName.includes('ak_hp')) return false;
            if (elId.includes('honeypot') || elName.includes('honeypot')) return false;
            if (/^(state_\d+|gform_|is_submit_|version_hash|ak_js|_wp|nonce)/.test(elName)) return false;
            if (/^(state_\d+|gform_|is_submit_|version_hash|ak_js|_wp|nonce)/.test(elId)) return false;
            const formText = (el.form?.innerText || '').toLowerCase();
            if (formText.includes('password') && formText.includes('login')) return false;

            if (el.tagName === 'SELECT') {
                const option = Array.from(el.options).find(o =>
                    o.value.toLowerCase() === String(val).toLowerCase() ||
                    o.textContent.trim().toLowerCase() === String(val).toLowerCase()
                );
                if (option) el.value = option.value;
                else return false;
            } else {
                if ((el.type || '').toLowerCase() === 'number') {
                    val = String(val).replace(/\\D/g, '');
                }
                const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                if (setter) setter.call(el, val);
                else el.value = val;
            }
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
            count++;
            return true;
        }

        for (const el of document.querySelectorAll('input, select')) {
            const type = (el.type || '').toLowerCase();
            const rawName = (el.name || '').toLowerCase();
            const rawId = (el.id || '').toLowerCase();
            if (/^(state_\d+|gform_|is_submit_|version_hash|ak_js|_wp|nonce)/.test(rawName)) continue;
            if (/^(state_\d+|gform_|is_submit_|version_hash|ak_js|_wp|nonce)/.test(rawId)) continue;
            const isVisible = el.offsetHeight > 0 || el.offsetWidth > 0;
            const label = (el.closest('label')?.innerText ||
                (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.innerText) || '');
            const ctx = `${type} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${label} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
            if (ctx.includes('username') || ctx.includes('password')) continue;
            const gravityPart = (
                rawName.match(/(?:^|_)input_\d+\.([1-6])$/)?.[1] ||
                rawId.match(/_\d+_4_([1-6])$/)?.[1] ||
                rawName.match(/\.([1-6])$/)?.[1]
            );
            if (gravityPart) {
                if (gravityPart === '1') setValue(el, values.address);
                else if (gravityPart === '3') setValue(el, values.city);
                else if (gravityPart === '4') setValue(el, values.state);
                else if (gravityPart === '5') setValue(el, values.postalCode);
                else if (gravityPart === '6') setValue(el, 'United States');
                continue;
            }
            if (!isVisible && el.form) {
                const formInputs = Array.from(el.form.querySelectorAll('input, textarea, select'));
                const hasVisibleEmail = formInputs.some(x => (x.offsetHeight > 0 || x.offsetWidth > 0) &&
                    (((x.type || '').toLowerCase() === 'email') || `${x.name || ''} ${x.id || ''}`.toLowerCase().includes('email')));
                const hasVisiblePhone = formInputs.some(x => (x.offsetHeight > 0 || x.offsetWidth > 0) &&
                    (((x.type || '').toLowerCase() === 'tel') || `${x.name || ''} ${x.id || ''} ${x.placeholder || ''}`.toLowerCase().match(/phone|tel/)));
                if (hasVisibleEmail && (type === 'email' || ctx.includes('email'))) continue;
                if (hasVisiblePhone && (type === 'tel' || ctx.includes('phone') || ctx.includes('telephone'))) continue;
            }

            if (type === 'radio') {
                const choice = `${el.value || ''} ${label}`.toLowerCase();
                if (!el.checked && (choice.includes('private') || choice.includes('lot'))) {
                    el.checked = true;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    count++;
                }
                continue;
            }
            if (type === 'checkbox') {
                const choice = `${el.value || ''} ${label}`.toLowerCase();
                if (!el.checked && (choice.includes('consent') || choice.includes('sms') || choice.includes('message'))) {
                    el.checked = true;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    count++;
                }
                continue;
            }

            if (type === 'email' || ctx.includes('email') || /input_\\d+$/.test(el.name || '') && label.toLowerCase().includes('email')) {
                setValue(el, values.email);
            } else if (type === 'tel' || ctx.includes('phone') || ctx.includes('telephone')) {
                setValue(el, type === 'number' ? values.phoneDigits : values.phone);
            } else if (ctx.includes('first')) {
                setValue(el, values.firstName);
            } else if (ctx.includes('last')) {
                setValue(el, values.lastName);
            } else if (ctx.includes('city') || /\\.3$/.test(el.name || '')) {
                setValue(el, values.city);
            } else if (ctx.includes('zip') || ctx.includes('postal') || /\\.5$/.test(el.name || '')) {
                setValue(el, values.postalCode);
            } else if (ctx.includes('state') || /\\.4$/.test(el.name || '')) {
                setValue(el, values.state);
            } else if (ctx.includes('address') || ctx.includes('street') || ctx.includes('autocomplete') || /\\.1$/.test(el.name || '')) {
                setValue(el, values.address);
            }
        }

        return count;
    }""", [name, email, phone, address, city, state, postal_code])


async def fill_address_with_autocomplete(page, selector, address):
    """Type into address autocomplete fields so site JS can populate hidden fields."""
    try:
        locator = page.locator(selector).first
        await locator.scroll_into_view_if_needed(timeout=5000)
        await locator.click(timeout=5000)
        await page.keyboard.press("Control+A")
        await page.keyboard.type(address, delay=20)
        await page.wait_for_timeout(1800)
        for key in ("ArrowDown", "Enter", "Tab"):
            try:
                await page.keyboard.press(key)
                await page.wait_for_timeout(350)
            except Exception:
                pass
        await page.evaluate("""(selector) => {
            const el = document.querySelector(selector);
            if (!el) return;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        }""", selector)
        await page.wait_for_timeout(800)
        return True
    except Exception:
        return False


async def goto_with_fallbacks(page, url, timeout=30000):
    """Navigate with http/https fallback for stale GBP websites and bad redirects."""
    candidates = []
    normalized = normalize_website(url)
    candidates.append(normalized)
    parsed = urlparse(normalized)
    if parsed.scheme == "https":
        candidates.append(parsed._replace(scheme="http").geturl())
    elif parsed.scheme == "http":
        candidates.append(parsed._replace(scheme="https").geturl())

    last_error = None
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            await page.goto(candidate, wait_until="domcontentloaded", timeout=timeout)
            await page.wait_for_timeout(2000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            return candidate
        except Exception as e:
            last_error = e
            msg = str(e)
            if not any(token in msg for token in [
                "ERR_CERT", "ERR_SSL", "ERR_NAME_NOT_RESOLVED",
                "ERR_ABORTED", "ERR_FAILED", "ERR_CONNECTION"
            ]):
                break
    if last_error:
        raise last_error
    raise RuntimeError(f"Could not navigate to {url}")


async def click_visible_submit(page, preferred_selector=None):
    """Click a genuinely visible submit/send control, including styled anchors."""
    return await page.evaluate("""(preferredSelector) => {
        function visible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                rect.width > 8 &&
                rect.height > 8 &&
                rect.bottom >= 0 &&
                rect.right >= 0;
        }
        function clickEl(el) {
            el.scrollIntoView({ behavior: 'instant', block: 'center' });
            el.click();
            return true;
        }
        if (preferredSelector) {
            const preferred = Array.from(document.querySelectorAll(preferredSelector)).filter(visible);
            if (preferred.length) return clickEl(preferred[preferred.length - 1]);
        }

        const candidates = Array.from(document.querySelectorAll(
            'button, input[type="submit"], a, [role="button"], .wsite-button, .wsite-button-inner'
        ));
        const patterns = /(submit|send|contact us|get my|cash offer|fair cash|question|comment|next|continue)/i;
        for (const el of candidates) {
            const text = `${el.textContent || ''} ${el.value || ''} ${el.getAttribute('aria-label') || ''}`.trim();
            if (visible(el) && patterns.test(text)) {
                const clickable = el.closest('a, button, [role="button"]') || el;
                return clickEl(clickable);
            }
        }
        return false;
    }""", preferred_selector)


async def fill_followup_step_and_submit(page, name, email, phone, address, city, state, postal_code):
    """Complete common Gravity/Carrot step-2 seller-detail forms after first-step acceptance."""
    filled = await page.evaluate(r"""(args) => {
        const [fullName, email, phone, address, city, state, postalCode] = args;
        const [firstName, ...lastParts] = fullName.split(/\s+/);
        const lastName = lastParts.join(' ') || '';
        let count = 0;

        function visible(el) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
                rect.width > 1 && rect.height > 1;
        }
        function labelFor(el) {
            const explicit = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
            const label = el.closest('label') || explicit;
            const container = el.closest('.gfield, .form-field, fieldset, li, p, div');
            return `${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${label?.innerText || ''} ${container?.innerText || ''}`.toLowerCase();
        }
        function setValue(el, val) {
            if (!el || val == null) return false;
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (setter) setter.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
            count++;
            return true;
        }
        function valueFor(el) {
            const ctx = labelFor(el);
            if (ctx.includes('first')) return firstName || 'Florian';
            if (ctx.includes('last')) return lastName || 'Rolke';
            if (ctx.includes('full name') || /\bname\b/.test(ctx)) return fullName;
            if (ctx.includes('email')) return email;
            if (ctx.includes('phone') || ctx.includes('tel')) return phone;
            if (ctx.includes('address') || ctx.includes('street')) return address;
            if (ctx.includes('city') || ctx.includes('town')) return city;
            if (ctx.includes('state') || ctx.includes('province')) return state;
            if (ctx.includes('zip') || ctx.includes('postal')) return postalCode;
            if (ctx.includes('space') || ctx.includes('lot #') || ctx.includes('unit')) return '1';
            if (ctx.includes('year')) return '1998';
            if (ctx.includes('bed')) return '2';
            if (ctx.includes('bath')) return '1';
            if (ctx.includes('size') || ctx.includes('sq') || ctx.includes('length') || ctx.includes('width')) return '1000';
            if (ctx.includes('make') || ctx.includes('model') || ctx.includes('manufacturer')) return 'Manufactured home';
            if (ctx.includes('condition') || ctx.includes('repairs')) return 'Average';
            if (ctx.includes('asking') || ctx.includes('owe') || ctx.includes('rent') || ctx.includes('price')) return '0';
            return 'N/A';
        }

        const controls = Array.from(document.querySelectorAll('input, textarea, select')).filter(visible);
        const radioGroups = new Set();
        for (const el of controls) {
            const type = (el.type || '').toLowerCase();
            if (['submit', 'button', 'image', 'reset', 'file', 'password'].includes(type)) continue;
            const ctx = labelFor(el);
            if (ctx.includes('credit card') || ctx.includes('card number') || ctx.includes('cvv')) continue;

            if (type === 'radio') {
                if (!el.name || radioGroups.has(el.name)) continue;
                radioGroups.add(el.name);
                const group = controls.filter(x => x.type === 'radio' && x.name === el.name);
                if (group.some(x => x.checked)) continue;
                let choice = group.find(x => /private|lot|email|phone|yes|no/i.test(`${x.value || ''} ${labelFor(x)}`)) || group[0];
                choice.checked = true;
                choice.dispatchEvent(new Event('change', { bubbles: true }));
                count++;
                continue;
            }
            if (type === 'checkbox') {
                const required = el.required || el.getAttribute('aria-required') === 'true' || /consent|agree|sms|email|message/i.test(ctx);
                if (required && !el.checked) {
                    el.checked = true;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    count++;
                }
                continue;
            }
            if (el.tagName === 'SELECT') {
                const current = (el.value || '').trim();
                const currentText = el.selectedOptions?.[0]?.textContent?.trim().toLowerCase() || '';
                if (current && !/select|choose|please/.test(currentText)) continue;
                const options = Array.from(el.options).filter(o => o.value && !o.disabled && !/select|choose|please|--/.test(o.textContent.trim().toLowerCase()));
                if (!options.length) continue;
                const preferred = options.find(o => /email|phone|text|any|morning|afternoon|yes|no/i.test(o.textContent)) || options[0];
                el.value = preferred.value;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                count++;
                continue;
            }
            if ((el.value || '').trim()) continue;
            if (el.tagName === 'TEXTAREA') setValue(el, 'Please contact me by email.');
            else setValue(el, valueFor(el));
        }
        return count;
    }""", [name, email, phone, address, city, state, postal_code])

    clicked = await click_visible_submit(page)
    if not clicked:
        await page.keyboard.press("Enter")
    await page.wait_for_timeout(9000)
    verification = await page.evaluate(r"""() => {
        const body = document.body.innerText.toLowerCase();
        const successPatterns = [
            'thank you', 'thanks for', 'message sent', 'submission received',
            'successfully submitted', 'we will get back', 'we\'ll get back',
            'form submitted', 'request received', 'inquiry received',
            'been received', 'reach out soon', 'contact you soon',
            'excellent', 'congratulations'
        ];
        for (const pat of successPatterns) {
            if (body.includes(pat) && !body.includes('there was a problem')) {
                return { confirmed: true, type: 'success_text', match: pat };
            }
        }
        const errorPatterns = ['there was a problem', 'problem with your submission', 'please review', 'required', 'invalid'];
        for (const pat of errorPatterns) {
            if (body.includes(pat)) return { confirmed: false, type: 'validation_error', match: pat };
        }
        if (body.includes('step 2 of 2') || body.includes('a few more questions')) {
            return { confirmed: null, type: 'still_on_followup_step', match: 'step 2 still visible' };
        }
        return { confirmed: null, type: 'unknown', match: 'no final confirmation detected' };
    }""")
    return {"fields_filled": filled, "clicked": clicked, "verification": verification}


def merge_calendar_links(existing, discovered):
    seen = {link.get("href") for link in existing if link.get("href")}
    for link in discovered or []:
        href = link.get("href")
        if href and href not in seen:
            seen.add(href)
            existing.append(link)
    return existing


async def detect_calendar_links(page):
    """Detect visible and image-backed scheduling links like Acuity/Calendly."""
    return await page.evaluate(r"""() => {
        const providerPatterns = [
            'calendly.com',
            'acuityscheduling.com',
            'cal.com',
            'calendar.google.com',
            'scheduleonce.com',
            'oncehub.com',
            'bookeo.com',
            'setmore.com',
            'youcanbook.me',
            'hubspot.com/meetings',
            'meetings.hubspot.com',
            'savvycal.com',
            'appointlet.com',
            'tidycal.com'
        ];
        const keywordPattern = /(schedule|calendar|book\s+(a\s+)?(call|appointment|meeting)|appointment|meeting|consultation)/i;
        const socialPatterns = [
            'facebook.com/sharer',
            'facebook.com/profile.php',
            'facebook.com/people/',
            'twitter.com/share',
            'x.com/share',
            'linkedin.com/share',
            'pinterest.com/pin'
        ];
        const links = [];
        const seen = new Set();

        function add(href, text, source) {
            if (!href || seen.has(href)) return;
            if (href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return;
            const hrefLower = href.toLowerCase();
            if (hrefLower.startsWith('http://tel:') || hrefLower.startsWith('https://tel:')) return;
            if (socialPatterns.some(pattern => hrefLower.includes(pattern))) return;
            const haystack = `${href} ${text || ''}`.toLowerCase();
            const providerMatch = providerPatterns.some(pattern => hrefLower.includes(pattern));
            const keywordMatch = keywordPattern.test(haystack);
            if (!providerMatch && !keywordMatch) return;

            seen.add(href);
            links.push({
                href,
                text: (text || '').trim().replace(/\s+/g, ' ').slice(0, 160),
                source
            });
        }

        for (const a of document.querySelectorAll('a[href]')) {
            const imageText = Array.from(a.querySelectorAll('img'))
                .map(img => `${img.alt || ''} ${img.src || ''}`)
                .join(' ');
            add(a.href, `${a.textContent || ''} ${imageText}`, 'anchor');
        }

        for (const iframe of document.querySelectorAll('iframe[src]')) {
            add(
                iframe.src,
                iframe.title || iframe.getAttribute('aria-label') || '',
                'iframe'
            );
        }

        return links.slice(0, 20);
    }""")


async def extract_contact_details(page):
    """Capture visible phone/email/address-like contact details for follow-up notes."""
    return await page.evaluate(r"""() => {
        const body = document.body?.innerText || '';
        const lines = body.split(/\n+/).map(line => line.trim()).filter(Boolean);
        const emails = Array.from(new Set((body.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig) || [])));
        const phones = Array.from(new Set((body.match(/(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}/g) || [])
            .map(phone => phone.replace(/\s+/g, ' ').trim())));

        const detailLines = [];
        const usefulPatterns = [
            /call\s+us/i,
            /email\s+us/i,
            /buyers?\s+call/i,
            /sellers?\s+call/i,
            /licensed\s+dealer/i,
            /office/i,
            /contact/i,
            /investor/i,
            /@[A-Z0-9.-]+\.[A-Z]{2,}/i,
            /\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/,
            /\b\d{2,6}\s+[A-Za-z0-9 .'-]+(?:street|st|road|rd|avenue|ave|drive|dr|lane|ln|parkway|pkwy|boulevard|blvd|highway|hwy|court|ct|way)\b/i
        ];

        for (const line of lines) {
            if (line.length > 220) continue;
            if (usefulPatterns.some(pattern => pattern.test(line))) {
                detailLines.push(line);
            }
        }

        const seen = new Set();
        const uniqueLines = detailLines.filter(line => {
            const key = line.toLowerCase();
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        }).slice(0, 24);

        return {
            emails,
            phones,
            notes: uniqueLines.join(' | ')
        };
    }""")


def merge_contact_details(existing, discovered):
    existing = existing or {"emails": [], "phones": [], "notes": ""}
    discovered = discovered or {}
    for key in ("emails", "phones"):
        seen = set(existing.get(key, []))
        for value in discovered.get(key, []) or []:
            if value and value not in seen:
                seen.add(value)
                existing.setdefault(key, []).append(value)

    notes = [part.strip() for part in (existing.get("notes") or "").split(" | ") if part.strip()]
    seen_notes = {note.lower() for note in notes}
    for part in (discovered.get("notes") or "").split(" | "):
        part = part.strip()
        if part and part.lower() not in seen_notes:
            seen_notes.add(part.lower())
            notes.append(part)
    existing["notes"] = " | ".join(notes[:40])
    return existing


async def detect_checkout_or_payment_page(page):
    """Avoid domain-sale, checkout, cart, and payment forms."""
    return await page.evaluate(r"""() => {
        const text = (document.body?.innerText || '').toLowerCase();
        const url = location.href.toLowerCase();
        const html = document.body?.innerHTML.toLowerCase() || '';
        const paymentInputs = document.querySelectorAll(
            'input[name*="card" i], input[id*="card" i], input[autocomplete*="cc-" i], input[name*="cvv" i], input[id*="cvv" i]'
        ).length;
        const strongCheckoutSignals = [
            'card number',
            'expiration date',
            'billing address',
            'shopping cart',
            'obtener este dominio',
            'está a la venta',
            'domain verified',
            'godaddy operating company',
            'this domain is for sale'
        ];
        const matched = strongCheckoutSignals.filter(signal => text.includes(signal) || url.includes(signal.replace(/\s+/g, '-')));
        if (html.includes('godaddy') && (text.includes('domain') || text.includes('dominio'))) {
            matched.push('godaddy domain sale');
        }
        return {
            is_checkout: paymentInputs > 0 || matched.length > 0,
            payment_inputs: paymentInputs,
            signals: Array.from(new Set(matched)).slice(0, 8)
        };
    }""")


async def assess_page_quality(page):
    """Lightweight preflight score to avoid low-quality/no-form pages."""
    return await page.evaluate(r"""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        const url = location.href.toLowerCase();
        const links = Array.from(document.querySelectorAll('a[href]'));
        const forms = Array.from(document.querySelectorAll('form'));
        const fields = Array.from(document.querySelectorAll(
            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select'
        )).filter(el => {
            const r = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return style.display !== 'none' && style.visibility !== 'hidden' && r.width > 8 && r.height > 8;
        });
        const contactLinks = links.filter(a => /contact|get.?in.?touch|request|quote|estimate|schedule|book/i.test(`${a.textContent || ''} ${a.href || ''}`));
        const socialOnlyLinks = links.length > 0 && links.every(a => /facebook|instagram|linkedin|youtube|twitter|x\.com|google\.com/.test(a.href || ''));
        const phoneCount = (body.match(/(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}/g) || []).length;
        const emailCount = (body.match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/gi) || []).length;

        const positiveTerms = [
            'plumbing', 'plumber', 'drain', 'sewer', 'water heater', 'leak repair',
            'hvac', 'air conditioning', 'heating', 'schedule service', 'request service',
            'contact us', 'get a quote', 'free estimate'
        ];
        const negativeTerms = [
            'domain is for sale', 'obtener este dominio', 'godaddy operating company',
            'shopping cart', 'add to cart', 'checkout', 'billing address',
            'plumbing supply', 'supply store', 'wholesale', 'distributor',
            'manufacturer', 'factory outlet', 'training center', 'union dues'
        ];
        let score = 0;
        const reasons = [];
        for (const term of positiveTerms) {
            if (body.includes(term) || url.includes(term.replace(/\s+/g, '-'))) {
                score += 8;
                reasons.push('+' + term);
            }
        }
        for (const term of negativeTerms) {
            if (body.includes(term) || url.includes(term.replace(/\s+/g, '-'))) {
                score -= 18;
                reasons.push('-' + term);
            }
        }
        if (forms.length > 0) { score += 20; reasons.push('+form'); }
        if (fields.length >= 2) { score += 15; reasons.push('+fillable_fields'); }
        if (contactLinks.length > 0) { score += 12; reasons.push('+contact_link'); }
        if (phoneCount > 0) { score += 5; reasons.push('+phone'); }
        if (emailCount > 0) { score += 5; reasons.push('+email'); }
        if (socialOnlyLinks) { score -= 25; reasons.push('-social_only'); }
        if (body.length < 300) { score -= 20; reasons.push('-thin_page'); }

        return {
            score,
            reasons: Array.from(new Set(reasons)).slice(0, 12),
            forms: forms.length,
            fields: fields.length,
            contact_links: contactLinks.length,
            phones: phoneCount,
            emails: emailCount,
            social_only: socialOnlyLinks
        };
    }""")


async def find_contact_page(page, base_url):
    """Find the contact page by reading the site's actual navigation."""
    # First check if current page already has a contact form
    has_form = await page.evaluate("""() => {
        const forms = document.querySelectorAll('form');
        const inputs = document.querySelectorAll('input[type="text"], input[type="email"], textarea');
        return forms.length > 0 && inputs.length > 1;
    }""")
    if has_form:
        print(f"    [NAV] Homepage already has a contact form")
        return page.url

    # Read ALL navigation links from the page — nav, header, footer, menus
    all_nav_links = await page.evaluate(r"""() => {
        const results = [];
        const seen = new Set();

        // Priority 1: nav/header/menu links (main navigation)
        const navAreas = document.querySelectorAll('nav, header, [role="navigation"], .menu, .nav, .navbar, #menu, #nav, #navigation');
        for (const area of navAreas) {
            for (const a of area.querySelectorAll('a[href]')) {
                const href = a.href;
                if (seen.has(href) || !href || href === '#' || href.startsWith('javascript:') || href.startsWith('tel:')) continue;
                seen.add(href);
                const text = (a.textContent || '').trim().replace(/\s+/g, ' ').substring(0, 60);
                if (text.length > 0) {
                    results.push({ href, text, source: 'nav', priority: 1 });
                }
            }
        }

        // Priority 2: footer links
        const footerAreas = document.querySelectorAll('footer, .footer, #footer, [role="contentinfo"]');
        for (const area of footerAreas) {
            for (const a of area.querySelectorAll('a[href]')) {
                const href = a.href;
                if (seen.has(href) || !href || href === '#' || href.startsWith('javascript:') || href.startsWith('tel:')) continue;
                seen.add(href);
                const text = (a.textContent || '').trim().replace(/\s+/g, ' ').substring(0, 60);
                if (text.length > 0) {
                    results.push({ href, text, source: 'footer', priority: 2 });
                }
            }
        }

        // Priority 3: all remaining page links
        for (const a of document.querySelectorAll('a[href]')) {
            const href = a.href;
            if (seen.has(href) || !href || href === '#' || href.startsWith('javascript:') || href.startsWith('tel:')) continue;
            seen.add(href);
            const text = (a.textContent || '').trim().replace(/\s+/g, ' ').substring(0, 60);
            if (text.length > 0) {
                results.push({ href, text, source: 'body', priority: 3 });
            }
        }

        return results;
    }""")

    print(f"    [NAV] Found {len(all_nav_links)} links on page")

    # Score each link for contact-page likelihood
    contact_keywords = ['contact', 'kontakt', 'get in touch', 'reach us', 'reach out',
                        'send message', 'write to us', 'inquiry', 'enquiry',
                        'schedule', 'consultation', 'book a call', 'free consultation']
    # These are NOT contact pages
    exclude_keywords = ['contact lens', 'login', 'sign in', 'cart', 'shop', 'blog',
                        'facebook', 'twitter', 'instagram', 'linkedin', 'youtube',
                        'privacy', 'terms', 'sitemap']
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.")

    scored = []
    for link in all_nav_links:
        text = link["text"].lower()
        href = link["href"].lower()
        link_host = urlparse(link["href"]).netloc.lower().removeprefix("www.")

        # Skip mailto, external social, excluded
        if "mailto:" in href:
            continue
        if "support.google.com/accounts" in href or "accounts.google.com" in href:
            continue
        if base_host and link_host and link_host != base_host:
            continue
        if any(ex in text for ex in exclude_keywords):
            continue

        score = 0
        # Exact text match "Contact" or "Contact Us" in nav = highest score
        if re.match(r'^contact(\s+us)?$', text.strip()):
            score = 100
        elif any(kw in text for kw in contact_keywords):
            score = 80
        elif any(kw in href for kw in ['/contact', '/get-in-touch', '/reach-us', '/inquiry']):
            score = 60
        # "About" pages sometimes have contact forms
        elif 'about' in text and 'contact' in href:
            score = 40

        if score > 0:
            # Boost only after a real contact/scheduling signal exists.
            if link["source"] == "nav":
                score += 10
            elif link["source"] == "footer":
                score += 5
            scored.append((score, link))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    if scored:
        # Show top candidates
        for s, l in scored[:3]:
            print(f"    [NAV] Candidate (score {s}): \"{l['text']}\" → {l['href'][:70]} [{l['source']}]")

        best = scored[0][1]
        print(f"    [NAV] Selected: \"{best['text']}\" → {best['href'][:80]}")
        return best["href"]

    # Last resort: show what nav links we DID find so we can debug
    nav_only = [l for l in all_nav_links if l["source"] == "nav"]
    if nav_only:
        print(f"    [NAV] No contact link found. Nav links seen:")
        for l in nav_only[:10]:
            print(f"           \"{l['text']}\" → {l['href'][:60]}")

    print(f"    [NAV] No contact link found; trying common contact/quote paths")
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in CONTACT_PATHS:
        candidate = urljoin(base, path)
        try:
            await page.goto(candidate, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(1200)
            has_form = await page.evaluate("""() => {
                const forms = document.querySelectorAll('form');
                const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], textarea');
                return forms.length > 0 && inputs.length > 1;
            }""")
            if has_form:
                print(f"    [NAV] Common path has form: {candidate}")
                return candidate
        except Exception:
            continue

    print(f"    [NAV] No contact page found")
    return None


async def detect_captcha_type(page):
    """Detect what type of CAPTCHA is on the page."""
    return await page.evaluate(r"""() => {
        const bodyHtml = document.body.innerHTML;
        const body = bodyHtml.toLowerCase();
        const result = { type: 'none', site_key: null };

        function selectorFor(el) {
            if (!el) return null;
            if (el.id) return '#' + CSS.escape(el.id);
            if (el.name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]`;
            const all = Array.from(document.querySelectorAll(el.tagName.toLowerCase()));
            const idx = all.indexOf(el);
            return `${el.tagName.toLowerCase()}:nth-of-type(${idx + 1})`;
        }

        function decodeRocketLazyScripts() {
            const decoded = [];
            for (const s of document.querySelectorAll('script[data-rocketlazyloadscript]')) {
                const val = s.getAttribute('data-rocketlazyloadscript') || '';
                const m = val.match(/^data:text\/javascript;base64,(.+)$/);
                if (m) {
                    try { decoded.push(atob(m[1])); } catch(e) {}
                }
            }
            return decoded;
        }

        // Custom image/text CAPTCHAs like "Enter the code from the image here".
        if (body.includes('enter the code from the image') ||
            body.includes('security code') ||
            body.includes('verification code') ||
            body.includes('captcha code')) {
            const images = Array.from(document.querySelectorAll('img')).filter(img => {
                const r = img.getBoundingClientRect();
                const src = (img.src || '').toLowerCase();
                const alt = (img.alt || '').toLowerCase();
                return r.width > 35 && r.height > 12 &&
                    (src.includes('captcha') || src.includes('security') || src.includes('code') ||
                     alt.includes('captcha') || alt.includes('security') || alt.includes('code') ||
                     body.includes('enter the code from the image'));
            });
            const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea')).filter(el => {
                const r = el.getBoundingClientRect();
                const ctx = `${el.name || ''} ${el.id || ''} ${el.placeholder || ''}`.toLowerCase();
                return r.width > 30 && r.height > 10 &&
                    (ctx.includes('captcha') || ctx.includes('security') || ctx.includes('code') || !el.value);
            });
            if (images.length && inputs.length) {
                const img = images[images.length - 1];
                const imgRect = img.getBoundingClientRect();
                let bestInput = inputs[inputs.length - 1];
                let bestDist = Infinity;
                for (const input of inputs) {
                    const r = input.getBoundingClientRect();
                    const dist = Math.abs(r.top - imgRect.top) + Math.max(0, imgRect.left - r.left);
                    if (r.top >= imgRect.top - 80 && dist < bestDist) {
                        bestDist = dist;
                        bestInput = input;
                    }
                }
                result.type = 'custom_image';
                result.image_selector = selectorFor(img);
                result.input_selector = selectorFor(bestInput);
                return result;
            }
        }

        // reCAPTCHA v2 (visible checkbox OR invisible)
        const recapEl = document.querySelector('[data-sitekey]');
        if (recapEl) {
            const isInvisible = recapEl.getAttribute('data-size') === 'invisible' ||
                                recapEl.getAttribute('data-badge') !== null ||
                                recapEl.classList.contains('g-recaptcha-invisible');
            result.type = isInvisible ? 'recaptcha_v2_invisible' : 'recaptcha_v2';
            result.site_key = recapEl.getAttribute('data-sitekey');
            return result;
        }
        const recapIframe = document.querySelector('iframe[src*="recaptcha"]');
        if (recapIframe) {
            // Check if invisible by looking for badge or invisible param
            const isInvisible = recapIframe.src.includes('size=invisible') ||
                                document.querySelector('.grecaptcha-badge') !== null;
            result.type = isInvisible ? 'recaptcha_v2_invisible' : 'recaptcha_v2';
            const match = recapIframe.src.match(/[?&]k=([^&]+)/);
            if (match) result.site_key = match[1];
            return result;
        }
        // Check for invisible badge (no iframe visible yet, loads on submit)
        if (document.querySelector('.grecaptcha-badge')) {
            result.type = 'recaptcha_v2_invisible';
            // Find site key from script tags
            const scripts = document.querySelectorAll('script[src*="recaptcha"]');
            for (const s of scripts) {
                const m = s.src.match(/render=([^&]+)/);
                if (m && m[1] !== 'explicit') { result.site_key = m[1]; break; }
            }
            // Also check inline scripts for sitekey
            if (!result.site_key) {
                for (const s of document.querySelectorAll('script:not([src])')) {
                    const m = (s.textContent || '').match(/sitekey['":\s]+['"]([^'"]+)['"]/i);
                    if (m) { result.site_key = m[1]; break; }
                }
            }
            return result;
        }

        // reCAPTCHA v3 (invisible, loaded via render=SITEKEY)
        const v3Scripts = document.querySelectorAll('script[src*="recaptcha"][src*="render="]');
        if (v3Scripts.length > 0) {
            result.type = 'recaptcha_v3';
            for (const s of v3Scripts) {
                const m = s.src.match(/render=([^&]+)/);
                if (m && m[1] !== 'explicit') { result.site_key = m[1]; break; }
            }
            if (result.site_key) return result;
        }

        // WordPress plugins may lazy-load invisible reCAPTCHA config as base64.
        const lazyScripts = decodeRocketLazyScripts();
        for (const txt of lazyScripts) {
            if (txt.includes('grecaptcha.render') || txt.includes('grecaptcha.execute') || txt.includes('sitekey')) {
                result.type = txt.includes("'size': 'invisible'") || txt.includes('"size": "invisible"')
                    ? 'recaptcha_v2_invisible'
                    : 'recaptcha_v2';
                const m = txt.match(/['"]sitekey['"]\s*:\s*['"]([^'"]+)['"]/i);
                if (m) result.site_key = m[1];
                return result;
            }
        }

        // hCaptcha
        if (document.querySelector('.h-captcha') || body.includes('hcaptcha')) {
            result.type = 'hcaptcha';
            const hEl = document.querySelector('.h-captcha[data-sitekey]');
            if (hEl) result.site_key = hEl.getAttribute('data-sitekey');
            return result;
        }

        // Cloudflare Turnstile
        if (document.querySelector('.cf-turnstile') || body.includes('turnstile')) {
            result.type = 'turnstile';
            const tEl = document.querySelector('.cf-turnstile[data-sitekey]');
            if (tEl) result.site_key = tEl.getAttribute('data-sitekey');
            return result;
        }

        return result;
    }""")


async def solve_captcha(page, captcha_info):
    """Solve any detected CAPTCHA using CapSolver."""
    import capsolver

    api_key = os.environ.get("CAPSOLVER_API_KEY") or os.environ.get("Capsolver_API_KEY")
    if not api_key:
        print("    [CAPSOLVER] No CAPSOLVER_API_KEY in .env")
        return False

    capsolver.api_key = api_key
    captcha_type = captcha_info.get("type", "none")
    site_key = captcha_info.get("site_key")
    page_url = page.url

    if captcha_type == "none":
        return True  # No CAPTCHA to solve

    if captcha_type == "custom_image":
        image_selector = captcha_info.get("image_selector")
        input_selector = captcha_info.get("input_selector")
        if not image_selector or not input_selector:
            print("    [CAPSOLVER] Custom image CAPTCHA detected but image/input selector missing")
            return False
        print(f"    [CAPSOLVER] Custom image CAPTCHA detected; solving image...")
        try:
            image_bytes = await page.locator(image_selector).last.screenshot(timeout=10000)
            image_b64 = base64.b64encode(image_bytes).decode("ascii")

            def _solve_image():
                return capsolver.solve({
                    "type": "ImageToTextTask",
                    "body": image_b64,
                })

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                solution = await loop.run_in_executor(pool, _solve_image)

            nested_solution = solution.get("solution") if isinstance(solution.get("solution"), dict) else {}
            text = (
                solution.get("text") or
                solution.get("answer") or
                solution.get("captcha") or
                nested_solution.get("text") or
                ""
            )
            text = (text or "").strip()
            if not text:
                print(f"    [CAPSOLVER] No text in image CAPTCHA response: {list(solution.keys())}")
                return False
            print(f"    [CAPSOLVER] Image CAPTCHA solved as '{text}'")
            success = await set_field_value(page, input_selector, text)
            if not success:
                await page.fill(input_selector, text, timeout=5000)
            await page.wait_for_timeout(800)
            return True
        except Exception as e:
            print(f"    [CAPSOLVER] Image CAPTCHA error: {str(e)[:200]}")
            return False

    if not site_key:
        print(f"    [CAPSOLVER] {captcha_type} detected but no site key found")
        return False

    print(f"    [CAPSOLVER] {captcha_type} detected | site key: {site_key[:20]}...")
    print(f"    [CAPSOLVER] Sending to CapSolver API...")

    try:
        # Map captcha type to CapSolver task type
        task_config = {"websiteURL": page_url, "websiteKey": site_key}

        if captcha_type == "recaptcha_v2":
            task_config["type"] = "ReCaptchaV2TaskProxyLess"
        elif captcha_type == "recaptcha_v2_invisible":
            task_config["type"] = "ReCaptchaV2TaskProxyLess"
            task_config["isInvisible"] = True
        elif captcha_type == "recaptcha_v3":
            task_config["type"] = "ReCaptchaV3TaskProxyLess"
            task_config["pageAction"] = "submit"
            task_config["minScore"] = 0.7
        elif captcha_type == "hcaptcha":
            task_config["type"] = "HCaptchaTaskProxyLess"
        elif captcha_type == "turnstile":
            task_config["type"] = "AntiTurnstileTaskProxyLess"
        else:
            print(f"    [CAPSOLVER] Unsupported type: {captcha_type}")
            return False

        # Run blocking solve in thread to keep Playwright alive
        def _solve():
            return capsolver.solve(task_config)

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            solution = await loop.run_in_executor(pool, _solve)

        # Get the token from solution
        token = (solution.get("gRecaptchaResponse") or
                 solution.get("token") or
                 solution.get("captcha_response") or "")

        if not token:
            print(f"    [CAPSOLVER] No token in response: {list(solution.keys())}")
            return False

        print(f"    [CAPSOLVER] Got token ({len(token)} chars) — injecting...")

        # Inject token based on type
        if captcha_type.startswith("recaptcha"):
            injected = await page.evaluate("""(token) => {
                let count = 0;
                document.querySelectorAll('textarea[name="g-recaptcha-response"], #g-recaptcha-response').forEach(ta => {
                    ta.value = token; count++;
                });
                document.querySelectorAll('textarea[id*="recaptcha-response"]').forEach(ta => {
                    ta.value = token; count++;
                });
                document.querySelectorAll('input[name="recaptcha_token"], textarea[name="recaptcha_token"], input[id*="recaptcha_token"]').forEach(el => {
                    el.value = token;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    count++;
                });
                try {
                    if (typeof ___grecaptcha_cfg !== 'undefined') {
                        const clients = ___grecaptcha_cfg.clients;
                        for (const cid in clients) {
                            const walk = (obj, d) => {
                                if (d > 5 || !obj) return;
                                for (const k in obj) {
                                    if (typeof obj[k] === 'function' && k === 'callback') obj[k](token);
                                    if (typeof obj[k] === 'object') walk(obj[k], d+1);
                                }
                            };
                            walk(clients[cid], 0);
                        }
                    }
                } catch(e) {}
                return count;
            }""", token)
        elif captcha_type == "hcaptcha":
            injected = await page.evaluate("""(token) => {
                let count = 0;
                document.querySelectorAll('textarea[name="h-captcha-response"], [name="g-recaptcha-response"]').forEach(ta => {
                    ta.value = token; count++;
                });
                return count;
            }""", token)
        elif captcha_type == "turnstile":
            injected = await page.evaluate("""(token) => {
                let count = 0;
                document.querySelectorAll('[name="cf-turnstile-response"], input[name="turnstileToken"]').forEach(el => {
                    el.value = token; count++;
                });
                return count;
            }""", token)
        else:
            injected = 0

        print(f"    [CAPSOLVER] Token injected into {injected} field(s)")
        await page.wait_for_timeout(1000)
        return True

    except Exception as e:
        print(f"    [CAPSOLVER] Error: {str(e)[:200]}")
        return False


async def detect_form_fields(page):
    """Detect contact form fields on the page.

    IMPORTANT: When multiple forms exist (e.g. contact form + newsletter subscribe),
    we must identify the CONTACT form (the one with the most fields / has a textarea)
    and scope all field detection to that specific <form> element. This prevents
    newsletter email fields from overwriting the contact form email field.
    """
    return await page.evaluate(r"""() => {
        const result = {
            has_form: false,
            has_mailto: false,
            mailto_email: null,
            fields: {},
        };

        // Mailto check
        const mailtoLinks = document.querySelectorAll('a[href^="mailto:"]');
        if (mailtoLinks.length > 0) {
            result.has_mailto = true;
            result.mailto_email = mailtoLinks[0].href.replace('mailto:', '').split('?')[0];
        }

        const allForms = document.querySelectorAll('form');
        if (allForms.length === 0) {
            const inputs = document.querySelectorAll('input[type="text"], input[type="email"], textarea');
            if (inputs.length < 2) return result;
        }

        // CRITICAL: Find the CONTACT form, not the newsletter/subscribe form.
        // The contact form is the one with the most input fields and/or a textarea.
        // Newsletter forms typically have just 1 email field.
        let contactForm = null;
        let bestScore = 0;

        for (const form of allForms) {
            const inputs = form.querySelectorAll('input:not([type="submit"]):not([type="button"]):not([type="hidden"]):not([type="checkbox"]):not([type="radio"])');
            const textareas = form.querySelectorAll('textarea');
            const visibleInputs = Array.from(inputs).filter(el => el.offsetHeight > 0 || el.offsetWidth > 0);
            const formCtx = `${form.innerText || ''} ${form.id || ''} ${form.className || ''} ${form.getAttribute('role') || ''} ${form.getAttribute('action') || ''}`.toLowerCase();

            // Score: number of visible inputs + 5 bonus for having a textarea (strong contact form signal)
            let score = visibleInputs.length + (textareas.length > 0 ? 5 : 0);

            if (/contact|message|quote|estimate|request|service|appointment|inquiry|get in touch/.test(formCtx)) {
                score += 8;
            }
            if (/search|site search|search the site|wp-block-search/.test(formCtx)) {
                score -= 20;
            }
            const searchInputs = visibleInputs.filter(el => {
                const ctx = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
                return /search/.test(ctx);
            });
            if (searchInputs.length && visibleInputs.length <= 2 && textareas.length === 0) {
                score -= 40;
            }

            // Penalty for forms inside footer (likely newsletter)
            if (form.closest('footer, .footer, #footer, [role="contentinfo"]')) {
                score -= 10;
            }

            if (score > bestScore) {
                bestScore = score;
                contactForm = form;
            }
        }

        // If no form found with good score, fall back only to a non-search form with 2+ inputs.
        if (!contactForm && allForms.length > 0) {
            contactForm = Array.from(allForms).find(form => {
                const inputs = Array.from(form.querySelectorAll('input:not([type="submit"]):not([type="button"]):not([type="hidden"])'))
                    .filter(el => el.offsetHeight > 0 || el.offsetWidth > 0);
                const ctx = `${form.innerText || ''} ${form.id || ''} ${form.className || ''} ${form.getAttribute('role') || ''} ${form.getAttribute('action') || ''}`.toLowerCase();
                return inputs.length >= 2 && !/search|site search|wp-block-search/.test(ctx);
            });
        }

        if (!contactForm) return result;

        result.has_form = true;
        const formIndex = Array.from(allForms).indexOf(contactForm);
        result.form_index = formIndex;
        result.total_forms = allForms.length;

        // Helper: check if a field is required
        function isRequired(el) {
            if (el.required || el.getAttribute('aria-required') === 'true') return true;
            const labelEl = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
            if (labelEl && (labelEl.textContent || '').includes('*')) return true;
            if ((el.placeholder || '').includes('*')) return true;
            const parent = el.parentElement;
            if (parent) {
                const asterisk = parent.querySelector('.required, .asterisk, abbr[title="required"]');
                if (asterisk) return true;
                const prevSib = el.previousElementSibling;
                if (prevSib && (prevSib.textContent || '').includes('*')) return true;
            }
            return false;
        }

        // Scan inputs and selects ONLY within the identified contact form
        for (const el of contactForm.querySelectorAll('input, select')) {
            const inputType = (el.type || 'text').toLowerCase();
            if (['submit', 'button', 'hidden', 'checkbox', 'radio', 'file', 'image', 'reset'].includes(inputType)) continue;
            if (el.offsetHeight === 0 && el.offsetWidth === 0) continue;

            const n = (el.name || '').toLowerCase();
            const id = (el.id || '').toLowerCase();
            const ph = (el.placeholder || '').toLowerCase();
            const labelEl = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
            const label = (labelEl?.textContent || '').toLowerCase();
            const prevLabel = el.previousElementSibling?.textContent?.toLowerCase() || '';
            const parentText = el.parentElement?.textContent?.toLowerCase().trim() || '';
            const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
            const ctx = n + ' ' + id + ' ' + ph + ' ' + label + ' ' + prevLabel + ' ' + parentText + ' ' + ariaLabel;
            const looksInternal = ctx.includes('company email for contacts') || ctx.includes('for contacts') || ctx.includes('routing');
            const sel = el.id ? '#' + CSS.escape(el.id) : (el.name ? `[name="${CSS.escape(el.name)}"]` : null);
            if (!sel) continue;
            const req = isRequired(el);
            const isVisible = el.offsetHeight > 0 || el.offsetWidth > 0;
            const isSelectEl = el.tagName === 'SELECT';
            const looksLikeAddressAutocomplete = (
                id.includes('autocomplete') ||
                ctx.includes('enter your address') ||
                ctx.includes('property address') ||
                ctx.includes('service address')
            );
            let options = null;
            if (isSelectEl) {
                options = Array.from(el.options).map(o => ({ value: o.value, text: o.textContent.trim() })).filter(o => o.value);
            }
            const gravityAddressPart = (
                n.match(/(?:^|_)input_\d+\.([1-6])$/)?.[1] ||
                id.match(/_4_([1-6])$/)?.[1] ||
                n.match(/\.([1-6])$/)?.[1]
            );

            if ((ctx.includes('first') && (ctx.includes('name') || label.trim() === 'first' || parentText === 'first')) ||
                ctx.includes('fname') || ctx.includes('first_name') || ctx.includes('vorname')) {
                result.fields.first_name = { selector: sel, required: req };
            } else if ((ctx.includes('last') && (ctx.includes('name') || label.trim() === 'last' || parentText === 'last')) ||
                ctx.includes('lname') || ctx.includes('last_name') || ctx.includes('nachname')) {
                result.fields.last_name = { selector: sel, required: req };
            } else if (ctx.includes('name') && !ctx.includes('email') && !ctx.includes('company') && !ctx.includes('user') && !result.fields.name && !result.fields.first_name) {
                result.fields.name = { selector: sel, required: req };
            }
            if (!looksInternal && (ctx.includes('email') || inputType === 'email') &&
                (!result.fields.email || req || !result.fields.email.required)) {
                result.fields.email = { selector: sel, required: req };
            }
            if (ctx.includes('phone') || ctx.includes('tel') || inputType === 'tel') {
                result.fields.phone = { selector: sel, required: req };
            }
            if (ctx.includes('subject') || ctx.includes('subj') || ctx.includes('betreff')) {
                result.fields.subject = { selector: sel, required: req };
            }
            if (!looksInternal && inputType !== 'email' &&
                (ctx.includes('company') || ctx.includes('organization') || ctx.includes('firma'))) {
                result.fields.company = { selector: sel, required: req };
            }
            if (gravityAddressPart === '1') {
                if (!result.fields.address || !result.fields.address.visible || isVisible) {
                    result.fields.address = { selector: sel, required: req, visible: isVisible };
                }
            } else if (gravityAddressPart === '3') {
                result.fields.city = { selector: sel, required: req, visible: isVisible };
            } else if (gravityAddressPart === '4') {
                result.fields.state = { selector: sel, required: req, visible: isVisible };
            } else if (gravityAddressPart === '5') {
                result.fields.postal_code = { selector: sel, required: req, visible: isVisible };
            } else if (ctx.includes('address') || ctx.includes('street') || ctx.includes('service address') || ctx.includes('autocomplete')) {
                if (!result.fields.address || !result.fields.address.visible || isVisible) {
                    result.fields.address = { selector: sel, required: req, visible: isVisible };
                }
            }
            if (!looksLikeAddressAutocomplete && (ctx.includes('city') || ctx.includes('town'))) {
                result.fields.city = { selector: sel, required: req, visible: isVisible };
            }
            if (!looksLikeAddressAutocomplete && (ctx.includes('state') || ctx.includes('province'))) {
                result.fields.state = { selector: sel, required: req, visible: isVisible };
            }
            if (!looksLikeAddressAutocomplete && (ctx.includes('zip') || ctx.includes('postal'))) {
                result.fields.postal_code = { selector: sel, required: req, visible: isVisible };
            }
            if (ctx.includes('space #') || ctx.includes('space number') || ctx.includes('lot #') || ctx.includes('lot number')) {
                result.fields.space_number = { selector: sel, required: req, visible: isVisible };
            }
            if (isSelectEl && !result.fields[ctx.split(' ')[0]]) {
                const cleanLabel = (label || prevLabel || ph || n).replace('*', '').trim();
                if (cleanLabel && !['name','email','phone','subject','company'].some(k => ctx.includes(k))) {
                    result.fields['_select_' + n] = { selector: sel, required: req, type: 'select', label: cleanLabel, options };
                }
            }
        }

        // Some Gravity/Carrot forms keep a validation-relevant email field hidden
        // until JS/autocomplete expands the form. Fill it if no visible email was mapped.
        if (!result.fields.email) {
            for (const el of contactForm.querySelectorAll('input[type="email"], input[type="text"]')) {
                const n = (el.name || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                if (n.includes('hp') || id.includes('hp') || n.includes('honeypot') || id.includes('honeypot')) continue;
                const labelEl = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                const label = (labelEl?.textContent || '').toLowerCase();
                const ph = (el.placeholder || '').toLowerCase();
                const ctx = `${n} ${id} ${label} ${ph}`;
                if (!ctx.includes('email')) continue;
                const sel = el.id ? '#' + CSS.escape(el.id) : (el.name ? `[name="${CSS.escape(el.name)}"]` : null);
                if (sel) {
                    result.fields.email = { selector: sel, required: isRequired(el), hidden: el.offsetHeight === 0 && el.offsetWidth === 0 };
                    break;
                }
            }
        }

        // Required radio/checkbox groups are common on cash-offer forms:
        // "private lot / park" and SMS consent. Pick the safest generic option.
        const groupedChoices = new Map();
        for (const el of contactForm.querySelectorAll('input[type="radio"], input[type="checkbox"]')) {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) continue;
            const name = el.name || el.id;
            if (!name) continue;
            if (!groupedChoices.has(name)) groupedChoices.set(name, []);
            groupedChoices.get(name).push(el);
        }
        for (const [groupName, items] of groupedChoices.entries()) {
            const first = items[0];
            const type = (first.type || '').toLowerCase();
            const containerText = (
                first.closest('.gfield, .form-field, fieldset, li, div')?.textContent || ''
            ).toLowerCase();
            const required = isRequired(first) || containerText.includes('*') || containerText.includes('required') || containerText.includes('consent');
            const choiceData = items.map(el => {
                const labelEl = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
                return {
                    selector: el.id ? '#' + CSS.escape(el.id) : `[name="${CSS.escape(el.name)}"][value="${CSS.escape(el.value)}"]`,
                    value: el.value || '',
                    label: (labelEl?.textContent || el.value || '').trim()
                };
            });
            const fieldKey = `_${type}_${groupName.replace(/[^a-zA-Z0-9_]/g, '_')}`;
            result.fields[fieldKey] = {
                selector: choiceData[0]?.selector,
                required,
                type,
                label: containerText.replace(/\s+/g, ' ').trim().slice(0, 120),
                choices: choiceData
            };
        }

        // Find message textarea ONLY within the contact form
        for (const ta of contactForm.querySelectorAll('textarea')) {
            const taId = (ta.id || '').toLowerCase();
            const taName = (ta.name || '').toLowerCase();
            if (taId.includes('recaptcha') || taName.includes('recaptcha')) continue;
            if (taId.includes('captcha') || taName.includes('captcha')) continue;
            if (ta.offsetHeight === 0 && ta.offsetWidth === 0) continue;
            const sel = ta.id ? '#' + CSS.escape(ta.id) : (ta.name ? `textarea[name="${CSS.escape(ta.name)}"]` : 'textarea:not([name*="recaptcha"])');
            result.fields.message = { selector: sel, required: isRequired(ta) };
            break;
        }

        // Capture additional required text fields that are not the main message.
        // Plumbing/HVAC service forms often ask for "Service Needed" or
        // "Description of your system" separately from the message field.
        const claimedSelectors = new Set(
            Object.values(result.fields)
                .filter(f => f && f.selector)
                .map(f => f.selector)
        );
        let extraTextIndex = 0;
        for (const el of contactForm.querySelectorAll('input, textarea')) {
            const inputType = (el.type || 'text').toLowerCase();
            if (['submit', 'button', 'hidden', 'checkbox', 'radio', 'file', 'image', 'reset', 'password'].includes(inputType)) continue;
            if (el.offsetHeight === 0 && el.offsetWidth === 0) continue;
            const sel = el.id ? '#' + CSS.escape(el.id) : (el.name ? `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]` : null);
            if (!sel || claimedSelectors.has(sel)) continue;

            const labelEl = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
            const label = (labelEl?.textContent || '').toLowerCase();
            const prevLabel = el.previousElementSibling?.textContent?.toLowerCase() || '';
            const parentText = el.parentElement?.textContent?.toLowerCase().trim() || '';
            const ctx = `${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${label} ${prevLabel} ${parentText} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
            if (ctx.includes('recaptcha') || ctx.includes('captcha') || ctx.includes('honeypot')) continue;
            if (ctx.includes('username') || ctx.includes('password')) continue;
            const shouldFill = isRequired(el) || /service|description|system|unit|question|comment|details|request|issue/.test(ctx);
            if (!shouldFill) continue;

            extraTextIndex++;
            result.fields[`_text_${extraTextIndex}`] = {
                selector: sel,
                required: isRequired(el),
                type: 'text',
                input_type: inputType,
                label: (label || prevLabel || el.placeholder || el.name || el.id || 'additional text field')
                    .replace('*', '')
                    .trim()
                    .replace(/\s+/g, ' ')
                    .slice(0, 160)
            };
            claimedSelectors.add(sel);
        }

        // Find submit button ONLY within the contact form
        const btns = contactForm.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type])');
        for (const btn of btns) {
            const text = (btn.textContent || btn.value || '').toLowerCase();
            if (text.match(/send|submit|contact|get in touch|request|anfrage|absenden/)) {
                const sel = btn.id ? '#' + CSS.escape(btn.id) : null;
                result.fields.submit = { selector: sel || 'button[type="submit"], input[type="submit"]', text: (btn.textContent || btn.value || '').trim() };
                break;
            }
        }
        if (!result.fields.submit && btns.length > 0) {
            const btn = btns[0];
            const sel = btn.id ? '#' + CSS.escape(btn.id) : null;
            result.fields.submit = { selector: sel || 'button[type="submit"], input[type="submit"]', text: (btn.textContent || btn.value || '').trim() };
        }

        return result;
    }""")


async def repair_validation_fields(page, name, email, phone, company, subject, message,
                                   address, city, state, postal_code):
    """After a failed submit, fill any browser-invalid or visibly required fields."""
    return await page.evaluate(r"""(args) => {
        const [fullName, email, phone, company, subject, message, address, city, state, postalCode] = args;
        const [firstName, ...lastParts] = String(fullName || '').split(/\s+/);
        const lastName = lastParts.join(' ') || '';
        const phoneDigits = String(phone || '').replace(/\D/g, '');
        const fullAddress = [address, city, state, postalCode].filter(Boolean).join(', ');
        const repairLabels = [];
        let filled = 0;

        function visible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && r.width > 5 && r.height > 5;
        }
        function labelFor(el) {
            const labelEl = el.closest('label') || (el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null);
            const nearby = el.closest('.gfield, .form-field, .field, .form-group, li, p, div');
            return `${labelEl?.textContent || ''} ${el.previousElementSibling?.textContent || ''} ${nearby?.textContent || ''}`.replace(/\s+/g, ' ').trim();
        }
        function ctxFor(el) {
            return `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${labelFor(el)}`.toLowerCase();
        }
        function isRequiredish(el) {
            if (el.required || el.getAttribute('aria-required') === 'true') return true;
            const ctx = ctxFor(el);
            return ctx.includes('*') || ctx.includes('required') || el.getAttribute('aria-invalid') === 'true';
        }
        function desiredValue(el) {
            const type = (el.type || '').toLowerCase();
            const ctx = ctxFor(el);
            const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
            const isoDate = nextWeek.toISOString().slice(0, 10);
            if (ctx.includes('captcha') || ctx.includes('recaptcha') || ctx.includes('honeypot')) return null;
            if (ctx.includes('first') && ctx.includes('name')) return firstName;
            if (ctx.includes('last') && ctx.includes('name')) return lastName;
            if (ctx.includes('full name') || (ctx.includes('name') && !ctx.includes('email') && !ctx.includes('company'))) return fullName;
            if (type === 'email' || ctx.includes('email')) return email;
            if (type === 'tel' || ctx.includes('phone') || ctx.includes('telephone') || ctx.includes('mobile')) return phone;
            if (type === 'number' && (ctx.includes('phone') || ctx.includes('tel'))) return phoneDigits;
            if (ctx.includes('company') || ctx.includes('organization') || ctx.includes('business')) return company || fullName;
            if (ctx.includes('subject')) return subject || 'Mitigation partnership inquiry';
            if (ctx.includes('city')) return city;
            if (ctx.includes('state') || ctx.includes('province')) return state;
            if (ctx.includes('zip') || ctx.includes('postal')) return postalCode;
            if (ctx.includes('address') || ctx.includes('street') || ctx.includes('service location')) return fullAddress || address;
            if (ctx.includes('service') || ctx.includes('request') || ctx.includes('type')) return 'Mitigation partnership inquiry';
            if (type === 'date' || ctx.includes('date')) return type === 'date' ? isoDate : 'Next week';
            if (type === 'time') return '09:00';
            if (ctx.includes('time') || ctx.includes('timeline') || ctx.includes('preferred')) return 'Next week';
            if (el.tagName === 'TEXTAREA' || ctx.includes('message') || ctx.includes('comment') ||
                ctx.includes('question') || ctx.includes('description') || ctx.includes('details') ||
                ctx.includes('issue') || ctx.includes('how can we help')) return message;
            return 'Business partnership inquiry';
        }
        function setValue(el, val) {
            if (!el || val == null || val === '') return false;
            const type = (el.type || '').toLowerCase();
            if (type === 'number') val = String(val).replace(/\D/g, '');
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (setter) setter.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
            filled++;
            repairLabels.push((labelFor(el) || el.name || el.id || el.tagName).slice(0, 80));
            return true;
        }
        function chooseSelect(el) {
            const options = Array.from(el.options || []).filter(o =>
                !o.disabled && o.value && !/select|choose|please|--/.test((o.textContent || '').trim().toLowerCase())
            );
            if (!options.length) return false;
            const ctx = ctxFor(el);
            let option = null;
            option = options.find(o => /as soon|soon|next week|morning|flexible|other|general|inquiry|contact|business|service|consultation|referral/i.test(o.textContent || ''));
            if (!option && ctx.includes('state')) option = options.find(o => /texas|tx/i.test(o.textContent || ''));
            if (!option) option = options[0];
            el.value = option.value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            filled++;
            repairLabels.push((labelFor(el) || el.name || 'select').slice(0, 80));
            return true;
        }

        const controls = Array.from(document.querySelectorAll('input, textarea, select')).filter(visible);
        for (const el of controls) {
            const type = (el.type || '').toLowerCase();
            if (['submit', 'button', 'image', 'reset', 'file', 'password', 'hidden'].includes(type)) continue;
            const invalid = (() => { try { return el.willValidate && !el.checkValidity(); } catch(e) { return false; } })();
            const emptyRequired = isRequiredish(el) && !String(el.value || '').trim();
            const ariaInvalid = el.getAttribute('aria-invalid') === 'true';
            if (!invalid && !emptyRequired && !ariaInvalid) continue;

            if (el.tagName === 'SELECT') {
                chooseSelect(el);
            } else if (type === 'radio') {
                const group = controls.filter(x => x.type === 'radio' && x.name === el.name);
                const choice = group.find(x => /other|general|yes|no|private|service/i.test(`${x.value || ''} ${labelFor(x)}`)) || group[0];
                if (choice && !choice.checked) {
                    choice.checked = true;
                    choice.dispatchEvent(new Event('change', { bubbles: true }));
                    filled++;
                    repairLabels.push((labelFor(choice) || choice.name || 'radio').slice(0, 80));
                }
            } else if (type === 'checkbox') {
                if (!el.checked && /agree|consent|message|sms|email|terms|privacy/i.test(ctxFor(el))) {
                    el.checked = true;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    filled++;
                    repairLabels.push((labelFor(el) || el.name || 'checkbox').slice(0, 80));
                }
            } else {
                setValue(el, desiredValue(el));
            }
        }

        // Some frameworks do not expose willValidate. Fill any still-empty visible
        // required-looking fields inside active forms as a final pass.
        for (const el of controls) {
            const type = (el.type || '').toLowerCase();
            if (['submit', 'button', 'image', 'reset', 'file', 'password', 'hidden', 'radio', 'checkbox'].includes(type)) continue;
            if (String(el.value || '').trim()) continue;
            if (!isRequiredish(el)) continue;
            if (el.tagName === 'SELECT') chooseSelect(el);
            else setValue(el, desiredValue(el));
        }

        return { filled, labels: Array.from(new Set(repairLabels)).slice(0, 12) };
    }""", [name, email, phone, company, subject, message, address, city, state, postal_code])


async def broad_prefill_visible_controls(page, name, email, phone, company, subject, message,
                                         address, city, state, postal_code):
    """Fill visible form controls when normal field mapping found no usable fields."""
    return await page.evaluate(r"""(args) => {
        const [fullName, email, phone, company, subject, message, address, city, state, postalCode] = args;
        const [firstName, ...lastParts] = String(fullName || '').split(/\s+/);
        const lastName = lastParts.join(' ') || '';
        const phoneDigits = String(phone || '').replace(/\D/g, '');
        const fullAddress = [address, city, state, postalCode].filter(Boolean).join(', ');
        const labels = [];
        let filled = 0;

        function visible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && r.width > 5 && r.height > 5;
        }
        function labelFor(el) {
            const labelEl = el.closest('label') || (el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null);
            const nearby = el.closest('.gfield, .form-field, .field, .form-group, .wpcf7-form-control-wrap, li, p, div');
            return `${labelEl?.textContent || ''} ${el.previousElementSibling?.textContent || ''} ${nearby?.textContent || ''}`.replace(/\s+/g, ' ').trim();
        }
        function ctxFor(el) {
            return `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${labelFor(el)}`.toLowerCase();
        }
        function ignored(el) {
            const ctx = ctxFor(el);
            const type = (el.type || '').toLowerCase();
            return ['submit','button','image','reset','file','password','hidden'].includes(type) ||
                /search|login|password|username|captcha|recaptcha|honeypot|payment|credit card|card number|checkout|cart/.test(ctx);
        }
        function valueFor(el) {
            const type = (el.type || '').toLowerCase();
            const ctx = ctxFor(el);
            if (ctx.includes('first') && ctx.includes('name')) return firstName;
            if (ctx.includes('last') && ctx.includes('name')) return lastName || fullName;
            if (ctx.includes('full name') || (ctx.includes('name') && !ctx.includes('email') && !ctx.includes('company'))) return fullName;
            if (type === 'email' || ctx.includes('email')) return email;
            if (type === 'tel' || ctx.includes('phone') || ctx.includes('telephone') || ctx.includes('mobile')) return phone;
            if (type === 'number' && (ctx.includes('phone') || ctx.includes('tel'))) return phoneDigits;
            if (ctx.includes('company') || ctx.includes('organization') || ctx.includes('business')) return company || fullName;
            if (ctx.includes('subject')) return subject || 'Mitigation partnership inquiry';
            if (ctx.includes('city')) return city;
            if (ctx.includes('state') || ctx.includes('province')) return state;
            if (ctx.includes('zip') || ctx.includes('postal')) return postalCode;
            if (ctx.includes('address') || ctx.includes('street') || ctx.includes('location')) return fullAddress || address;
            if (el.tagName === 'TEXTAREA' || ctx.includes('message') || ctx.includes('comment') || ctx.includes('question') ||
                ctx.includes('description') || ctx.includes('details') || ctx.includes('how can we help')) return message;
            if (ctx.includes('service') || ctx.includes('request') || ctx.includes('type')) return 'Mitigation partnership inquiry';
            if (el.required || el.getAttribute('aria-required') === 'true' || ctx.includes('*') || ctx.includes('required')) return 'Business partnership inquiry';
            return null;
        }
        function setValue(el, val) {
            if (!val) return false;
            const type = (el.type || '').toLowerCase();
            if (type === 'number') val = String(val).replace(/\D/g, '');
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (setter) setter.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
            filled++;
            labels.push((labelFor(el) || el.name || el.id || el.tagName).slice(0, 80));
            return true;
        }
        function chooseSelect(el) {
            const ctx = ctxFor(el);
            const options = Array.from(el.options || []).filter(o => {
                const text = (o.textContent || '').trim().toLowerCase();
                const value = String(o.value || '').trim().toLowerCase();
                return !o.disabled && value && !/^(select|choose|please|interested in|service category|service category needed|--|—)/.test(text);
            });
            if (!options.length) return false;
            let option = null;
            if (ctx.includes('state')) option = options.find(o => /^(tx|texas)$/i.test((o.textContent || '').trim()) || /^(tx|texas)$/i.test(String(o.value || '').trim()));
            if (!option) option = options.find(o => /other|general|inquiry|business|consultation|service|referral|contact/i.test(o.textContent || ''));
            if (!option) option = options[0];
            el.value = option.value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
            filled++;
            labels.push((labelFor(el) || el.name || 'select').slice(0, 80));
            return true;
        }

        const forms = Array.from(document.querySelectorAll('form'));
        const roots = forms.length ? forms : [document.body];
        const scored = roots.map(root => {
            const text = `${root.innerText || ''} ${root.id || ''} ${root.className || ''}`.toLowerCase();
            const controls = Array.from(root.querySelectorAll('input, textarea, select')).filter(el => visible(el) && !ignored(el));
            let score = controls.length;
            if (root.querySelector('textarea')) score += 5;
            if (/contact|message|quote|estimate|request|service|appointment|inquiry|get in touch/.test(text)) score += 8;
            if (/search|login|checkout|cart|payment/.test(text)) score -= 20;
            return { root, controls, score };
        }).sort((a, b) => b.score - a.score);
        const controls = scored[0]?.controls || [];
        for (const el of controls) {
            const type = (el.type || '').toLowerCase();
            if (el.tagName === 'SELECT') {
                chooseSelect(el);
            } else if (type === 'radio') {
                const group = controls.filter(x => x.type === 'radio' && x.name === el.name);
                if (!group.some(x => x.checked)) {
                    const choice = group.find(x => /other|general|yes|private|service/i.test(`${x.value || ''} ${labelFor(x)}`)) || group[0];
                    if (choice) {
                        choice.checked = true;
                        choice.dispatchEvent(new Event('change', { bubbles: true }));
                        filled++;
                        labels.push((labelFor(choice) || choice.name || 'radio').slice(0, 80));
                    }
                }
            } else if (type === 'checkbox') {
                if (!el.checked && /agree|consent|message|sms|email|terms|privacy|required/i.test(ctxFor(el))) {
                    el.checked = true;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    filled++;
                    labels.push((labelFor(el) || el.name || 'checkbox').slice(0, 80));
                }
            } else if (!String(el.value || '').trim()) {
                setValue(el, valueFor(el));
            }
        }
        return { filled, labels: Array.from(new Set(labels)).slice(0, 12) };
    }""", [name, email, phone, company, subject, message, address, city, state, postal_code])


async def quick_verify_submission_state(page):
    """Compact verification used after validation repair resubmits."""
    return await page.evaluate(r"""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        function visible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && r.width > 5 && r.height > 5;
        }
        function ignoredControl(el) {
            const formText = (el.form?.innerText || '').toLowerCase();
            const ctx = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${formText}`.toLowerCase();
            if (ctx.includes('honeypot') || ctx.includes('captcha') || ctx.includes('recaptcha')) return true;
            if (ctx.includes('password') || formText.includes('login')) return true;
            if (/search|site-search|wp-block-search|search the site/.test(ctx) && !/message|comment|contact|quote|estimate|request/.test(formText)) return true;
            return false;
        }
        const invalid = Array.from(document.querySelectorAll('input, textarea, select')).find(el => {
            try { return visible(el) && !ignoredControl(el) && el.willValidate && !el.checkValidity(); } catch(e) { return false; }
        });
        if (invalid) {
            const labelEl = invalid.closest('label') || (invalid.id ? document.querySelector(`label[for="${CSS.escape(invalid.id)}"]`) : null);
            const label = (labelEl?.textContent || invalid.placeholder || invalid.name || invalid.id || invalid.validationMessage || 'invalid required field').trim();
            return { confirmed: false, type: 'browser_validation', match: label.substring(0, 120) };
        }
        const successPatterns = [
            'thank you', 'thanks for', 'message sent', 'submission received',
            'successfully submitted', 'we will get back', 'we\'ll get back',
            'form submitted', 'request received', 'inquiry received',
            'been received', 'reach out soon', 'contact you soon',
            'message has been', 'form has been', 'successfully sent',
            'we have received your inquiry', 'received your inquiry', 'success!'
        ];
        for (const pat of successPatterns) {
            if (body.includes(pat)) return { confirmed: true, type: 'success_text', match: pat };
        }
        const errorPatterns = [
            'this field needs to be filled', 'please fill', 'required field',
            'invalid', 'please enter a valid', 'is required', 'fill in',
            'oops', 'something went wrong', 'error', 'failed',
            'problem with your submission', 'review the fields below',
            'there was a problem'
        ];
        for (const pat of errorPatterns) {
            if (body.includes(pat)) return { confirmed: false, type: 'validation_error', match: pat };
        }
        return { confirmed: null, type: 'unknown', match: 'no confirmation or error detected after repair' };
    }""")


async def fill_and_submit(page, name, email, message, subject="", phone="", company="",
                          address="", city="", state="", postal_code="",
                          dry_run=False, review_before_submit=False, review_path=None):
    """Fill form fields and submit. Intelligently handles required fields."""
    form_info = await detect_form_fields(page)
    captcha_info = await detect_captcha_type(page)

    total_forms = form_info.get('total_forms', '?')
    form_idx = form_info.get('form_index', '?')
    print(f"    [FORM] Has form: {form_info.get('has_form')} | Using form {form_idx}/{total_forms} | CAPTCHA: {captcha_info.get('type')}")

    if not form_info.get("has_form"):
        if form_info.get("has_mailto"):
            return {"status": "mailto_only", "email": form_info.get("mailto_email"),
                    "note": "No form — only mailto link found"}
        return {"status": "no_form", "note": "No contact form found"}

    fields = form_info.get("fields", {})

    # Show all detected fields with required status
    for fname, fdata in fields.items():
        if fname == "submit":
            continue
        req = "REQUIRED" if fdata.get("required") else "optional"
        extra = ""
        if fdata.get("type") == "select":
            opts = fdata.get("options", [])
            extra = f" [{len(opts)} options: {', '.join(o['text'][:20] for o in opts[:4])}...]"
        print(f"    [FORM]   {fname}: {req}{extra}")

    filled = []
    missing_required = []

    # Build ordered field values (matches visual tab order on most forms)
    fill_order = []
    if fields.get("first_name") and fields.get("last_name"):
        parts = name.split(" ", 1)
        fill_order.append(("first_name", parts[0]))
        fill_order.append(("last_name", parts[1] if len(parts) > 1 else ""))
    elif fields.get("first_name"):
        # Some forms label one combined field as "First/Last name".
        # If there is no separate last-name field, use the full name.
        fill_order.append(("first_name", name))
    elif fields.get("last_name"):
        parts = name.split(" ", 1)
        fill_order.append(("last_name", parts[1] if len(parts) > 1 else name))
    elif fields.get("name"):
        fill_order.append(("name", name))
    if fields.get("email"):
        fill_order.append(("email", email))
    if fields.get("phone"):
        fill_order.append(("phone", phone))
    if fields.get("subject"):
        fill_order.append(("subject", subject or "Business Inquiry"))
    if fields.get("company"):
        fill_order.append(("company", company))
    if fields.get("address"):
        full_address = ", ".join(part for part in [address, city, state, postal_code] if part)
        fill_order.append(("address", full_address or address))
    if fields.get("city"):
        fill_order.append(("city", city))
    if fields.get("state"):
        fill_order.append(("state", state))
    if fields.get("postal_code"):
        fill_order.append(("postal_code", postal_code))
    if fields.get("space_number"):
        fill_order.append(("space_number", "1"))
    if fields.get("message"):
        fill_order.append(("message", message))
    for fname, fdata in fields.items():
        if fname.startswith("_text_"):
            fill_order.append((fname, generic_required_text_value(fdata.get("label", ""), message)))

    if not fill_order:
        try:
            broad = await broad_prefill_visible_controls(
                page, name, email, phone, company, subject, message,
                address, city, state, postal_code
            )
            if broad.get("filled"):
                for label in broad.get("labels", []):
                    filled.append(f"broad:{label}")
                print(f"    [FORM] Broad prefill filled {broad.get('filled')} visible control(s)")
                await page.wait_for_timeout(800)
            else:
                return {
                    "status": "no_fillable_fields",
                    "fields_filled": [],
                    "captcha_type": captcha_info.get("type", "none"),
                    "missing_required": [],
                    "note": "Detected a form container, but no fillable outreach fields were mapped. Submission skipped."
                }
        except Exception as e:
            return {
                "status": "no_fillable_fields",
                "fields_filled": [],
                "captcha_type": captcha_info.get("type", "none"),
                "missing_required": [],
                "note": f"Detected a form container, but no fillable outreach fields were mapped. Broad fallback failed: {str(e)[:120]}"
            }

    # Check for missing required fields
    fill_names = {n for n, _ in fill_order}
    for fname, fdata in fields.items():
        if fname == "submit":
            continue
        if fdata.get("required") and fname not in fill_names and not fname.startswith(("_select_", "_radio_", "_checkbox_")):
            missing_required.append(fname)

    # React/Wix/custom forms: use the native browser value setter first so fields
    # do not clear each other during framework re-renders.
    for fname, value in fill_order:
        if not value:
            if fields.get(fname, {}).get("required"):
                missing_required.append(fname)
            continue

        sel = fields[fname]["selector"]
        try:
            success = False
            if fname == "address":
                success = await fill_address_with_autocomplete(page, sel, value)
            if not success:
                success = await set_field_value(page, sel, value)
            if not success and fname in ("email", "phone"):
                success = await type_field_value(page, sel, value)
            if not success:
                await page.fill(sel, value, timeout=5000)
            filled.append(fname)
            print(f"    [FILL] {fname}: set ({len(value)} chars)")
            await page.wait_for_timeout(1200)
        except Exception as e:
            print(f"    [WARN] Could not fill {fname}: {str(e)[:100]}")

    # Handle select dropdowns (unknown fields like "Case Type", "How did you hear")
    for fname, fdata in fields.items():
        if fdata.get("type") != "select":
            continue
        options = fdata.get("options", [])
        label = fdata.get("label", fname)
        if not options:
            continue

        def is_placeholder_option(opt):
            text = str(opt.get("text", "")).strip().lower()
            value = str(opt.get("value", "")).strip().lower()
            if not text and not value:
                return True
            placeholder_prefixes = (
                "select", "choose", "please", "--", "—", "-",
                "interested in", "service category", "service category needed", "pick one",
                "how can we help", "what service"
            )
            return text.startswith(placeholder_prefixes) or value.startswith(placeholder_prefixes)

        valid_options = [opt for opt in options if not is_placeholder_option(opt)]
        if not valid_options:
            valid_options = options

        # Smart selection: pick the most generic/relevant option
        chosen = None
        if "state" in (label or "").lower():
            for opt in valid_options:
                text = opt["text"].lower()
                value = str(opt.get("value", "")).lower()
                if text in ("tx", "texas") or value in ("tx", "texas"):
                    chosen = opt
                    break
        for opt in valid_options:
            if chosen:
                break
            text = opt["text"].lower()
            # Prefer generic options
            if any(kw in text for kw in ["other", "general", "inquiry", "business", "consultation", "referral", "website"]):
                chosen = opt
                break
        if not chosen:
            # Pick the first non-empty option (skip "Select..." / "Choose..." placeholders)
            for opt in valid_options:
                if not opt["text"].lower().startswith(("select", "choose", "please", "--", "—")):
                    chosen = opt
                    break
        if not chosen and valid_options:
            chosen = valid_options[0]

        if chosen:
            try:
                selected = await page.evaluate("""(args) => {
                    const [selector, value] = args;
                    const el = document.querySelector(selector);
                    if (!el || el.tagName !== 'SELECT') return false;
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                    return el.value === value;
                }""", [fdata["selector"], chosen["value"]])
                if not selected:
                    await page.select_option(fdata["selector"], chosen["value"], timeout=5000)
                filled.append(f"{label}={chosen['text']}")
                print(f"    [FORM] Selected '{chosen['text']}' for dropdown '{label}'")
                await page.wait_for_timeout(300)
            except Exception as e:
                print(f"    [WARN] Could not select {label}: {str(e)[:100]}")
                if fdata.get("required"):
                    missing_required.append(label)

    # Handle radio/checkbox groups. Prefer "private lot" for seller cash-offer forms
    # and check consent boxes when present.
    for fname, fdata in fields.items():
        if fdata.get("type") not in ("radio", "checkbox"):
            continue
        choices = fdata.get("choices", [])
        if not choices:
            continue

        chosen = choices[0]
        if fdata.get("type") == "radio":
            for choice in choices:
                text = f"{choice.get('label', '')} {choice.get('value', '')}".lower()
                if "private" in text or "lot" in text:
                    chosen = choice
                    break
        elif fdata.get("type") == "checkbox":
            for choice in choices:
                text = f"{choice.get('label', '')} {choice.get('value', '')}".lower()
                if any(kw in text for kw in ["consent", "agree", "sms", "email", "message"]):
                    chosen = choice
                    break

        try:
            await page.locator(chosen["selector"]).first.check(timeout=5000, force=True)
            filled.append(f"{fdata.get('label', fname)}={chosen.get('label') or chosen.get('value')}")
            print(f"    [FORM] Checked {fdata.get('type')} '{chosen.get('label') or chosen.get('value')}'")
            await page.wait_for_timeout(300)
        except Exception as e:
            print(f"    [WARN] Could not check {fname}: {str(e)[:100]}")
            if fdata.get("required"):
                missing_required.append(fdata.get("label", fname))

    try:
        fallback_count = await fill_common_form_fallbacks(page, name, email, phone, address, city, state, postal_code)
        if fallback_count:
            print(f"    [FORM] Fallback-filled {fallback_count} duplicate/hidden field(s)")
    except Exception as e:
        print(f"    [WARN] Common fallback fill failed: {str(e)[:100]}")

    result = {
        "status": "filled",
        "fields_filled": filled,
        "captcha_type": captcha_info.get("type", "none"),
        "missing_required": missing_required,
    }

    # Check if we're missing any required fields
    if missing_required and not filled:
        print(f"    [FORM] MISSING REQUIRED FIELDS: {', '.join(missing_required)}")
        result["status"] = "missing_required"
        result["note"] = f"Cannot submit — missing required fields: {', '.join(missing_required)}"
        return result
    if missing_required:
        print(f"    [FORM] Required fields were flagged, but {len(filled)} field action(s) succeeded; submitting to trigger page-level validation.")

    if dry_run:
        result["status"] = "dry_run"
        return result

    if review_before_submit:
        if review_path:
            await page.screenshot(path=str(review_path), full_page=False)
            result["review_screenshot"] = str(review_path)
        result["status"] = "review_pending"
        result["note"] = "Form filled and screenshot saved; not submitted because review-before-submit is enabled"
        return result

    # Solve CAPTCHA if present
    if captcha_info.get("type") != "none":
        if captcha_info.get("type", "").startswith("recaptcha") and not captcha_info.get("site_key"):
            print(f"    [CAPTCHA] {captcha_info.get('type')} detected without exposed site key; trying native site submit")
        else:
            print(f"    [CAPTCHA] Solving {captcha_info['type']}...")
            solved = await solve_captcha(page, captcha_info)
            if not solved:
                result["status"] = "captcha_failed"
                return result
            print(f"    [CAPTCHA] Solved!")

    # Submit
    if fields.get("submit"):
        try:
            sel = fields["submit"]["selector"]
            clicked = await click_visible_submit(page, sel)
            if not clicked:
                # Use .last to pick the visible one if multiple match
                btn = page.locator(sel).last
                await btn.scroll_into_view_if_needed(timeout=5000)
                await btn.click(timeout=10000)
            await page.wait_for_timeout(9000)
        except Exception as e:
            # Fallback: press Enter on the form
            try:
                clicked = await click_visible_submit(page)
                if not clicked:
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(9000)
            except Exception:
                result["status"] = "submit_error"
                result["note"] = str(e)[:200]
                return result
    else:
        try:
            clicked = await click_visible_submit(page)
            if not clicked:
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(9000)
        except Exception:
            result["status"] = "no_submit_button"
            return result

    # Verify submission — look for confirmation message or validation errors
    try:
        verification = await page.evaluate(r"""() => {
        const body = document.body.innerText.toLowerCase();
        const html = document.body.innerHTML.toLowerCase();
        function visible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && r.width > 5 && r.height > 5;
        }
        function ignoredControl(el) {
            const formText = (el.form?.innerText || '').toLowerCase();
            const ctx = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${formText}`.toLowerCase();
            if (ctx.includes('honeypot') || ctx.includes('captcha') || ctx.includes('recaptcha')) return true;
            if (ctx.includes('password') || formText.includes('login')) return true;
            if (/search|site-search|wp-block-search|search the site/.test(ctx) && !/message|comment|contact|quote|estimate|request/.test(formText)) return true;
            return false;
        }

        if (
            body.includes('step 2 of 2') ||
            body.includes('a few more questions') ||
            body.includes('learn more about your property') ||
            body.includes('excellent! now')
        ) {
            return { confirmed: null, type: 'multi_step_next', match: 'form advanced to next step' };
        }

        // Check for success confirmation messages
        const invalid = Array.from(document.querySelectorAll('input, textarea, select')).find(el => {
            try { return visible(el) && !ignoredControl(el) && el.willValidate && !el.checkValidity(); } catch(e) { return false; }
        });
        if (invalid) {
            const labelEl = invalid.closest('label') || document.querySelector(`label[for="${invalid.id}"]`);
            const label = (labelEl?.textContent || invalid.placeholder || invalid.name || invalid.id || invalid.validationMessage || 'invalid required field').trim();
            return { confirmed: false, type: 'browser_validation', match: label.substring(0, 120) };
        }

        const captchaSignals = ['enter the code from the image', 'security code', 'verification code', 'captcha code'];
        for (const pat of captchaSignals) {
            if (body.includes(pat)) {
                return { confirmed: false, type: 'custom_captcha_or_verification', match: pat };
            }
        }

        const visibleCaptcha = Array.from(document.querySelectorAll(
            '.g-recaptcha, .h-captcha, .cf-turnstile, iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="turnstile"]'
        )).some(el => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 20 && rect.height > 10;
        });
        if (visibleCaptcha && !body.includes('thank you')) {
            return { confirmed: false, type: 'custom_captcha_or_verification', match: 'visible captcha present after submit' };
        }

        const successPatterns = [
            'thank you', 'thanks for', 'message sent', 'submission received',
            'successfully submitted', 'we will get back', 'we\'ll get back',
            'form submitted', 'request received', 'inquiry received',
            'been received', 'reach out soon', 'contact you soon',
            'message has been', 'form has been', 'successfully sent',
            'we have received your inquiry', 'received your inquiry',
            'success!',
            'danke', 'nachricht wurde', 'erfolgreich'
        ];
        for (const pat of successPatterns) {
            if (body.includes(pat)) {
                return { confirmed: true, type: 'success_text', match: pat };
            }
        }

        // Check for Webflow-specific success state (w-form-done visible)
        const wfDone = document.querySelector('.w-form-done');
        if (wfDone) {
            const style = window.getComputedStyle(wfDone);
            if (style.display !== 'none' && style.opacity !== '0') {
                return { confirmed: true, type: 'webflow_done', match: wfDone.textContent.trim().substring(0, 80) };
            }
        }

        // Check for validation errors still visible
        const errorPatterns = [
            'this field needs to be filled', 'please fill', 'required field',
            'invalid', 'please enter a valid', 'is required', 'fill in',
            'oops', 'something went wrong', 'error', 'failed',
            'problem with your submission', 'review the fields below',
            'there was a problem'
        ];
        for (const pat of errorPatterns) {
            if (body.includes(pat)) {
                return { confirmed: false, type: 'validation_error', match: pat };
            }
        }

        // Check for Webflow error state (w-form-fail visible)
        const wfFail = document.querySelector('.w-form-fail');
        if (wfFail) {
            const style = window.getComputedStyle(wfFail);
            if (style.display !== 'none' && style.opacity !== '0') {
                return { confirmed: false, type: 'webflow_fail', match: wfFail.textContent.trim().substring(0, 80) };
            }
        }

        // No clear signal either way
        return { confirmed: null, type: 'unknown', match: 'no confirmation or error detected' };
        }""")
    except Exception as e:
        result["status"] = "submitted_unconfirmed"
        result["confirmation"] = {
            "confirmed": None,
            "type": "navigation_after_submit",
            "match": str(e)[:160],
        }
        result["note"] = "Submitted and page navigated before confirmation could be checked — verify manually"
        return result

    print(f"    [VERIFY] {verification.get('type')}: \"{verification.get('match', '')}\"")

    if verification.get("type") == "custom_captcha_or_verification":
        try:
            delayed_captcha = await detect_captcha_type(page)
            result["delayed_captcha_type"] = delayed_captcha.get("type", "none")
            if delayed_captcha.get("type") != "none":
                print(f"    [CAPTCHA-LATE] Solving delayed {delayed_captcha.get('type')}...")
                solved = await solve_captcha(page, delayed_captcha)
                if solved:
                    clicked = await click_visible_submit(page, fields.get("submit", {}).get("selector"))
                    if not clicked:
                        await page.keyboard.press("Enter")
                    await page.wait_for_timeout(9000)
                    verification = await quick_verify_submission_state(page)
                    print(f"    [VERIFY-CAPTCHA] {verification.get('type')}: \"{verification.get('match', '')}\"")
                else:
                    result["status"] = "captcha_failed"
                    result["confirmation"] = verification
                    result["note"] = f"Delayed CAPTCHA could not be solved: {verification.get('match', '')}"
                    return result
        except Exception as e:
            result["delayed_captcha_error"] = str(e)[:200]

    if verification.get("type") == "multi_step_next":
        print("    [FORM] First step accepted; completing follow-up step...")
        try:
            followup = await fill_followup_step_and_submit(page, name, email, phone, address, city, state, postal_code)
            result["followup"] = followup
            fields_filled = followup.get("fields_filled", 0)
            follow_verification = followup.get("verification", {})
            print(f"    [VERIFY-2] {follow_verification.get('type')}: \"{follow_verification.get('match', '')}\" | follow-up fields: {fields_filled}")
            verification = follow_verification
        except Exception as e:
            result["followup"] = {"error": str(e)[:200]}
            result["status"] = "submitted_unconfirmed"
            result["confirmation"] = verification
            result["note"] = "First step accepted; follow-up step could not be completed automatically"
            return result

    if verification.get("confirmed") is True:
        result["status"] = "confirmed"
        result["confirmation"] = verification
    elif verification.get("confirmed") is False:
        if verification.get("type") in ("browser_validation", "validation_error", "webflow_fail"):
            try:
                repairs = []
                for repair_attempt in range(1, 4):
                    repair = await repair_validation_fields(
                        page, name, email, phone, company, subject, message,
                        address, city, state, postal_code
                    )
                    repair["attempt"] = repair_attempt
                    repairs.append(repair)
                    if repair.get("filled", 0) <= 0:
                        break

                    print(f"    [REPAIR-{repair_attempt}] Filled {repair.get('filled')} validation field(s): {', '.join(repair.get('labels', [])[:4])}")
                    clicked = await click_visible_submit(page, fields.get("submit", {}).get("selector"))
                    if not clicked:
                        await page.keyboard.press("Enter")
                    await page.wait_for_timeout(8000)
                    repaired_verification = await quick_verify_submission_state(page)
                    print(f"    [VERIFY-REPAIR-{repair_attempt}] {repaired_verification.get('type')}: \"{repaired_verification.get('match', '')}\"")
                    verification = repaired_verification
                    if verification.get("confirmed") is not False:
                        break
                    if verification.get("type") not in ("browser_validation", "validation_error", "webflow_fail"):
                        break
                result["validation_repair"] = repairs
            except Exception as e:
                result["validation_repair"] = {"error": str(e)[:200]}

        if verification.get("confirmed") is True:
            result["status"] = "confirmed"
            result["confirmation"] = verification
            return result
        if verification.get("confirmed") is None:
            result["status"] = "submitted_unconfirmed"
            result["confirmation"] = verification
            result["note"] = "Submitted after validation repair but no confirmation message detected — verify manually"
            return result

        result["status"] = "failed_validation"
        result["confirmation"] = verification
        result["note"] = f"Form validation failed: {verification.get('match', 'unknown error')}"
    else:
        result["status"] = "submitted_unconfirmed"
        result["confirmation"] = verification
        result["note"] = "Submitted but no confirmation message detected — verify manually"

    return result


async def process_website(page, website_url, name, email, message, subject="",
                          phone="", company_name="", address="", city="", state="",
                          postal_code="", dry_run=False, review_before_submit=False,
                          prefilter_low_quality_pages=False, min_page_quality_score=10):
    """Navigate to a website, find contact page, fill and submit form."""
    slug = re.sub(r'[^a-z0-9]', '_', company_name.lower())[:30] or "site"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n  {'='*55}")
    print(f"  Company: {company_name or 'N/A'}")
    print(f"  Website: {website_url[:80]}")
    calendar_links = []
    contact_details = {"emails": [], "phones": [], "notes": ""}

    # Navigate to homepage
    try:
        website_url = await goto_with_fallbacks(page, website_url, timeout=30000)
    except Exception as e:
        print(f"  [ERROR] Failed to load: {str(e)[:150]}")
        return {"status": "load_error", "url": website_url, "error": str(e)[:200]}

    try:
        contact_details = merge_contact_details(contact_details, await extract_contact_details(page))
        if contact_details.get("emails") or contact_details.get("phones"):
            print(f"  [CONTACT] Found {len(contact_details.get('emails', []))} email(s), {len(contact_details.get('phones', []))} phone(s)")
    except Exception as e:
        print(f"  [WARN] Contact-detail extraction failed: {str(e)[:120]}")

    try:
        checkout_info = await detect_checkout_or_payment_page(page)
        if checkout_info.get("is_checkout"):
            return {
                "status": "checkout_or_payment_page",
                "url": website_url,
                "note": "Skipped because page appears to be a checkout, domain-sale, cart, or payment flow",
                "checkout_signals": checkout_info.get("signals", []),
                "contact_details": contact_details,
            }
    except Exception as e:
        print(f"  [WARN] Checkout detection failed: {str(e)[:120]}")

    if prefilter_low_quality_pages:
        try:
            quality = await assess_page_quality(page)
            print(f"  [PREFLIGHT] Page quality {quality.get('score')} | {', '.join(quality.get('reasons', [])[:6])}")
            no_contact_surface = quality.get("forms", 0) == 0 and quality.get("contact_links", 0) == 0
            if quality.get("score", 0) < min_page_quality_score and no_contact_surface:
                return {
                    "status": "page_prefilter_rejected",
                    "url": website_url,
                    "note": "Skipped before contact-page probing because homepage looked low quality and exposed no form/contact route",
                    "page_quality": quality,
                    "contact_details": contact_details,
                }
        except Exception as e:
            print(f"  [WARN] Page preflight failed: {str(e)[:120]}")

    try:
        calendar_links = merge_calendar_links(calendar_links, await detect_calendar_links(page))
        if calendar_links:
            print(f"  [CAL] Found {len(calendar_links)} scheduling/calendar link(s)")
    except Exception as e:
        print(f"  [WARN] Calendar link detection failed: {str(e)[:120]}")

    # Find contact page
    try:
        contact_url = await find_contact_page(page, website_url)
    except Exception as e:
        print(f"  [ERROR] Contact page detection failed: {str(e)[:150]}")
        return {
            "status": "detection_error",
            "url": website_url,
            "error": str(e)[:200],
            "calendar_link": calendar_links[0]["href"] if calendar_links else "",
            "calendar_links": calendar_links,
            "contact_details": contact_details,
        }
    if not contact_url:
        return {
            "status": "no_contact_page",
            "url": website_url,
            "note": "Could not find a contact page with a form",
            "calendar_link": calendar_links[0]["href"] if calendar_links else "",
            "calendar_links": calendar_links,
            "contact_details": contact_details,
        }

    # Navigate to contact page if different from current
    if contact_url != page.url:
        try:
            contact_url = await goto_with_fallbacks(page, contact_url, timeout=30000)
        except Exception as e:
            print(f"  [ERROR] Failed to load contact page: {str(e)[:150]}")
            return {
                "status": "load_error",
                "url": contact_url,
                "error": str(e)[:200],
                "calendar_link": calendar_links[0]["href"] if calendar_links else "",
                "calendar_links": calendar_links,
                "contact_details": contact_details,
            }

    try:
        contact_details = merge_contact_details(contact_details, await extract_contact_details(page))
    except Exception as e:
        print(f"  [WARN] Contact-page detail extraction failed: {str(e)[:120]}")

    try:
        checkout_info = await detect_checkout_or_payment_page(page)
        if checkout_info.get("is_checkout"):
            return {
                "status": "checkout_or_payment_page",
                "url": contact_url,
                "note": "Skipped because page appears to be a checkout, domain-sale, cart, or payment flow",
                "checkout_signals": checkout_info.get("signals", []),
                "calendar_link": calendar_links[0]["href"] if calendar_links else "",
                "calendar_links": calendar_links,
                "contact_details": contact_details,
            }
    except Exception as e:
        print(f"  [WARN] Contact-page checkout detection failed: {str(e)[:120]}")

    try:
        before_count = len(calendar_links)
        calendar_links = merge_calendar_links(calendar_links, await detect_calendar_links(page))
        if len(calendar_links) > before_count:
            print(f"  [CAL] Found {len(calendar_links)} total scheduling/calendar link(s)")
    except Exception as e:
        print(f"  [WARN] Contact-page calendar detection failed: {str(e)[:120]}")

    # Scroll to form
    await page.evaluate("""() => {
        const form = document.querySelector('form') || document.querySelector('textarea');
        if (form) form.scrollIntoView({ behavior: 'smooth', block: 'center' });
        else window.scrollTo(0, document.body.scrollHeight * 0.4);
    }""")
    await page.wait_for_timeout(1500)

    # Screenshot before
    before_path = SCREENSHOT_DIR / f"{slug}_{timestamp}_before.png"
    try:
        await page.screenshot(path=str(before_path), full_page=False, timeout=10000)
    except Exception as e:
        print(f"  [WARN] Before screenshot failed: {str(e)[:120]}")
        before_path = ""
    review_path = REVIEW_SCREENSHOT_DIR / f"{slug}_{timestamp}_filled_before_submit.png"

    # Fill and submit
    result = await fill_and_submit(
        page, name, email, message, subject, phone,
        company=company_name,
        address=address,
        city=city,
        state=state,
        postal_code=postal_code,
        dry_run=dry_run,
        review_before_submit=review_before_submit,
        review_path=review_path,
    )

    # Screenshot after
    after_path = SCREENSHOT_DIR / f"{slug}_{timestamp}_after.png"
    try:
        await page.screenshot(path=str(after_path), full_page=False, timeout=10000)
    except Exception:
        after_path = ""

    result["url"] = website_url
    result["contact_url"] = contact_url
    result["company_name"] = company_name
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    result["screenshot_before"] = str(before_path) if before_path else ""
    result["screenshot_after"] = str(after_path) if after_path else ""
    result["calendar_link"] = calendar_links[0]["href"] if calendar_links else ""
    result["calendar_links"] = calendar_links
    result["contact_details"] = contact_details

    icon = {"confirmed": "OK", "submitted": "OK", "submitted_enter": "OK",
            "submitted_unconfirmed": "??", "dry_run": "DRY",
            "review_pending": "REV",
            "mailto_only": "MAIL", "no_form": "SKIP", "captcha_failed": "CAP",
            "load_error": "ERR", "submit_error": "ERR", "no_contact_page": "SKIP",
            "failed_validation": "FAIL", "missing_required": "MISS",
            "page_prefilter_rejected": "FILT", "lead_prefilter_rejected": "FILT"
            }.get(result["status"], "???")

    print(f"  [{icon}] {result['status']} | Fields: {', '.join(result.get('fields_filled', []))}")
    if result.get("note"):
        print(f"       {result['note']}")

    return result


async def main():
    parser = argparse.ArgumentParser(description="Plumbing/HVAC website form submission via Playwright + CapSolver")
    parser.add_argument("--url", help="Single website URL")
    parser.add_argument("--name", default=DEFAULT_SENDER_NAME, help="Sender name")
    parser.add_argument("--email", default=DEFAULT_SENDER_EMAIL, help="Sender email")
    parser.add_argument("--subject", default="", help="Subject (if form has one)")
    parser.add_argument("--phone", default=DEFAULT_SENDER_PHONE, help="Sender phone number (if form has one)")
    parser.add_argument("--sender-address", default="", help="Sender/service address if form asks for address")
    parser.add_argument("--sender-city", default="", help="Sender/service city if form asks for city")
    parser.add_argument("--sender-state", default="", help="Sender/service state if form asks for state")
    parser.add_argument("--sender-postal-code", default="", help="Sender/service ZIP/postal code if form asks for it")
    parser.add_argument("--message", default="", help="Message body")
    parser.add_argument("--exact-mobile-home-template", action="store_true",
                        help="Use the exact mobile-home case-study template, changing only the first name when available")
    parser.add_argument("--exact-charley-hayden-template", action="store_true",
                        help="Use Charley Hayden's exact Greater Houston mitigation partnership template, changing only the company name")
    parser.add_argument("--exact-vincent-template", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--charley-round2-template", action="store_true",
                        help="Use Charley Hayden's round-2 message (round-1 wording + local + in-person coffee), changing only the company name")
    parser.add_argument("--company", default="", help="Company name for the target")
    parser.add_argument("--target-company", default="", help="Alias for --company")
    parser.add_argument("--location", default="", help="Target location, e.g. Sugar Land, TX")
    parser.add_argument("--niche", default="", help="Target niche, e.g. Plumber or HVAC contractor")
    parser.add_argument("--notes", default="", help="Optional personalization notes about the target")
    parser.add_argument("--batch", help="Path to CSV or JSON file with leads")
    parser.add_argument("--limit", type=int, default=5, help="Max submissions per run")
    parser.add_argument("--dry-run", action="store_true", help="Fill forms but don't submit")
    parser.add_argument("--review-before-submit", action="store_true",
                        help="Fill forms, save a preview screenshot, and stop before CAPTCHA/submit")
    parser.add_argument("--stop-after-successes", type=int, default=0,
                        help="Stop the batch after this many confirmed/submitted statuses")
    parser.add_argument("--strict-service-filter", action="store_true",
                        help="Skip obvious non-service rows such as supply stores, manufacturers, unions, and directories")
    parser.add_argument("--min-lead-score", type=int, default=20,
                        help="Minimum lead service score when --strict-service-filter is enabled")
    parser.add_argument("--prefilter-low-quality-pages", action="store_true",
                        help="Skip pages that expose no form/contact path and score as low-quality before deeper probing")
    parser.add_argument("--min-page-quality-score", type=int, default=10,
                        help="Minimum page quality score when --prefilter-low-quality-pages is enabled")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between submissions")
    parser.add_argument("--browser-channel", default="chrome",
                        help="Playwright browser channel. Use 'chrome' for Google Chrome or 'chromium' for bundled Chromium.")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly with no visible Chrome window")
    parser.add_argument("--profile-suffix", default="",
                        help="Optional suffix for an isolated browser profile, useful for resumable parallel-safe runs.")
    args = parser.parse_args()

    if not args.url and not args.batch:
        parser.error("Either --url or --batch is required")
    validate_sender_config(args.name, args.email)

    from playwright.async_api import async_playwright

    leads = []
    if args.batch:
        leads = load_leads(args.batch)
        leads = leads[:args.limit]
        print(f"\n  Loaded {len(leads)} leads from {args.batch}")
    elif args.url:
        lead = normalize_lead({
            "website": args.url,
            "company_name": args.target_company or args.company,
            "location": args.location,
            "niche": args.niche,
            "notes": args.notes,
            "message": args.message,
        })
        leads = [lead]

    async with async_playwright() as p:
        profile_name = "browser_profile_website"
        if args.profile_suffix:
            safe_suffix = re.sub(r"[^a-zA-Z0-9_-]+", "_", args.profile_suffix.strip())
            profile_name = f"{profile_name}_{safe_suffix}"
        user_data_dir = str(PROJECT_DIR / ".tmp" / profile_name)
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        launch_kwargs = {
            "headless": args.headless,
            "viewport": {"width": 1280, "height": 900},
            "ignore_https_errors": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            "ignore_default_args": ["--enable-automation"],
        }
        if args.browser_channel and args.browser_channel.lower() != "chromium":
            launch_kwargs["channel"] = args.browser_channel

        context = await p.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        log = load_log()
        results = []

        print(f"\n{'='*60}")
        print(f"  PLUMBING/HVAC WEBSITE SUBMISSION AGENT")
        print(f"  Leads: {len(leads)} | Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
        if args.review_before_submit:
            print(f"  Review mode: filled screenshots only, no submissions")
        print(f"  Sender: {args.name} <{args.email}>")
        print(f"{'='*60}")

        for i, lead in enumerate(leads):
            url = normalize_website(lead.get("website") or lead.get("url", ""))
            company = lead.get("company_name", "")
            msg = lead.get("message", args.message)

            if args.exact_mobile_home_template:
                msg = generate_exact_case_study_message(lead)
            elif args.charley_round2_template:
                msg = generate_charley_round2_message(lead)
            elif args.exact_charley_hayden_template or args.exact_vincent_template:
                msg = generate_exact_charley_hayden_message(lead)

            if not msg:
                msg = generate_partnership_message(lead)

            if not url:
                print(f"\n  [{i+1}/{len(leads)}] SKIP {company} — no URL")
                continue

            if args.strict_service_filter:
                lead_score, lead_reasons = score_service_lead(lead)
                if lead_score < args.min_lead_score:
                    print(f"\n  [{i+1}/{len(leads)}] FILTER {company} - lead score {lead_score} < {args.min_lead_score} ({', '.join(lead_reasons)})")
                    result = {
                        "status": "lead_prefilter_rejected",
                        "url": url,
                        "company_name": company,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "lead_quality_score": lead_score,
                        "lead_quality_reasons": lead_reasons,
                        "note": "Skipped by strict service filter before browser visit",
                    }
                    results.append(result)
                    log.append(result)
                    save_log(log)
                    continue
                print(f"\n  [{i+1}/{len(leads)}] PREFILTER PASS {company} - lead score {lead_score} ({', '.join(lead_reasons[:5])})")

            location_city, location_state = split_location(lead.get("location", ""))
            sender_city = lead_value(lead, "sender_city", "city", default=args.sender_city or location_city)
            sender_state = lead_value(lead, "sender_state", "state", default=args.sender_state or location_state)
            sender_postal_code = lead_value(
                lead, "sender_postal_code", "postal_code", "zip",
                default=args.sender_postal_code or DEFAULT_PROPERTY_POSTAL_CODE
            )
            sender_address = lead_value(lead, "sender_address", default=args.sender_address)
            if not sender_address:
                sender_address = ", ".join(
                    part for part in [
                        DEFAULT_PROPERTY_ADDRESS,
                        sender_city,
                        " ".join(part for part in [sender_state, sender_postal_code] if part),
                    ] if part
                )

            result = await process_website(
                page, url, args.name, args.email, msg,
                subject=lead_value(lead, "subject", default=args.subject),
                phone=lead_value(lead, "sender_phone", default=args.phone),
                company_name=company,
                address=sender_address,
                city=sender_city,
                state=sender_state,
                postal_code=sender_postal_code,
                dry_run=args.dry_run,
                review_before_submit=args.review_before_submit,
                prefilter_low_quality_pages=args.prefilter_low_quality_pages,
                min_page_quality_score=args.min_page_quality_score,
            )
            results.append(result)
            log.append(result)
            save_log(log)

            if args.stop_after_successes:
                successful = sum(
                    1 for r in results
                    if r["status"] in ("confirmed", "submitted", "submitted_enter", "submitted_unconfirmed")
                )
                if successful >= args.stop_after_successes:
                    print(f"    Stop target reached: {successful} successful submissions")
                    break

            if i < len(leads) - 1:
                print(f"    Waiting {args.delay}s...")
                await asyncio.sleep(args.delay)

        await context.close()

    # Summary
    submitted = sum(1 for r in results if r["status"] in ("confirmed", "submitted", "submitted_enter", "submitted_unconfirmed"))
    dry = sum(1 for r in results if r["status"] == "dry_run")
    review = sum(1 for r in results if r["status"] == "review_pending")
    skipped = sum(1 for r in results if r["status"] in (
        "no_form", "mailto_only", "no_contact_page",
        "lead_prefilter_rejected", "page_prefilter_rejected",
        "checkout_or_payment_page",
    ))
    errors = sum(1 for r in results if "error" in r["status"])
    captcha_fail = sum(1 for r in results if r["status"] == "captcha_failed")

    print(f"\n{'='*60}")
    print(f"  WEBSITE OUTREACH COMPLETE")
    print(f"{'='*60}")
    print(f"  Submitted:       {submitted}")
    if dry: print(f"  Dry run:         {dry}")
    if review: print(f"  Review pending:  {review}")
    print(f"  Skipped:         {skipped}")
    print(f"  Errors:          {errors}")
    if captcha_fail: print(f"  Captcha failed:  {captcha_fail}")
    print(f"  Log:             {LOG_FILE.name}")
    print(f"  Screenshots:     {SCREENSHOT_DIR}")
    if review: print(f"  Review images:   {REVIEW_SCREENSHOT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
