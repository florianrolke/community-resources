#!/usr/bin/env python3
"""Magazine Ad Detector — Claude Haiku Vision

Sends cropped page images to Claude Haiku for ad detection.
Returns structured JSON with business name, ad type, and page number.

Blank pages (< 55KB) are automatically skipped.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import json
import re
import time
import base64
import requests
import anthropic
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


BLANK_THRESHOLD_BYTES = 55000
HAIKU_MODEL = "claude-haiku-4-5-20251001"
OPENROUTER_MODEL = "anthropic/claude-haiku-4-5"
RATE_LIMIT_DELAY = 1.0  # seconds between API calls

# Auto-detect: None = try Anthropic first, True = use OpenRouter
_USE_OPENROUTER = None

DETECTION_PROMPT = """Identify all business advertisements on this magazine page.

For each ad, return:
- business_name: The business name exactly as shown
- ad_type: One of: full_page, half_page, quarter_page, strip, logo_only
- phone: Phone number if visible (null if not)
- website: Website URL if visible (null if not)

Return as a JSON array. If there are no ads (editorial content only), return [].

Example:
[
  {"business_name": "Smith Dental", "ad_type": "half_page", "phone": "(913) 555-0100", "website": "smithdental.com"},
  {"business_name": "KC Roofing", "ad_type": "quarter_page", "phone": null, "website": "kcroofing.com"}
]

