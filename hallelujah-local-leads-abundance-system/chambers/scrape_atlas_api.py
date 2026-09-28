#!/usr/bin/env python3
"""Atlas SPA REST API Scraper

Uses Playwright to capture JWT token from Atlas Angular SPA, then calls
the WebLink Connect REST API directly for fast, complete member extraction.

Atlas API base: https://api-internal.weblinkconnect.com/api
Requires x-tenant header (e.g., "CaryNCCOC")

Usage:
    python scrape_atlas_api.py --url https://web.carycc.com/atlas/directory --tenant CaryNCCOC
    python scrape_atlas_api.py --url https://web.carycc.com/atlas/directory --tenant CaryNCCOC --output leads/cary_atlas.json
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import asyncio
import argparse
import json
import time
from datetime import datetime, timezone

# Social media type IDs in Atlas API
SOCIAL_TYPE_MAP = {
    101: "facebook",
    102: "twitter",
    103: "linkedin",
    113: "instagram",
    114: "youtube",
}

API_BASE = "https://api-internal.weblinkconnect.com/api"


async def capture_token(url: str, tenant: str) -> dict:
    """Use Playwright to load Atlas directory page and capture JWT token.

    Intercepts the Tenant/Current API response to extract the AccessToken.

    Returns: dict with 'token' and 'tenant' keys
    """
    from playwright.async_api import async_playwright

    token_data = {"token": None, "tenant": tenant}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Intercept API responses to capture the token
        async def handle_response(response):
            try:
                resp_url = response.url.lower()
                if "tenant/current" in resp_url or "token" in resp_url:
                    if response.status == 200:
                        body = await response.json()
                        # Token can be in various locations
                        if isinstance(body, dict):
                            for key in ["AccessToken", "accessToken", "access_token", "token", "Token"]:
                                if key in body:
                                    token_data["token"] = body[key]
                                    print(f"[TOKEN] Captured from {response.url}")
                                    return
                            # Sometimes nested under data
                            if "data" in body and isinstance(body["data"], dict):
                                for key in ["AccessToken", "accessToken", "access_token", "token"]:
                                    if key in body["data"]:
                                        token_data["token"] = body["data"][key]
                                        print(f"[TOKEN] Captured from {response.url} (nested)")
                                        return
            except Exception:
                pass

        page.on("response", handle_response)

        print(f"[ATLAS] Loading: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # If token not captured from response, try to extract from page
        if not token_data["token"]:
            print("[TOKEN] Trying to extract from page localStorage/sessionStorage...")
            token_from_page = await page.evaluate("""
                () => {
                    // Check localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        const val = localStorage.getItem(key);
                        if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth')) {
                            try {
                                const parsed = JSON.parse(val);
                                if (parsed.AccessToken) return parsed.AccessToken;
                                if (parsed.access_token) return parsed.access_token;
                                if (parsed.token) return parsed.token;
                            } catch(e) {
                                if (val && val.length > 20 && val.length < 2000) return val;
                            }
                        }
                    }
                    // Check sessionStorage
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        const val = sessionStorage.getItem(key);
                        if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth')) {
                            try {
                                const parsed = JSON.parse(val);
                                if (parsed.AccessToken) return parsed.AccessToken;
                                if (parsed.access_token) return parsed.access_token;
                            } catch(e) {
                                if (val && val.length > 20 && val.length < 2000) return val;
                            }
                        }
                    }
                    return null;
                }
            """)
            if token_from_page:
                token_data["token"] = token_from_page
                print("[TOKEN] Captured from page storage")

        # Also try to extract tenant from API calls if not provided
        if not token_data["tenant"]:
            tenant_from_page = await page.evaluate("""
                () => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const match = s.textContent.match(/tenant['":\\s]+['"]([A-Za-z0-9]+)['"]/);
                        if (match) return match[1];
                    }
                    return null;
                }
            """)
            if tenant_from_page:
                token_data["tenant"] = tenant_from_page

        await browser.close()

    if not token_data["token"]:
        print("[ERROR] Failed to capture JWT token")
        print("[HINT] Try running with a visible browser to debug: load the URL and check Network tab")

    return token_data


async def fetch_members_api(token: str, tenant: str, page_size: int = 100) -> list:
    """Fetch all members via Atlas REST API with pagination.

    Uses POST /website/v1/listing/search endpoint.
    """
    import aiohttp

    headers = {
        "Authorization": f"Bearer {token}",
        "x-tenant": tenant,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    }

    all_members = []
    page_num = 1
    total_pages = None

    async with aiohttp.ClientSession() as session:
        while True:
            payload = {
                "PageNumber": page_num,
                "PageSize": page_size,
                "Sort": "Name",
                "SortDirection": "ASC",
            }

            url = f"{API_BASE}/website/v1/listing/search"
            print(f"[API] Fetching page {page_num}" + (f"/{total_pages}" if total_pages else "") + "...")

            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 401:
                        print("[ERROR] Token expired or invalid (401)")
                        break
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"[ERROR] API returned {resp.status}: {text[:200]}")
                        break

                    data = await resp.json()

            except Exception as e:
                print(f"[ERROR] API request failed: {e}")
                break

            # Extract results
            items = data.get("Results", data.get("results", data.get("Items", data.get("items", []))))
            if not items:
                # Try alternate response shapes
                if isinstance(data, list):
                    items = data
                elif "data" in data:
                    items = data["data"] if isinstance(data["data"], list) else data["data"].get("Results", [])

            if not items:
                print(f"[INFO] No more results on page {page_num}")
                break

            # Calculate total pages from first response
            if total_pages is None:
                total_count = data.get("TotalCount", data.get("totalCount", data.get("Total", 0)))
                if total_count:
                    total_pages = (total_count + page_size - 1) // page_size
                    print(f"[INFO] Total members: {total_count}, pages: {total_pages}")

            for item in items:
                member = {
                    "company": item.get("Name", item.get("name", "")),
                    "address": _format_address(item),
                    "phone": item.get("Phone", item.get("phone", "")),
                    "website": item.get("Website", item.get("website", item.get("WebsiteUrl", ""))),
                    "category": item.get("Category", item.get("category", item.get("PrimaryCategory", ""))),
                    "detail_url": "",
                    "atlas_id": item.get("Id", item.get("id", "")),
                    "email": item.get("Email", item.get("email", "")),
                    "description": item.get("Description", item.get("description", ""))[:500] if item.get("Description") or item.get("description") else "",
                }
                all_members.append(member)

            print(f"  Page {page_num}: {len(items)} members (total so far: {len(all_members)})")

            if len(items) < page_size:
                break

            page_num += 1
            await asyncio.sleep(0.5)  # Gentle rate limiting

    return all_members


def _format_address(item: dict) -> str:
    """Format address from Atlas API item fields."""
    parts = []
    for key in ["Address1", "address1", "Address", "address"]:
        if item.get(key):
            parts.append(item[key])
            break
    for key in ["Address2", "address2"]:
        if item.get(key):
            parts.append(item[key])
            break
    city = item.get("City", item.get("city", ""))
    state = item.get("State", item.get("state", ""))
    zip_code = item.get("Zip", item.get("zip", item.get("PostalCode", "")))
    if city or state or zip_code:
        parts.append(f"{city}, {state} {zip_code}".strip().strip(","))
    return ", ".join(parts).strip(", ")


async def fetch_social_links(token: str, tenant: str, atlas_id: str) -> dict:
    """Fetch social media links for a single member via Atlas API.

    Social type IDs: 101=Facebook, 102=Twitter, 103=LinkedIn, 113=Instagram, 114=YouTube
    """
    import aiohttp

    headers = {
        "Authorization": f"Bearer {token}",
        "x-tenant": tenant,
        "Accept": "application/json",
    }

    social = {"linkedin": None, "facebook": None, "twitter": None, "instagram": None, "youtube": None}

    url = f"{API_BASE}/website/v1/listing/{atlas_id}/Social-media"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return social
                data = await resp.json()

        items = data if isinstance(data, list) else data.get("Results", data.get("items", []))
        for item in items:
            type_id = item.get("SocialMediaTypeId", item.get("TypeId", 0))
            link = item.get("Url", item.get("url", item.get("Link", "")))
            if not link:
                continue
            platform = SOCIAL_TYPE_MAP.get(type_id)
            if platform:
                social[platform] = link

    except Exception as e:
        print(f"[WARN] Social fetch error for {atlas_id}: {e}")

    return social


async def enrich_social_links(token: str, tenant: str, members: list, delay: float = 0.3) -> list:
    """Enrich all members with social media links."""
    total = len(members)
    enriched_count = 0

    for i, member in enumerate(members):
        atlas_id = member.get("atlas_id")
        if not atlas_id:
            continue

        social = await fetch_social_links(token, tenant, str(atlas_id))

        # Only update if we found something
        any_social = any(v for v in social.values())
        if any_social:
            member.update(social)
            enriched_count += 1

        if (i + 1) % 25 == 0:
            print(f"[SOCIAL] Progress: {i+1}/{total} members, {enriched_count} with social links")

        await asyncio.sleep(delay)

    print(f"[SOCIAL] Complete: {enriched_count}/{total} members have social links")
    return members


async def run(args):
    """Main async entry point."""
    # Step 1: Capture JWT token via Playwright
    print(f"{'='*60}")
    print(f"Atlas API Scraper")
    print(f"{'='*60}")

    token_data = await capture_token(args.url, args.tenant)

    if not token_data["token"]:
        print("[FATAL] Could not capture authentication token. Exiting.")
        sys.exit(1)

    token = token_data["token"]
    tenant = token_data["tenant"] or args.tenant

    print(f"[INFO] Token captured ({len(token)} chars)")
    print(f"[INFO] Tenant: {tenant}")

    # Step 2: Fetch all members via REST API
    members = await fetch_members_api(token, tenant, page_size=100)

    if not members:
        print("[WARN] No members returned from API")
        return

    # Step 3: Enrich with social links (if not skipped)
    if not args.skip_social:
        print(f"\n[SOCIAL] Enriching {len(members)} members with social links...")
        members = await enrich_social_links(token, tenant, members, delay=0.3)
    else:
        print("[SOCIAL] Skipping social link enrichment (--skip-social)")

    # Step 4: Add metadata
    for m in members:
        m["source"] = "atlas_api"
        m["scraped_at"] = datetime.now(timezone.utc).isoformat()

    # Step 5: Save output
    output_path = args.output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(members, f, indent=2, ensure_ascii=False)

    # Print summary
    linkedin_count = sum(1 for m in members if m.get("linkedin"))
    facebook_count = sum(1 for m in members if m.get("facebook"))
    email_count = sum(1 for m in members if m.get("email"))

    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"  Total members: {len(members)}")
    print(f"  With LinkedIn: {linkedin_count}")
    print(f"  With Facebook: {facebook_count}")
    print(f"  With email:    {email_count}")
    print(f"  Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Atlas SPA REST API Scraper")
    parser.add_argument("--url", required=True, help="Atlas directory page URL (e.g., https://web.carycc.com/atlas/directory)")
    parser.add_argument("--tenant", required=True, help="x-tenant header value (e.g., CaryNCCOC)")
    parser.add_argument("--output", default="leads/atlas_members.json", help="Output JSON file path (default: leads/atlas_members.json)")
    parser.add_argument("--skip-social", action="store_true", help="Skip social media link enrichment")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
