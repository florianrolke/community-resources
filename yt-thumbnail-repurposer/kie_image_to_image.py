#!/usr/bin/env python3
"""
Kie.ai Image-to-Image Thumbnail Augmentation

Takes a source YouTube thumbnail and uses Kie.ai's Nano Banana 2 model
to regenerate it with your face, brand colors, and style — while keeping
the layout, energy, and composition that made the original perform well.

Usage:
    # Augment a single thumbnail
    python kie_image_to_image.py --source thumbnails/mrBeast/abc123__title.jpg \
        --prompt "Replace the person with a man in a dark suit, keep dramatic orange backlighting"

    # Batch augment all thumbnails in a folder
    python kie_image_to_image.py --folder thumbnails/mrBeast/ \
        --prompt "Professional man in suit, same dramatic lighting and composition" \
        --limit 5

    # Use a style preset
    python kie_image_to_image.py --source path/to/thumb.jpg --style cinematic-dark

Env vars (.env file):
    KIE_AI_API_KEY   — your Kie.ai API key (get one at kie.ai)

Output:
    output/<source_filename>_kie.png
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────

KIE_AI_BASE = "https://api.kie.ai/api/v1/jobs"
OUTPUT_DIR = Path("output")

# Style presets — pre-written prompt suffixes for common thumbnail aesthetics
STYLE_PRESETS = {
    "cinematic-dark": (
        "Dramatic cinematic lighting, deep shadows, high contrast, dark background "
        "with warm orange-amber backlight, professional production quality, 4K sharp"
    ),
    "mrbeast-energy": (
        "Bright bold colors, high energy, vibrant background, expressive emotion, "
        "clean composition, professional YouTube thumbnail style"
    ),
    "educational": (
        "Clean minimalist background, professional lighting, clear and readable layout, "
        "trustworthy and authoritative feel, business professional"
    ),
    "tech-ai": (
        "Dark background with neon blue/purple accents, futuristic AI aesthetic, "
        "circuit patterns, glowing elements, premium tech brand feel"
    ),
}


# ── Kie.ai API ─────────────────────────────────────────────────────────────────

def image_to_base64(image_path: str | Path) -> str:
    """Read an image file and return its base64 encoding."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def create_task(
    prompt: str,
    source_image_path: str | Path = None,
    source_image_url: str = None,
    model: str = "nano-banana-2",
    aspect_ratio: str = "16:9",
    resolution: str = "4K",
    api_key: str = None,
) -> str | None:
    """
    Submit an image generation (or image-to-image) task to Kie.ai.

    Provide either source_image_path (local file) or source_image_url.
    If neither is provided, runs as text-to-image.

    Returns: task_id (str) or None on failure
    """
    key = api_key or os.getenv("KIE_AI_API_KEY")
    if not key:
        print("ERROR: KIE_AI_API_KEY not found. Set it in .env or pass --api-key")
        return None

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Build image_input list
    image_input = []
    if source_image_path:
        b64 = image_to_base64(source_image_path)
        ext = Path(source_image_path).suffix.lstrip(".").lower() or "jpeg"
        mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
        image_input.append({"type": "base64", "data": b64, "mime_type": mime})
    elif source_image_url:
        image_input.append({"type": "url", "url": source_image_url})

    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "output_format": "png",
            "image_input": image_input,
        },
    }

    print(f"  Submitting to Kie.ai ({model}, {resolution}, {aspect_ratio})...")
    print(f"  Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    if image_input:
        print(f"  Source image: {'base64 upload' if source_image_path else source_image_url}")

    try:
        resp = requests.post(
            f"{KIE_AI_BASE}/createTask",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 200:
            print(f"  ERROR from Kie.ai: {data.get('message', data)}")
            return None

        task_id = data["data"]["taskId"]
        print(f"  Task created: {task_id}")
        return task_id

    except requests.exceptions.HTTPError as e:
        print(f"  HTTP error: {e.response.status_code} — {e.response.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

    return None


def poll_task(
    task_id: str,
    api_key: str = None,
    max_wait_seconds: int = 300,
    poll_interval: int = 5,
) -> dict | None:
    """
    Poll Kie.ai until the task completes or times out.

    Returns the result dict (with image URL) or None.
    """
    key = api_key or os.getenv("KIE_AI_API_KEY")
    headers = {"Authorization": f"Bearer {key}"}
    max_attempts = max_wait_seconds // poll_interval

    print(f"  Waiting for result", end="", flush=True)

    for attempt in range(max_attempts):
        time.sleep(poll_interval)
        print(".", end="", flush=True)

        try:
            resp = requests.get(
                f"{KIE_AI_BASE}/recordInfo",
                params={"taskId": task_id},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            state = data.get("state", "pending")

            if state == "success":
                print(" Done!")
                result = data.get("resultJson")
                if isinstance(result, str):
                    result = json.loads(result)
                return result

            elif state == "fail":
                print(f" FAILED")
                print(f"  Fail code: {data.get('failCode')} — {data.get('failMsg')}")
                return None

        except Exception as e:
            print(f"\n  Poll error: {e}")
            continue

    print(f"\n  TIMEOUT after {max_wait_seconds}s")
    return None


def extract_image_url(result: dict | list) -> str | None:
    """Extract the image URL from Kie.ai's result payload."""
    if isinstance(result, list):
        result = result[0] if result else {}

    if isinstance(result, str):
        return result

    # Try common key names
    for key in ("url", "image_url", "output", "images", "imageUrl", "image"):
        val = result.get(key)
        if val:
            return val[0] if isinstance(val, list) else val

    return None


def download_result(image_url: str, save_path: Path) -> bool:
    """Download the generated image to save_path."""
    try:
        resp = requests.get(image_url, timeout=60)
        resp.raise_for_status()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        return False


# ── High-level pipeline ─────────────────────────────────────────────────────────

def augment_thumbnail(
    source_path: str | Path,
    prompt: str,
    output_path: str | Path = None,
    style: str = None,
    api_key: str = None,
) -> Path | None:
    """
    Full image-to-image pipeline for a single thumbnail.

    1. Upload source image to Kie.ai with prompt
    2. Poll for completion
    3. Download result
    4. Return output path

    Args:
        source_path:  Path to source thumbnail (.jpg/.png)
        prompt:       What to change / keep in the thumbnail
        output_path:  Where to save the result (auto-generated if None)
        style:        Optional style preset name (see STYLE_PRESETS)
        api_key:      Kie.ai API key (uses KIE_AI_API_KEY env var if not set)

    Returns:
        Path to generated image, or None if failed
    """
    source_path = Path(source_path)
    if not source_path.exists():
        print(f"ERROR: Source image not found: {source_path}")
        return None

    # Append style preset to prompt
    full_prompt = prompt
    if style and style in STYLE_PRESETS:
        full_prompt = f"{prompt}. {STYLE_PRESETS[style]}"
        print(f"  Style preset: {style}")

    print(f"\nAugmenting: {source_path.name}")

    # Submit task
    task_id = create_task(
        prompt=full_prompt,
        source_image_path=source_path,
        api_key=api_key,
    )
    if not task_id:
        return None

    # Poll for result
    result = poll_task(task_id, api_key=api_key)
    if not result:
        return None

    # Extract image URL
    image_url = extract_image_url(result)
    if not image_url:
        print(f"  No image URL in result: {result}")
        return None

    print(f"  Result URL: {image_url[:80]}...")

    # Determine output path
    if output_path is None:
        stem = source_path.stem
        out_dir = OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{stem}_kie.png"

    output_path = Path(output_path)

    # Download
    if download_result(image_url, output_path):
        size_kb = output_path.stat().st_size // 1024
        print(f"  Saved: {output_path} ({size_kb} KB)")
        return output_path
    return None


def augment_folder(
    folder: str | Path,
    prompt: str,
    limit: int = None,
    style: str = None,
    api_key: str = None,
) -> list[Path]:
    """
    Batch augment all thumbnails in a folder.

    Args:
        folder:   Path to folder containing thumbnail images
        prompt:   Augmentation prompt applied to all thumbnails
        limit:    Max number of thumbnails to process
        style:    Optional style preset
        api_key:  Kie.ai API key

    Returns:
        List of output paths
    """
    folder = Path(folder)
    if not folder.exists():
        print(f"ERROR: Folder not found: {folder}")
        return []

    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    thumbnails = [f for f in sorted(folder.iterdir()) if f.suffix.lower() in extensions]

    if limit:
        thumbnails = thumbnails[:limit]

    print(f"Processing {len(thumbnails)} thumbnails from {folder}")
    results = []

    for i, thumb in enumerate(thumbnails, 1):
        print(f"\n[{i}/{len(thumbnails)}] {thumb.name}")
        out = augment_thumbnail(thumb, prompt, style=style, api_key=api_key)
        if out:
            results.append(out)

    print(f"\n{'='*50}")
    print(f"Done. {len(results)}/{len(thumbnails)} augmented successfully.")
    for r in results:
        print(f"  → {r}")

    return results


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Augment YouTube thumbnails with Kie.ai image-to-image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Style presets (--style):
  {chr(10).join(f'  {k}' for k in STYLE_PRESETS)}

Examples:
  # Augment a single thumbnail
  python kie_image_to_image.py \\
    --source thumbnails/channel/abc123__video-title.jpg \\
    --prompt "Replace the person with a man in a dark suit"

  # Use a style preset
  python kie_image_to_image.py \\
    --source thumbnails/channel/abc123__video-title.jpg \\
    --prompt "Keep the layout, replace the person" \\
    --style cinematic-dark

  # Batch augment a whole channel's thumbnails
  python kie_image_to_image.py \\
    --folder thumbnails/mrBeast/ \\
    --prompt "Professional man in suit, same composition and energy" \\
    --limit 5 \\
    --style mrbeast-energy
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", "-s", type=str, help="Path to single source thumbnail")
    group.add_argument("--folder", "-f", type=str, help="Folder of thumbnails to batch process")

    parser.add_argument("--prompt", "-p", required=True,
                        help="What to change/preserve in the thumbnail")
    parser.add_argument("--style", choices=list(STYLE_PRESETS.keys()),
                        help="Apply a style preset")
    parser.add_argument("--limit", "-n", type=int,
                        help="Max thumbnails to process in batch mode")
    parser.add_argument("--output", "-o", type=str,
                        help="Output path (single mode) or directory (batch mode)")
    parser.add_argument("--api-key", type=str,
                        help="Kie.ai API key (overrides KIE_AI_API_KEY env var)")

    args = parser.parse_args()

    api_key = args.api_key or os.getenv("KIE_AI_API_KEY")
    if not api_key:
        print("ERROR: Set KIE_AI_API_KEY in .env or pass --api-key")
        sys.exit(1)

    if args.source:
        augment_thumbnail(
            source_path=args.source,
            prompt=args.prompt,
            output_path=args.output,
            style=args.style,
            api_key=api_key,
        )
    else:
        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        augment_folder(
            folder=args.folder,
            prompt=args.prompt,
            limit=args.limit,
            style=args.style,
            api_key=api_key,
        )


if __name__ == "__main__":
    main()
