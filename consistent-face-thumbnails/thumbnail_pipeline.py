#!/usr/bin/env python3
"""
Consistent-face thumbnail studio (Kie AI, gpt-image-2-image-to-image).

Make YouTube / LinkedIn thumbnails that show the SAME face every time
(character consistency) plus premium 3D "infographic" cards - all from one
reference photo of yourself and, optionally, a reference of your own brand
colors and style.

How the consistency works: the model is given your face photo as an actual
image input (not a text description), and the prompt tells it to keep your
face unaltered. The result looks like you, in a new scene, with the headline
rendered in a clean bold style you can rebrand to your own colors.

Two modes:
  --mode headline     you + a headline, high-trust talking-head style
  --mode infographic  a photographed 3D data card (optionally with your face),
                      driven by a JSON layer file (see prompts/infographic-template.txt)

Cost: each generation is ~10 Kie credits. This script is DRY-RUN BY DEFAULT -
it resolves inputs and prints the exact request without spending a credit.
Add --live to actually generate. See README for the $5 = 100 images math.

Setup:
  1. pip install -r requirements.txt
  2. cp .env.example .env  and put your Kie key in it (get one at https://kie.ai)
  3. Drop a photo of your face at assets/your-face.png (or pass --face <path>)
  4. (optional) Drop a brand/style reference at assets/your-brand-style.png

Usage (dry-run, no credits):
  python thumbnail_pipeline.py generate \
    --headline "The One Habit That 10x'd My Output" \
    --slug one-habit \
    --face assets/your-face.png

Match your own brand instead of the default white+gold text:
  python thumbnail_pipeline.py generate \
    --headline "Ship Faster" --slug ship-faster \
    --face assets/your-face.png \
    --brand-ref assets/your-brand-style.png \
    --brand-colors "#0B5FFF,#FFFFFF" \
    --brand-notes "clean, minimal, tech-startup feel"

Add --live to actually call Kie and spend ~10 credits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
COST_LOG = OUTPUT_DIR / "generation-log.jsonl"

BASE_URL = "https://api.kie.ai/api/v1/jobs"
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"
DEFAULT_MODEL = "gpt-image-2-image-to-image"
CREDITS_PER_GEN = 10.0

# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #

# This is the phrase that keeps YOUR face the same in every image. It is the
# single most important line in the whole pipeline - it is why the person in
# the output looks like the person in your reference photo.
FACE_LOCK = (
    "The subject is the exact person in the reference photo: keep their EXACT "
    "face, hair, and natural expression completely unaltered - do not beautify, "
    "restyle, age, slim, or augment their facial features in any way. It must be "
    "unmistakably the same person."
)

# Default headline / text treatment. Kept simple and high-contrast. You can
# override the colors and feel with --brand-colors / --brand-notes / --brand-ref
# so the thumbnail matches YOUR brand instead of this default.
DEFAULT_TEXT_STYLE = (
    "Render the headline \"{headline}\" as the dominant element: bold condensed "
    "uppercase, mostly white with the key words in a bright accent color, subtle "
    "3D drop shadow, one short underline accent under the last line. Big, "
    "punchy, readable on a phone at small size."
)

SCENE = (
    "Photorealistic. Backdrop: a clean, softly blurred professional setting with "
    "flattering light. Confident, warm, credible presence. No clutter, no "
    "watermark, no small subtitles."
)

HEADLINE_TEMPLATE = FACE_LOCK + " " + SCENE + " " + DEFAULT_TEXT_STYLE


def brand_clause(args: argparse.Namespace) -> str:
    parts = []
    if args.brand_colors:
        parts.append(
            f"Use this brand color palette for the text and accents: {args.brand_colors}. "
            "Override the default white+accent scheme with these colors."
        )
    if args.brand_notes:
        parts.append(f"Overall visual style should feel: {args.brand_notes}.")
    if args.brand_ref:
        parts.append(
            "A brand-style reference image is also provided: match its color "
            "palette, typography feel, and overall mood so the thumbnail looks "
            "on-brand for that creator."
        )
    return (" " + " ".join(parts)) if parts else ""


def build_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8").strip() + brand_clause(args)
    if args.prompt:
        return args.prompt + brand_clause(args)
    if args.mode == "infographic":
        raise SystemExit("--mode infographic requires --prompt-file (see prompts/infographic-template.txt)")
    return HEADLINE_TEMPLATE.format(headline=args.headline) + brand_clause(args)


# --------------------------------------------------------------------------- #
# Kie API
# --------------------------------------------------------------------------- #

def api_key() -> str:
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("KIE_AI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "KIE_AI_API_KEY not set. Copy .env.example to .env and paste your key "
            "from https://kie.ai. (Never commit your .env - it is gitignored.)"
        )
    return key


def upload_local_image(path: Path) -> str:
    """Upload a local file to Kie's temp file host and return its public URL.

    Kie needs image inputs as URLs. This host auto-deletes files after ~3 days,
    which is fine - the URL only has to live long enough for the generation call.
    Note it is a DIFFERENT host from the jobs API (api.kie.ai).
    """
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    with path.open("rb") as f:
        resp = requests.post(
            UPLOAD_URL,
            headers={"Authorization": f"Bearer {api_key()}"},
            files={"file": (path.name, f, mime)},
            data={"uploadPath": "images/thumbnail-refs", "fileName": path.name},
            timeout=120,
        )
    resp.raise_for_status()
    url = (resp.json().get("data") or {}).get("downloadUrl")
    if not url:
        raise RuntimeError(f"Upload returned no downloadUrl: {resp.text[:200]}")
    print(f"  uploaded {path.name}")
    return url


def resolve_inputs(paths: list[str], urls: list[str], live: bool) -> list[str]:
    inputs: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"  WARNING reference not found: {path}", file=sys.stderr)
            continue
        inputs.append(upload_local_image(path) if live else f"UPLOAD_PENDING::{path}")
    inputs.extend(urls)
    return inputs


def build_payload(prompt: str, image_inputs: list[str], model: str, aspect: str, resolution: str) -> dict:
    # gpt-image-2-* expects `input_urls`. Passing the wrong key silently degrades
    # to text-to-image (the model never sees your face) and you get a generic
    # stranger. This one detail is the difference between "looks like me" and not.
    input_obj: dict[str, Any] = {"prompt": prompt, "aspect_ratio": aspect, "resolution": resolution}
    if model.startswith("gpt-image"):
        input_obj["input_urls"] = image_inputs
    else:
        input_obj["output_format"] = "png"
        input_obj["image_input"] = image_inputs
    return {"model": model, "input": input_obj}


def create_task(payload: dict) -> str:
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/createTask", json=payload, headers=headers, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"Kie createTask error: {data}")
    return data["data"]["taskId"]


def poll_task(task_id: str, max_attempts: int = 60, interval: int = 5) -> dict | list | None:
    headers = {"Authorization": f"Bearer {api_key()}"}
    for attempt in range(max_attempts):
        resp = requests.get(f"{BASE_URL}/recordInfo", params={"taskId": task_id}, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()["data"]
        state = data.get("state")
        print(f"  [{attempt + 1}/{max_attempts}] state={state}")
        if state == "success":
            result = data.get("resultJson")
            return json.loads(result) if isinstance(result, str) else result
        if state == "fail":
            print(f"  FAILED: {data.get('failCode')} - {data.get('failMsg')}", file=sys.stderr)
            return None
        time.sleep(interval)
    print("  TIMEOUT polling Kie task", file=sys.stderr)
    return None


def extract_url(result: dict | list | None) -> str | None:
    if isinstance(result, list) and result:
        return str(result[0])
    if isinstance(result, dict):
        for key in ("resultUrls", "images", "url", "image_url", "output"):
            val = result.get(key)
            if isinstance(val, list) and val:
                return str(val[0])
            if isinstance(val, str):
                return val
    return None


def log_generation(entry: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Command
# --------------------------------------------------------------------------- #

def generate(args: argparse.Namespace) -> int:
    prompt = build_prompt(args)
    ref_paths = list(args.face or []) + list(args.style_ref or [])
    if args.brand_ref:
        ref_paths.append(args.brand_ref)
    image_inputs = resolve_inputs(ref_paths, list(args.ref_url or []), args.live)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_png = OUTPUT_DIR / f"{args.slug[:40].rstrip('-')}-{stamp}.png"
    payload = build_payload(prompt, image_inputs, args.model, args.aspect_ratio, args.resolution)

    if not args.live:
        print("DRY RUN - no credits spent. Review the request below, then re-run with --live.\n")
        print(json.dumps({
            "mode": args.mode,
            "slug": args.slug,
            "estimated_credits": CREDITS_PER_GEN,
            "output": str(out_png),
            "createTask_payload": payload,
        }, indent=2, ensure_ascii=False))
        if any(i.startswith("UPLOAD_PENDING::") for i in image_inputs):
            print("\nNote: local images show as UPLOAD_PENDING; with --live they are uploaded first.")
        if not image_inputs:
            print("\nWARNING: no reference image. For a consistent face you MUST pass --face <your photo>.")
        return 0

    if not image_inputs:
        print("ERROR: --live needs at least one reference. Pass --face <your photo>.", file=sys.stderr)
        return 2

    print(f"Creating Kie task (model={args.model}, ~{CREDITS_PER_GEN} credits)...")
    task_id = create_task(payload)
    print(f"Task: {task_id}\nPolling...")
    result = poll_task(task_id)
    result_url = extract_url(result)

    saved = None
    if result_url:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png.write_bytes(requests.get(result_url, timeout=60).content)
        saved = out_png
        print(f"Saved: {saved}")
    else:
        print("No result URL returned.", file=sys.stderr)

    log_generation({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slug": args.slug, "mode": args.mode, "model": args.model,
        "credits": CREDITS_PER_GEN, "task_id": task_id,
        "prompt": prompt, "image_inputs": image_inputs,
        "result_url": result_url, "output": str(saved) if saved else None,
    })
    return 0 if saved else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Consistent-face thumbnail studio (Kie AI)")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Generate a thumbnail (dry-run unless --live)")
    g.add_argument("--mode", default="headline", choices=["headline", "infographic"])
    g.add_argument("--headline", default="", help="Headline text (headline mode)")
    g.add_argument("--slug", required=True, help="Short name for the output file")
    g.add_argument("--face", action="append", help="Your face photo (repeatable). Required for a consistent face.")
    g.add_argument("--style-ref", action="append", help="Optional text/typography reference image (repeatable)")
    g.add_argument("--brand-ref", help="Optional brand-style reference image (your colors/look)")
    g.add_argument("--brand-colors", help="Optional brand colors, e.g. \"#0B5FFF,#FFFFFF\"")
    g.add_argument("--brand-notes", help="Optional free-text brand feel, e.g. \"clean, minimal, tech\"")
    g.add_argument("--ref-url", action="append", help="Already-hosted reference image URL (repeatable)")
    g.add_argument("--prompt", help="Override the prompt entirely")
    g.add_argument("--prompt-file", help="Read the prompt from a file (required for --mode infographic)")
    g.add_argument("--model", default=DEFAULT_MODEL)
    g.add_argument("--aspect-ratio", default="16:9")
    g.add_argument("--resolution", default="2K")
    g.add_argument("--live", action="store_true", help="Actually call Kie and spend ~10 credits")
    g.set_defaults(func=generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
