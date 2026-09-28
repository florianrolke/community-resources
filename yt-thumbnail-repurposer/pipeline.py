#!/usr/bin/env python3
"""
Full Pipeline: Scrape → Rank → Augment

Finds the best-performing thumbnails from a YouTube channel and
augments them with your face/brand using Kie.ai image-to-image.

Usage:
    # Full pipeline: scrape top 20 by views, augment top 3
    python pipeline.py --channel "@MrBeast" --scrape 20 --augment 3 \
        --prompt "Replace person with professional man in dark suit" \
        --style cinematic-dark

    # Skip scraping (use already-downloaded thumbnails)
    python pipeline.py --channel "@MrBeast" --skip-scrape --augment 5 \
        --prompt "Keep layout, replace person with suited professional"

    # Augment a specific thumbnail by rank
    python pipeline.py --channel "@hubermanlab" --scrape 30 --rank 1 \
        --prompt "Replace the person, keep the educational clean aesthetic"
"""

import argparse
import json
import sys
from pathlib import Path

from scrape_channel_thumbnails import scrape_channel
from kie_image_to_image import augment_thumbnail, augment_folder, STYLE_PRESETS

OUTPUT_DIR = Path("output")


def load_metadata(channel: str) -> list[dict]:
    """Load cached metadata for a channel."""
    handle = channel.lstrip("@").split("/")[-1]
    meta_path = Path("thumbnails") / handle / "metadata.json"
    if not meta_path.exists():
        return []
    return json.loads(meta_path.read_text(encoding="utf-8"))


def pick_top_thumbnails(metadata: list[dict], n: int, rank: int = None) -> list[dict]:
    """Return top n thumbnails sorted by views, or a specific rank."""
    sorted_by_views = sorted(metadata, key=lambda v: v.get("views", 0), reverse=True)
    if rank is not None:
        idx = rank - 1  # 1-indexed → 0-indexed
        return [sorted_by_views[idx]] if idx < len(sorted_by_views) else []
    return sorted_by_views[:n]


def main():
    parser = argparse.ArgumentParser(
        description="Scrape + augment top YouTube thumbnails with Kie.ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Style presets:
  {', '.join(STYLE_PRESETS.keys())}

Examples:
  # Full pipeline — top 3 most-viewed thumbnails from @MrBeast
  python pipeline.py \\
    --channel "@MrBeast" \\
    --scrape 30 --augment 3 \\
    --prompt "Replace person with suited man, keep energy and colors" \\
    --style mrbeast-energy

  # Only augment (already scraped)
  python pipeline.py \\
    --channel "@nickosaraev" --skip-scrape --augment 5 \\
    --prompt "Keep dark background and orange lighting, swap person to suited man"

  # Specific rank
  python pipeline.py \\
    --channel "@hubermanlab" --scrape 50 --rank 1 \\
    --prompt "Professional man in suit, keep clean educational look"
        """,
    )
    parser.add_argument("--channel", "-c", required=True,
                        help="YouTube channel handle or URL")
    parser.add_argument("--scrape", type=int, default=20, metavar="N",
                        help="Number of videos to scrape for thumbnails (default: 20)")
    parser.add_argument("--augment", type=int, default=3, metavar="N",
                        help="Number of top thumbnails to augment (default: 3)")
    parser.add_argument("--rank", type=int,
                        help="Augment only the Nth most-viewed thumbnail (1 = top)")
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip scraping, use already-downloaded thumbnails")
    parser.add_argument("--prompt", "-p", required=True,
                        help="Augmentation prompt for Kie.ai")
    parser.add_argument("--style", choices=list(STYLE_PRESETS.keys()),
                        help="Apply a style preset to the prompt")
    parser.add_argument("--api-key", type=str,
                        help="Kie.ai API key (overrides KIE_AI_API_KEY env var)")
    args = parser.parse_args()

    # Step 1: Scrape thumbnails
    if not args.skip_scrape:
        print(f"\n{'='*60}")
        print(f"STEP 1: Scraping {args.scrape} thumbnails from {args.channel}")
        print(f"{'='*60}")
        scrape_channel(channel=args.channel, limit=args.scrape, sort="date")
    else:
        print("Skipping scrape (--skip-scrape)")

    # Step 2: Load metadata and pick best thumbnails by view count
    print(f"\n{'='*60}")
    print("STEP 2: Selecting best-performing thumbnails by view count")
    print(f"{'='*60}")

    metadata = load_metadata(args.channel)
    if not metadata:
        print("No metadata found. Run scraping first.")
        sys.exit(1)

    targets = pick_top_thumbnails(metadata, n=args.augment, rank=args.rank)
    if not targets:
        print("No thumbnails to augment.")
        sys.exit(1)

    print(f"Selected {len(targets)} thumbnail(s) to augment:")
    for i, v in enumerate(targets, 1):
        views = f"{v.get('views', 0):,}"
        print(f"  #{i} | {views:>12} views | {v.get('title', '?')[:55]}")

    # Step 3: Augment with Kie.ai
    print(f"\n{'='*60}")
    print(f"STEP 3: Augmenting with Kie.ai")
    print(f"{'='*60}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for i, video in enumerate(targets, 1):
        thumb_path = video.get("thumbnail_path")
        if not thumb_path or not Path(thumb_path).exists():
            print(f"  [{i}] Thumbnail file not found: {thumb_path}")
            continue

        out_path = OUTPUT_DIR / f"augmented_{i:02d}_{Path(thumb_path).stem}_kie.png"
        result = augment_thumbnail(
            source_path=thumb_path,
            prompt=args.prompt,
            output_path=out_path,
            style=args.style,
            api_key=args.api_key,
        )
        if result:
            results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"DONE: {len(results)}/{len(targets)} thumbnails augmented")
    print(f"{'='*60}")
    for r in results:
        print(f"  ✓ {r}")


if __name__ == "__main__":
    main()