Return ONLY the JSON array, no other text."""


def parse_ad_response(content: str) -> list:
    """Parse Claude's response into a list of ad dicts.

    Handles cases where the response includes markdown code fences or extra text.
    """
    content = content.strip()

    # Try direct JSON parse first
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting JSON array from response
    match = re.search(r'\[[\s\S]*?\]', content)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Try stripping markdown code fences
    cleaned = re.sub(r'```(?:json)?\s*', '', content)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    return []


def _call_vision_anthropic(api_key: str, image_data: str, media_type: str, prompt_text: str):
    """Call Anthropic API directly for vision detection."""
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={
            "model": HAIKU_MODEL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": prompt_text}
            ]}]
        },
        timeout=30,
    )
    if response.status_code == 429:
        for retry in range(3):
            wait = (retry + 1) * 10
            print(f"    [WARN] Claude 429 — retrying in {wait}s (attempt {retry+2}/4)")
            time.sleep(wait)
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={
                    "model": HAIKU_MODEL,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                        {"type": "text", "text": prompt_text}
                    ]}]
                },
                timeout=30,
            )
            if response.status_code != 429:
                break
    if not response.ok:
        return None, response.status_code, response.text[:200]
    text = response.json().get("content", [{}])[0].get("text", "")
    return text, 200, None


def _call_vision_openrouter(api_key: str, image_data: str, media_type: str, prompt_text: str):
    """Call OpenRouter API (fallback when Anthropic credits exhausted)."""
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": OPENROUTER_MODEL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}},
                {"type": "text", "text": prompt_text}
            ]}]
        },
        timeout=60,
    )
    if not response.ok:
        return None, response.status_code, response.text[:200]
    text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return text, 200, None


def detect_ads_single_page(client, page_path: Path, page_num: int) -> list:
    """Detect ads in a single page image.

    Uses Anthropic API by default, auto-switches to OpenRouter if Anthropic
    credits are exhausted (400 error with "credit balance" in message).

    Args:
        client: Unused (kept for backward compat). Uses env vars directly.
        page_path: Path to the cropped page image
        page_num: Page number for metadata

    Returns:
        List of ad dicts with page_num and source_image added
    """
    global _USE_OPENROUTER

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not anthropic_key and not openrouter_key:
        print("  [ERROR] No API key set (ANTHROPIC_API_KEY or OPENROUTER_API_KEY)")
        return []

    # Read and encode image
    with open(page_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    # Determine media type
    suffix = page_path.suffix.lower()
    media_type_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    media_type = media_type_map.get(suffix, "image/png")

    try:
        text = None

        # Try Anthropic first, auto-switch to OpenRouter on credit exhaustion
        if _USE_OPENROUTER is not True and anthropic_key:
            text, status, err = _call_vision_anthropic(anthropic_key, image_data, media_type, DETECTION_PROMPT)
            if text is None and status == 400 and "credit balance" in (err or "").lower():
                print("    [INFO] Anthropic credits exhausted — switching to OpenRouter")
                _USE_OPENROUTER = True
            elif text is None:
                print(f"    [WARN] Claude API error: HTTP {status}")
                return []

        if _USE_OPENROUTER and openrouter_key:
            text, status, err = _call_vision_openrouter(openrouter_key, image_data, media_type, DETECTION_PROMPT)
            if text is None:
                print(f"    [WARN] OpenRouter API error: HTTP {status}")
                return []
        elif _USE_OPENROUTER and not openrouter_key:
            print("    [ERROR] OpenRouter key not set, cannot fallback")
            return []

        if not text:
            return []

        ads = parse_ad_response(text)

        # Add metadata to each ad
        for ad in ads:
            ad["page_num"] = page_num
            ad["source_image"] = str(page_path)

        return ads

    except Exception as e:
        print(f"    [ERROR] Page {page_num}: {e}")
        return []


def detect_ads_in_pages(page_paths: list, tmp_dir: Path) -> list:
    """Send page images to Claude Haiku vision for ad detection.

    Args:
        page_paths: List of Path objects to cropped page images
        tmp_dir: Temp directory for intermediate results

    Returns:
        List of ad dicts with business_name, ad_type, page_num, etc.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not set in .env")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    all_ads = []

    # Load any previous partial results
    partial_path = Path(tmp_dir) / "detected_ads_partial.json"
    processed_pages = set()
    if partial_path.exists():
        with open(partial_path, "r", encoding="utf-8") as f:
            previous = json.load(f)
            all_ads = previous
            processed_pages = {ad["page_num"] for ad in previous}
            print(f"  Resuming: {len(processed_pages)} pages already processed")

    for page_path in page_paths:
        page_path = Path(page_path)

        # Extract page number from filename (page_001.png -> 1)
        try:
            page_num = int(page_path.stem.split("_")[-1])
        except (ValueError, IndexError):
            page_num = 0

        # Skip already processed
        if page_num in processed_pages:
            continue

        # Skip blank pages
        if page_path.stat().st_size < BLANK_THRESHOLD_BYTES:
            print(f"  Page {page_num}: BLANK (skipped)")
            continue

        print(f"  Page {page_num}: analyzing...", end=" ", flush=True)
        ads = detect_ads_single_page(client, page_path, page_num)

        if ads:
            print(f"found {len(ads)} ads: {', '.join(a.get('business_name', '?') for a in ads)}")
            all_ads.extend(ads)
        else:
            print("no ads (editorial)")

        # Save partial results every 5 pages
        if len(all_ads) % 5 == 0 and all_ads:
            with open(partial_path, "w", encoding="utf-8") as f:
                json.dump(all_ads, f, indent=2, ensure_ascii=False)

        time.sleep(RATE_LIMIT_DELAY)

    # Save final results
    with open(partial_path, "w", encoding="utf-8") as f:
        json.dump(all_ads, f, indent=2, ensure_ascii=False)

    # Deduplicate by business name (same business may appear on multiple pages)
    seen_names = {}
    deduped = []
    for ad in all_ads:
        name = ad.get("business_name", "").strip().lower()
        if name and name not in seen_names:
            seen_names[name] = True
            deduped.append(ad)
        elif name in seen_names:
            # Keep the one with more data
            pass

    print(f"\n  Total unique advertisers: {len(deduped)} (from {len(all_ads)} detections)")
    return deduped


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Detect ads in magazine page images")
    parser.add_argument("--pages-dir", required=True, help="Directory with page images")
    args = parser.parse_args()

    pages_dir = Path(args.pages_dir)
    pages = sorted(pages_dir.glob("page_*.png"))
    print(f"Found {len(pages)} page images")

    ads = detect_ads_in_pages(pages, pages_dir)
    print(f"\nDetected {len(ads)} unique advertisers")
    for ad in ads:
        print(f"  p{ad.get('page_num', '?')}: {ad.get('business_name', '?')} ({ad.get('ad_type', '?')})")
