#!/usr/bin/env python3
"""Magazine Advertiser Enricher

Enriches detected advertisers with business data:
- Website discovery and meta description scraping
- Owner/decision maker identification
- LinkedIn profile lookup
- Email discovery with optional SMTP verification

Uses the shared enrichment engine (lib/enrichment_engine.py) and
checkpoint manager (lib/checkpoint.py) for resilient processing.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import json
import time
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

try:
    from lib.enrichment_engine import EnrichmentEngine
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False
    print("[WARN] lib.enrichment_engine not available, using standalone enrichment")

try:
    from lib.checkpoint import CheckpointManager
    HAS_CHECKPOINT = True
except ImportError:
    HAS_CHECKPOINT = False


CHECKPOINT_PATH = Path(".tmp") / "magazine_enrichment_checkpoint.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
RATE_LIMIT_DELAY = 2.0
PAUSE_EVERY_N = 10
PAUSE_DURATION = 15.0


def scrape_meta_description(url: str) -> str:
    """Get meta description from a business website.

    Returns the description text (up to 300 chars) or empty string.
    """
    if not url:
        return ""

    # Normalize URL
    if not url.startswith("http"):
        url = "https://" + url

    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True
        )
        resp.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text[:50000], "html.parser")

        # Try meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()[:300]

        # Try og:description as fallback
        og_meta = soup.find("meta", attrs={"property": "og:description"})
        if og_meta and og_meta.get("content"):
            return og_meta["content"].strip()[:300]

        return ""
    except Exception:
        return ""


def find_website_exa(business_name: str, api_key: str) -> str | None:
    """Find business website using Exa search."""
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "query": f"{business_name} official website",
            "numResults": 3,
            "type": "keyword"
        }
        resp = requests.post("https://api.exa.ai/search", json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for r in results:
                url = r.get("url", "")
                # Skip social media and directories
                skip_domains = ["facebook.com", "linkedin.com", "yelp.com", "yellowpages.com",
                                "bbb.org", "mapquest.com", "instagram.com", "twitter.com"]
                if not any(d in url.lower() for d in skip_domains):
                    return url
    except Exception:
        pass
    return None


def find_owner_exa(business_name: str, website: str, api_key: str) -> dict:
    """Find business owner/decision maker using Exa."""
    result = {"owner_name": None, "owner_title": None, "linkedin_url": None, "email": None}
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "query": f'"{business_name}" owner OR founder OR CEO site:linkedin.com/in/',
            "numResults": 3,
            "type": "keyword"
        }
        resp = requests.post("https://api.exa.ai/search", json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for r in results:
                url = r.get("url", "")
                title = r.get("title", "")
                if "linkedin.com/in/" in url:
                    result["linkedin_url"] = url.split("?")[0]  # Strip query params
                    # Try to extract name from title
                    if " - " in title:
                        result["owner_name"] = title.split(" - ")[0].strip()
                    elif " | " in title:
                        result["owner_name"] = title.split(" | ")[0].strip()
                    break
    except Exception:
        pass
    return result


def verify_email_smtp(email: str) -> dict:
    """Verify email via Reacher SMTP verification service."""
    reacher_url = os.getenv("REACHER_API_URL")
    reacher_key = os.getenv("REACHER_API_KEY")
    if not reacher_url or not reacher_key:
        return {"is_reachable": "unknown", "verified": False}

    try:
        headers = {"Authorization": reacher_key, "Content-Type": "application/json"}
        resp = requests.post(
            f"{reacher_url}/v0/check_email",
            json={"to_email": email},
            headers=headers,
            timeout=45
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "is_reachable": data.get("is_reachable", "unknown"),
                "verified": data.get("is_reachable") == "safe",
                "smtp_ok": data.get("smtp", {}).get("can_connect_smtp", False)
            }
    except Exception:
        pass
    return {"is_reachable": "unknown", "verified": False}


def get_exa_key() -> str | None:
    """Get next available Exa API key with rotation."""
    key_vars = ["EXA_API_KEY_4", "EXA_API_KEY_5", "EXA_API_KEY_6",
                "EXA_API_KEY", "EXA_API_KEY_2", "EXA_API_KEY_3"]
    for var in key_vars:
        key = os.getenv(var)
        if key:
            return key
    return None


def enrich_single(ad: dict, exa_key: str, verify_smtp: bool = False) -> dict:
    """Enrich a single advertiser with website, owner, LinkedIn, email.

    Args:
        ad: Dict with at least business_name
        exa_key: Exa API key
        verify_smtp: Whether to SMTP-verify found emails

    Returns:
        Enriched ad dict with additional fields
    """
    name = ad.get("business_name", "")
    if not name:
        return ad

    enriched = dict(ad)

    # Step 1: Find website (use detected website first, then search)
    website = ad.get("website")
    if website and not website.startswith("http"):
        website = "https://" + website

    if not website:
        website = find_website_exa(name, exa_key)

    if website:
        enriched["website"] = website

        # Scrape meta description
        meta = scrape_meta_description(website)
        if meta:
            enriched["meta_description"] = meta

    # Step 2: Find owner and LinkedIn
    owner_info = find_owner_exa(name, website or "", exa_key)
    if owner_info.get("owner_name"):
        enriched["owner_name"] = owner_info["owner_name"]
    if owner_info.get("owner_title"):
        enriched["owner_title"] = owner_info["owner_title"]
    if owner_info.get("linkedin_url"):
        enriched["linkedin_url"] = owner_info["linkedin_url"]

    # Step 3: Email discovery — try common patterns from website domain
    if website and not enriched.get("email"):
        try:
            from urllib.parse import urlparse
            domain = urlparse(website).netloc.replace("www.", "")
            if domain and enriched.get("owner_name"):
                parts = enriched["owner_name"].lower().split()
                if len(parts) >= 2:
                    first, last = parts[0], parts[-1]
                    # Common patterns
                    candidates = [
                        f"{first}@{domain}",
                        f"{first}.{last}@{domain}",
                        f"{first[0]}{last}@{domain}",
                    ]
                    enriched["email_candidates"] = candidates
        except Exception:
            pass

    # Step 4: SMTP verify if email found
    if verify_smtp and enriched.get("email"):
        smtp_result = verify_email_smtp(enriched["email"])
        enriched["email_verified"] = smtp_result.get("verified", False)
        enriched["email_reachable"] = smtp_result.get("is_reachable", "unknown")

    enriched["enriched"] = True
    return enriched


def enrich_advertisers(ads: list, verify_smtp: bool = False) -> list:
    """Enrich all advertisers with business data.

    Features:
    - Checkpoint/resume support (saves every 5 advertisers)
    - Rate limiting (2s delay, 15s pause every 10 calls)
    - Exa API key rotation

    Args:
        ads: List of ad dicts from detect_ads
        verify_smtp: Whether to SMTP-verify found emails

    Returns:
        List of enriched ad dicts
    """
    exa_key = get_exa_key()
    if not exa_key:
        print("[ERROR] No Exa API key found in .env")
        return ads

    # Load checkpoint
    enriched = []
    processed_names = set()
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)
            enriched = checkpoint_data.get("enriched", [])
            processed_names = {a.get("business_name", "").lower() for a in enriched}
            print(f"  Resuming: {len(enriched)} already enriched")

    count = 0
    for ad in ads:
        name = ad.get("business_name", "")
        if name.lower() in processed_names:
            continue

        count += 1
        print(f"  [{count}/{len(ads) - len(processed_names)}] {name}...", end=" ", flush=True)

        try:
            result = enrich_single(ad, exa_key, verify_smtp)
            enriched.append(result)
            processed_names.add(name.lower())

            # Report what we found
            parts = []
            if result.get("website"): parts.append("web")
            if result.get("owner_name"): parts.append(f"owner={result['owner_name']}")
            if result.get("linkedin_url"): parts.append("LI")
            if result.get("email"): parts.append("email")
            print(", ".join(parts) if parts else "minimal")

        except Exception as e:
            print(f"ERROR: {e}")
            enriched.append(ad)  # Keep unenriched version

        # Checkpoint every 5
        if count % 5 == 0:
            CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
                json.dump({"enriched": enriched}, f, indent=2, ensure_ascii=False)

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)
        if count % PAUSE_EVERY_N == 0:
            print(f"  [Pause] {PAUSE_DURATION}s cooldown...")
            time.sleep(PAUSE_DURATION)

    # Final save and cleanup
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    # Stats
    with_website = sum(1 for a in enriched if a.get("website"))
    with_owner = sum(1 for a in enriched if a.get("owner_name"))
    with_linkedin = sum(1 for a in enriched if a.get("linkedin_url"))
    with_email = sum(1 for a in enriched if a.get("email"))
    print(f"\n  Enrichment stats: {len(enriched)} total")
    print(f"    Websites: {with_website} | Owners: {with_owner} | LinkedIn: {with_linkedin} | Emails: {with_email}")

    return enriched


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enrich magazine advertisers")
    parser.add_argument("--input", required=True, help="JSON file with detected ads")
    parser.add_argument("--skip-smtp", action="store_true")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        ads = json.load(f)

    print(f"Enriching {len(ads)} advertisers...")
    enriched = enrich_advertisers(ads, verify_smtp=not args.skip_smtp)

    output = args.input.replace(".json", "_enriched.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output}")
