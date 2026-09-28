#!/usr/bin/env python3
"""
Gemini Face Swap - replace any face in a YouTube thumbnail with yours.

Passes your reference photo + the source thumbnail to Gemini's image model
in a single multimodal call. Works where text-to-image fails because the
model actually sees your face rather than guessing from a description.

Usage:
    # Single thumbnail
    python gemini_faceswap.py \
        --source thumbnails/channel/abc123__title.jpg \
        --reference my_photo.jpg

    # Batch - swap face in every thumbnail in a folder
    python gemini_faceswap.py \
        --folder thumbnails/channel/ \
        --reference my_photo.jpg \
        --limit 5

    # Extra instructions (pose, zoom, expression)
    python gemini_faceswap.py \
        --source thumb.jpg --reference me.jpg \
        --prompt "person smiling at camera, zoomed in close"

Env vars (.env):
    GOOGLE_GEMINI_API_KEY   - Gemini API key (console.cloud.google.com)

Cost: ~$0.15-0.25 per image
"""

import argparse
import base64
import io
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

load_dotenv()

OUTPUT_DIR = Path("output")

# Try newer model first, fall back to older one
MODELS = [
    "gemini-2.0-flash-preview-image-generation",
    "gemini-3-pro-image-preview",
]

DEFAULT_IDENTITY = (
    "long dark hair tied back in a ponytail or bun (never loose, never short), "
    "prominent goatee/chin beard, wearing a suit with jacket and lapels"
)

PROMPT_TEMPLATE = """IMAGE 1: Reference photo of MY face. I have {identity}.
IMAGE 2: The YouTube thumbnail to edit.

TASK: Replace the face in the thumbnail with MY face from IMAGE 1.

RULES:
1. FACE: Use my exact face from IMAGE 1. Match my facial features precisely.
2. HAIR: My hair is always tied back in a ponytail or bun - never loose, never short.
3. WARDROBE: Replace the original person's clothing with a suit (jacket, lapels). Never keep a hoodie or t-shirt.
4. SKIN: Match scene lighting/color grade but keep natural smooth skin. No texture transfer from original.
5. POSE: Match the original head angle and camera focal length exactly.
6. EDGES: Blend naturally - no hard seams, no artifacts, no lighting discontinuities at face boundary.
7. IDENTITY: I must be clearly recognizable from IMAGE 1.

Keep every other pixel identical: background, text overlays, graphics, props, composition, color grade.
Output in 16:9 format.

{extra_prompt}"""


def load_image(path_or_url, max_size=(1280, 720)):
    if str(path_or_url).startswith("http"):
        r = requests.get(str(path_or_url), timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
    else:
        img = Image.open(str(path_or_url))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img


def faceswap(source, reference, output_path=None, identity=DEFAULT_IDENTITY,
             extra_prompt="", api_key=None):
    """
    Swap the face in source thumbnail with the face from reference photo.

    Args:
        source:       Path or URL to source thumbnail
        reference:    Path to your reference photo (clear face, facing camera)
        output_path:  Where to save result (auto-generated if None)
        identity:     Your appearance description for the prompt
        extra_prompt: Extra instructions e.g. "person smiling at camera, zoomed in"
        api_key:      Gemini API key (falls back to GOOGLE_GEMINI_API_KEY)

    Returns:
        Path to saved image, or None on failure
    """
    key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not key:
        print("ERROR: Set GOOGLE_GEMINI_API_KEY in .env or pass --api-key")
        return None

    source_path = Path(source)
    ref_path = Path(reference)

    if not source_path.exists():
        print(f"ERROR: Source not found: {source_path}")
        return None
    if not ref_path.exists():
        print(f"ERROR: Reference not found: {ref_path}")
        return None

    print(f"\nFace-swapping: {source_path.name}")
    print(f"Reference:     {ref_path.name}")

    ref_img = load_image(ref_path, max_size=(400, 400))
    src_img = load_image(source_path, max_size=(1280, 720))
    prompt = PROMPT_TEMPLATE.format(identity=identity, extra_prompt=extra_prompt)

    client = genai.Client(api_key=key)
    response = None

    for model in MODELS:
        try:
            print(f"  Trying {model}...")
            response = client.models.generate_content(
                model=model,
                contents=[ref_img, src_img, prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            print(f"  Model: {model}")
            break
        except Exception as e:
            print(f"  {model} failed: {e}")

    if response is None:
        print("  All models failed")
        return None

    result_img = None
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                data = part.inline_data.data
                if data:
                    img_bytes = base64.b64decode(data) if isinstance(data, str) else data
                    result_img = Image.open(io.BytesIO(img_bytes))
                    break
            elif hasattr(part, "text") and part.text:
                print(f"  Model note: {part.text[:200]}")

    if result_img is None:
        print("  No image returned from Gemini")
        return None

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"{source_path.stem}_faceswap.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_img.save(output_path)
    print(f"  Saved: {output_path} ({output_path.stat().st_size // 1024} KB, {result_img.size})")
    return output_path


def batch_faceswap(folder, reference, limit=None, identity=DEFAULT_IDENTITY,
                   extra_prompt="", api_key=None):
    """Swap faces in all thumbnails in a folder."""
    folder = Path(folder)
    if not folder.exists():
        print(f"ERROR: Folder not found: {folder}")
        return []

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = [f for f in sorted(folder.iterdir()) if f.suffix.lower() in exts]
    if limit:
        files = files[:limit]

    print(f"Processing {len(files)} thumbnails from {folder}")
    results = []

    for i, f in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}]")
        out = faceswap(f, reference, identity=identity, extra_prompt=extra_prompt, api_key=api_key)
        if out:
            results.append(out)

    print(f"\nDone. {len(results)}/{len(files)} succeeded.")
    for r in results:
        print(f"  -> {r}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Face-swap YouTube thumbnails using Gemini multimodal generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single thumbnail
  python gemini_faceswap.py --source thumbnails/channel/video.jpg --reference me.jpg

  # Smiling at camera, zoomed in
  python gemini_faceswap.py --source thumb.jpg --reference me.jpg \\
      --prompt "person facing camera, smiling warmly, zoomed in waist-up"

  # Batch - top 5 from a channel
  python gemini_faceswap.py --folder thumbnails/mrBeast/ --reference me.jpg --limit 5
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", "-s", help="Source thumbnail path or URL")
    group.add_argument("--folder", "-f", help="Folder of thumbnails (batch mode)")

    parser.add_argument("--reference", "-r", required=True,
                        help="Your reference photo (clear face, ideally facing camera)")
    parser.add_argument("--output", "-o", help="Output path (single) or directory (batch)")
    parser.add_argument("--identity", default=DEFAULT_IDENTITY,
                        help="Your appearance description for the prompt")
    parser.add_argument("--prompt", "-p", default="",
                        help="Extra instructions: pose, zoom, expression etc.")
    parser.add_argument("--limit", "-n", type=int, help="Max thumbnails in batch mode")
    parser.add_argument("--api-key", help="Gemini API key (overrides env var)")

    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GOOGLE_GEMINI_API_KEY in .env or pass --api-key")
        sys.exit(1)

    if args.source:
        result = faceswap(
            source=args.source,
            reference=args.reference,
            output_path=args.output,
            identity=args.identity,
            extra_prompt=args.prompt,
            api_key=api_key,
        )
        sys.exit(0 if result else 1)
    else:
        results = batch_faceswap(
            folder=args.folder,
            reference=args.reference,
            limit=args.limit,
            identity=args.identity,
            extra_prompt=args.prompt,
            api_key=api_key,
        )
        sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
