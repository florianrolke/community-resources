#!/usr/bin/env python3
"""
Email Discovery + SMTP Verification

Finds business emails through multiple strategies:
  1. Website scraping (mailto links, contact pages)
  2. Pattern generation (first@domain, info@domain)
  3. SMTP verification via self-hosted Reacher

Usage:
    python -X utf8 find_email.py --name "John Smith" --domain "acmecorp.com"
    python -X utf8 find_email.py --input leads.json --output leads_with_email.json
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding

fix_encoding()

import argparse
import json
import re
import requests
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

from lib.safe_io import safe_json_write, safe_json_read
from lib.rate_limiter import RateLimiter


# Common email patterns to try
EMAIL_PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "info@{domain}",
    "contact@{domain}",
]

REACHER_URL = os.environ.get("REACHER_API_URL", "")
REACHER_KEY = os.environ.get("REACHER_API_KEY", "")


def extract_emails_from_website(url: str) -> list[str]:
    """Scrape email addresses from a business website."""
    if not url:
        return []

    emails = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        html = resp.text[:100000]

        # Find mailto links
        mailto_pattern = re.compile(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
        for match in mailto_pattern.finditer(html):
            emails.add(match.group(1).lower())

        # Find email-like strings
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        for match in email_pattern.finditer(html):
            email = match.group(0).lower()
            # Filter out obvious non-emails
            if not any(x in email for x in ["@example", "@test", "@sentry", "@wix",
                                             ".png", ".jpg", ".gif", ".css", ".js"]):
                emails.add(email)

    except Exception:
        pass

    return list(emails)


def generate_email_patterns(first_name: str, last_name: str, domain: str) -> list[str]:
    """Generate common email patterns for a person at a domain."""
    if not domain or not first_name:
        return []

    first = first_name.lower().strip()
    last = last_name.lower().strip() if last_name else ""
    f = first[0] if first else ""

    patterns = []
    for pattern in EMAIL_PATTERNS:
        try:
            email = pattern.format(first=first, last=last, f=f, domain=domain)
            if "@" in email and not email.startswith("@"):
                patterns.append(email)
        except (KeyError, IndexError):
            continue

    return patterns


def verify_email_smtp(email: str) -> dict:
    """Verify an email address via Reacher SMTP check.

    Returns: {"is_reachable": "safe"|"risky"|"invalid"|"unknown",
              "can_connect_smtp": bool, "is_deliverable": bool}
    """
    if not REACHER_URL:
        return {"is_reachable": "unknown", "note": "REACHER_API_URL not configured"}

    headers = {"Content-Type": "application/json"}
    if REACHER_KEY:
        headers["Authorization"] = REACHER_KEY

    try:
        resp = requests.post(
            f"{REACHER_URL}/v0/check_email",
            json={"to_email": email},
            headers=headers,
            timeout=45,
        )
        if resp.ok:
            data = resp.json()
            return {
                "is_reachable": data.get("is_reachable", "unknown"),
                "can_connect_smtp": data.get("smtp", {}).get("can_connect_smtp", False),
                "is_deliverable": data.get("smtp", {}).get("is_deliverable", False),
            }
    except Exception as e:
        return {"is_reachable": "unknown", "error": str(e)}

    return {"is_reachable": "unknown"}


def find_email(name: str, website: str = "", verify: bool = True) -> dict:
    """Find and optionally verify an email for a person.

    Returns: {"email": str, "source": str, "verification": dict}
    """
    result = {"email": None, "source": None, "verification": None}

    # Strategy 1: Scrape from website
    if website:
        domain = urlparse(website).netloc.lower().replace("www.", "")
        scraped = extract_emails_from_website(website)

        # Filter out generic emails, prefer personal ones
        personal = [e for e in scraped if not e.startswith(("info@", "contact@", "hello@", "support@"))]
        generic = [e for e in scraped if e.startswith(("info@", "contact@"))]

        if personal:
            result["email"] = personal[0]
            result["source"] = "website_scrape"
        elif generic:
            result["email"] = generic[0]
            result["source"] = "website_scrape_generic"

    # Strategy 2: Pattern generation (if we have name + domain)
    if not result["email"] and website and name:
        domain = urlparse(website).netloc.lower().replace("www.", "")
        parts = name.strip().split()
        first = parts[0] if parts else ""
        last = parts[-1] if len(parts) > 1 else ""
        patterns = generate_email_patterns(first, last, domain)

        # Try the most common pattern first
        if patterns:
            result["email"] = patterns[0]
            result["source"] = "pattern_generated"

    # Strategy 3: SMTP verify
    if result["email"] and verify and REACHER_URL:
        result["verification"] = verify_email_smtp(result["email"])
        if result["verification"].get("is_reachable") == "invalid":
            result["email"] = None
            result["source"] = None

    return result


def main():
    parser = argparse.ArgumentParser(description="Find and verify business emails")
    parser.add_argument("--name", help="Person name (single lookup)")
    parser.add_argument("--website", default="", help="Business website URL")
    parser.add_argument("--input", help="Input JSON for batch mode")
    parser.add_argument("--output", help="Output JSON for batch mode")
    parser.add_argument("--no-verify", action="store_true", help="Skip SMTP verification")
    args = parser.parse_args()

    if args.name:
        result = find_email(args.name, args.website, verify=not args.no_verify)
        print(f"Email: {result['email'] or 'not found'}")
        if result["source"]:
            print(f"Source: {result['source']}")
        if result["verification"]:
            print(f"Verification: {result['verification']}")
    elif args.input:
        data = safe_json_read(args.input)
        if not data:
            return
        limiter = RateLimiter(delay=1.0, pause_every=15, pause_duration=10.0)
        found = 0
        for i, lead in enumerate(data):
            name = lead.get("name", lead.get("contact", ""))
            website = lead.get("website", "")
            if not name and not website:
                continue
            if lead.get("email"):
                found += 1
                continue
            limiter.wait()
            result = find_email(name, website, verify=not args.no_verify)
            if result["email"]:
                lead["email"] = result["email"]
                lead["email_source"] = result["source"]
                lead["email_verification"] = result["verification"]
                found += 1
                print(f"  [{i + 1}] {name[:30]} -> {result['email']}")
        output = args.output or str(Path(args.input).with_stem(Path(args.input).stem + "_emails"))
        safe_json_write(output, data)
        print(f"\nEmails found: {found}/{len(data)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
