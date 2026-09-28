#!/usr/bin/env python3
"""
Scrape thumbnails from any YouTube channel.

Downloads the highest-quality thumbnail for every video on a channel,
sorted by view count so you always get the best-performers first.

Usage:
    python scrape_channel_thumbnails.py --channel "@MrBeast" --limit 20
    python scrape_channel_thumbnails.py --channel "@nickosaraev" --limit 50 --sort views
    python scrape_channel_thumbnails.py --channel "https://www.youtube.com/@some_channel"

Output:
    thumbnails/<channel_name>/
        ├── <video_id>__<slugified_title>.jpg
        └── ...
    thumbnails/<channel_name>/metadata.json   (title, views, url, date for each video)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

# ── Config ─────────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path("thumbnails")
QUALITY_ORDER = ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]


def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:max_len]


def resolve_channel_url(channel: str) -> str:
    """Accept @handle, channel URL, or /c/ URL and return a canonical videos URL."""
    if channel.startswith("http"):
        base = channel.rstrip("/")
    elif channel.startswith("@"):
        base = f"https://www.youtube.com/{channel}"
    else:
        base = f"https://www.youtube.com/@{channel.lstrip('@')}"

    # Ensure we're hitting the /videos tab
    if not base.endswith("/videos"):
        base += "/videos"
    return base


def fetch_video_list(channel_url: str, limit: int = 30, sort: str = "date") -> list[dict]:
    """
    Use yt-dlp to get video metadata from a channel.

    Returns list of dicts: {id, title, views, upload_date, url}
    Sorted by views (desc) if sort=='views', else newest first.
    """
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(view_count)s\t%(upload_date)s",
        "--playlist-end", str(max(limit * 2, 50)),  # fetch extra to allow sorting
        "--no-warnings",
        channel_url,
    ]

    print(f"Fetching video list from: {channel_url}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120
        )
    except FileNotFoundError:
        print("ERROR: yt-dlp not found. Install with:  pip install yt-dlp")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: yt-dlp timed out")
        sys.exit(1)

    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        vid_id = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else vid_id
        views_raw = parts[2].strip() if len(parts) > 2 else "0"
        date_raw = parts[3].strip() if len(parts) > 3 else "00000000"

        try:
            views = int(views_raw) if views_raw not in ("", "NA", "None") else 0
        except ValueError:
            views = 0

        videos.append({
            "id": vid_id,
            "title": title,
            "views": views,
            "upload_date": date_raw,
            "url": f"https://www.youtube.com/watch?v={vid_id}",
        })

    if sort == "views":
        videos.sort(key=lambda v: v["views"], reverse=True)

    return videos[:limit]


def download_thumbnail(video_id: str, save_path: Path) -> bool:
    """Download the best available YouTube thumbnail to save_path."""
    for quality in QUALITY_ORDER:
        url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                img = resp.content
                # YouTube returns a placeholder (120×90) for missing qualities
                if len(img) < 5_000 and quality not in ("default", "mqdefault"):
                    continue
                save_path.write_bytes(img)
                return True
        except requests.RequestException:
            continue
    return False


def scrape_channel(channel: str, limit: int = 20, sort: str = "date", output_dir: Path = None) -> list[dict]:
    """
    Full scrape: fetch video list → download thumbnails → save metadata.

    Returns list of metadata dicts for downloaded thumbnails.
    """
    channel_url = resolve_channel_url(channel)

    # Determine channel name for folder
    handle = channel.lstrip("@").split("/")[-1]
    out_dir = (output_dir or OUTPUT_DIR) / handle
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output folder: {out_dir}")
    print(f"Fetching up to {limit} videos (sort={sort})...")

    videos = fetch_video_list(channel_url, limit=limit, sort=sort)
    print(f"Found {len(videos)} videos")

    downloaded = []
    for i, video in enumerate(videos, 1):
        slug = slugify(video["title"])
        filename = f"{video['id']}__{slug}.jpg"
        save_path = out_dir / filename

        if save_path.exists():
            print(f"  [{i}/{len(videos)}] Already exists: {filename}")
            video["thumbnail_path"] = str(save_path)
            downloaded.append(video)
            continue

        ok = download_thumbnail(video["id"], save_path)
        status = "OK" if ok else "FAIL"
        views_str = f"{video['views']:,}" if video["views"] else "?"
        print(f"  [{i}/{len(videos)}] {status} | {views_str:>12} views | {video['title'][:50]}")

        if ok:
            video["thumbnail_path"] = str(save_path)
            downloaded.append(video)

        time.sleep(0.2)  # gentle rate limit

    # Save metadata
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(
        json.dumps(downloaded, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved {len(downloaded)} thumbnails to {out_dir}")
    print(f"Metadata: {meta_path}")

    return downloaded


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape thumbnails from any YouTube channel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_channel_thumbnails.py --channel "@MrBeast" --limit 20
  python scrape_channel_thumbnails.py --channel "@nickosaraev" --limit 50 --sort views
  python scrape_channel_thumbnails.py --channel "https://www.youtube.com/@hubermanlab" --limit 30
        """,
    )
    parser.add_argument("--channel", "-c", required=True,
                        help="Channel handle (@name), URL, or name")
    parser.add_argument("--limit", "-n", type=int, default=20,
                        help="Max thumbnails to download (default: 20)")
    parser.add_argument("--sort", choices=["date", "views"], default="date",
                        help="Sort videos by date (default) or view count")
    parser.add_argument("--output", "-o", type=str, default="thumbnails",
                        help="Output directory (default: thumbnails/)")
    args = parser.parse_args()

    scrape_channel(
        channel=args.channel,
        limit=args.limit,
        sort=args.sort,
        output_dir=Path(args.output),
    )


if __name__ == "__main__":
    main()
