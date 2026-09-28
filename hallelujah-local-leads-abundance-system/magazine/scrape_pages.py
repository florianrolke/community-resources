#!/usr/bin/env python3
"""Magazine Page Screenshotter — Firecrawl + Issuu

Screenshots each page of an Issuu magazine embed and removes Issuu chrome
(zoom controls, sidebars, "Create a flipbook" text) using brightness analysis.

Technical details:
- Issuu embed URL: https://e.issuu.com/embed.html?d={SLUG}
  (NOT issuu.com/lifestylepubs/docs/)
- Firecrawl v2: use "formats": ["screenshot"] only
  Do NOT pass "screenshot": {"fullPage": false}
- Blank page detection: file size < 55KB = likely blank
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import json
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"
ISSUU_EMBED_BASE = "https://e.issuu.com/embed.html"
MAX_PAGES = 80
BLANK_THRESHOLD_BYTES = 55000
RATE_LIMIT_DELAY = 2.0


def crop_issuu_chrome(image_path: str, output_path: str) -> str:
    """Remove Issuu UI chrome from screenshot using per-row/col brightness analysis.

    Improved strategy (from production Andy pipeline):
    - Scan rows starting at y=60 for dark→bright transition to find content top
    - Bottom = top + 59% of total height (removes bottom controls + "Create a flipbook")
    - Scan columns starting at x=200 for left edge, x=1700 for right edge
    - Detect spreads (width > height × 1.3) and split into two pages
    """
    from PIL import Image
    import numpy as np

    img = Image.open(image_path)
    arr = np.array(img)
    h, w = arr.shape[:2]

    # Per-row and per-column mean brightness
    row_br = arr.mean(axis=(1, 2))
    col_br = arr.mean(axis=(0, 2))
    dark_thresh = 130

    # Find top edge: scan from row 60 for dark→bright transition
    top = int(h * 0.10)
    for y in range(60, h // 2):
        if row_br[y] < dark_thresh:
            for y2 in range(y, h // 2):
                if row_br[y2] > dark_thresh:
                    top = y2
                    break
            break

    # Bottom = top + 59% of total height
    bottom = top + int(h * 0.59)
    bottom = min(bottom, h)

    # Find left edge: scan from column 200
    left = int(w * 0.27)
    for x in range(200, w // 2):
        if col_br[x] < dark_thresh:
            for x2 in range(x, w // 2):
                if col_br[x2] > dark_thresh:
                    left = x2
                    break
            break

    # Find right edge: scan from column 1700 backward
    right = int(w * 0.73)
    for x in range(min(1700, w - 1), w // 2, -1):
        if col_br[x] < dark_thresh:
            for x2 in range(x, w // 2, -1):
                if col_br[x2] > dark_thresh:
                    right = x2 + 1
                    break
            break

    # Sanity check: don't crop to nothing
    if right - left < 100 or bottom - top < 100:
        img.save(output_path)
        return output_path

    cropped = img.crop((left, top, right, bottom))

    # Spread detection: if content is much wider than tall, split into 2 pages
    cw, ch = cropped.size
    if cw > ch * 1.3:
        mid = cw // 2
        left_page = cropped.crop((0, 0, mid, ch))
        right_page = cropped.crop((mid, 0, cw, ch))

        # Save left page as the main output
        left_page.save(output_path)
        # Save right page with _b suffix
        base, ext = os.path.splitext(output_path)
        right_path = f"{base}_b{ext}"
        right_page.save(right_path)
        return output_path  # caller will pick up _b via glob
    else:
        cropped.save(output_path)
        return output_path


def screenshot_page_firecrawl(url: str, api_key: str) -> bytes | None:
    """Screenshot a single URL using Firecrawl v2 API.

    Returns PNG bytes or None on failure.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "url": url,
        "formats": ["screenshot"],
        "waitFor": 3000
    }

    try:
        resp = requests.post(FIRECRAWL_API_URL, json=payload, headers=headers, timeout=60)
        if resp.status_code == 429:
            print("    [WARN] Rate limited, waiting 30s...")
            time.sleep(30)
            resp = requests.post(FIRECRAWL_API_URL, json=payload, headers=headers, timeout=60)

        if resp.status_code != 200:
            print(f"    [WARN] Firecrawl returned {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        screenshot_b64 = data.get("data", {}).get("screenshot")
        if not screenshot_b64:
            # Try alternate response shape
            screenshot_b64 = data.get("screenshot")

        if not screenshot_b64:
            print("    [WARN] No screenshot in response")
            return None

        # Strip data URI prefix if present
        if "base64," in screenshot_b64:
            screenshot_b64 = screenshot_b64.split("base64,")[1]

        return base64.b64decode(screenshot_b64)

    except requests.exceptions.Timeout:
        print("    [WARN] Firecrawl request timed out")
        return None
    except Exception as e:
        print(f"    [WARN] Firecrawl error: {e}")
        return None


def screenshot_issue(issuu_slug: str, output_dir: Path) -> list:
    """Screenshot all pages of an Issuu magazine issue.

    Args:
        issuu_slug: The Issuu document slug (e.g., "johnson_county_ks_march_2026")
        output_dir: Directory to save cropped page images

    Returns:
        List of Path objects for cropped page images (blanks excluded)
    """
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("[ERROR] FIRECRAWL_API_KEY not set in .env")
        return []

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    page_paths = []
    consecutive_blanks = 0
    max_consecutive_blanks = 3  # Stop after 3 blank pages in a row

    for page_num in range(1, MAX_PAGES + 1):
        # Check if already scraped (resume support)
        cropped_path = output_dir / f"page_{page_num:03d}.png"
        if cropped_path.exists() and cropped_path.stat().st_size > BLANK_THRESHOLD_BYTES:
            page_paths.append(cropped_path)
            consecutive_blanks = 0
            print(f"  Page {page_num}: already exists, skipping")
            continue

        # Build Issuu embed URL with page parameter
        url = f"{ISSUU_EMBED_BASE}?d={issuu_slug}&pageLayout=singlePage&u=lifestylepubs&p={page_num}"
        print(f"  Page {page_num}: screenshotting...", end=" ", flush=True)

        png_bytes = screenshot_page_firecrawl(url, api_key)
        if not png_bytes:
            print("FAILED")
            consecutive_blanks += 1
            if consecutive_blanks >= max_consecutive_blanks:
                print(f"  Stopping: {max_consecutive_blanks} consecutive failures")
                break
            continue

        # Save raw screenshot
        raw_path = raw_dir / f"raw_page_{page_num:03d}.png"
        with open(raw_path, "wb") as f:
            f.write(png_bytes)

        # Check for blank page
        if raw_path.stat().st_size < BLANK_THRESHOLD_BYTES:
            print(f"BLANK ({raw_path.stat().st_size // 1024}KB)")
            consecutive_blanks += 1
            if consecutive_blanks >= max_consecutive_blanks:
                print(f"  Stopping: {max_consecutive_blanks} consecutive blanks")
                break
            continue

        # Crop Issuu chrome
        try:
            crop_issuu_chrome(str(raw_path), str(cropped_path))
            page_paths.append(cropped_path)
            consecutive_blanks = 0
            size_kb = cropped_path.stat().st_size // 1024
            print(f"OK ({size_kb}KB)")
        except Exception as e:
            print(f"CROP ERROR: {e}")
            # Fall back to raw
            import shutil
            shutil.copy2(raw_path, cropped_path)
            page_paths.append(cropped_path)
            consecutive_blanks = 0

        # Rate limit
        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Total pages captured: {len(page_paths)}")
    return page_paths


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Screenshot Issuu magazine pages")
    parser.add_argument("--slug", required=True, help="Issuu document slug")
    parser.add_argument("--output-dir", default=".tmp/magazine_pages/test", help="Output directory")
    args = parser.parse_args()

    pages = screenshot_issue(args.slug, Path(args.output_dir))
    print(f"\nDone: {len(pages)} pages saved to {args.output_dir}")
