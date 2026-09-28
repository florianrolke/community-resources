#!/usr/bin/env python3
"""
Kie AI text-to-image Meta-ad static generator (generic, reusable).

WHAT THIS DOES
--------------
Generates Meta advertisement static images with the headline text baked directly
into the image, using the Kie AI Jobs API (model `seedream/5-pro-text-to-image`).

This is a pure TEXT-TO-IMAGE approach: each ad is described entirely by a text
prompt (scene description + the exact uppercase headline to render), with NO
reference image. The model paints both the scene and the typography. It works
well for typographic ad statics -- a photorealistic scene plus a solid headline
bar at the top -- because you can dictate the exact words to render.

THE CREDIT COST
---------------
Each generated image costs roughly ~7 credits on Kie at the default settings
(3:4 portrait, basic/1K quality, PNG). A batch of ten ads is therefore ~70
credits. Generation is a PAID call, so this script is DRY-RUN by default: it
prints the exact payloads it would send and makes no paid request until you
pass `--live`.

RETRY SAFETY (the whole point of `--only`)
------------------------------------------
Text-in-image models occasionally misspell a word (a classic pitfall: the word
"LEAK" rendering as "LEEK"). When that happens you want to regenerate ONLY the
one bad image, not re-bill the entire set. `--only <substr>` filters the run to
ads whose `stem` contains the substring, so a single retry never re-charges the
images that already came out right. Combine it with a stronger spelling hint in
that ad's prompt (e.g. "the word is LEAK spelled L-E-A-K, not LEEK") and re-run
just that one.

API PATTERN (Kie AI Jobs API)
-----------------------------
  Base:  https://api.kie.ai/api/v1/jobs
  POST /createTask   -> returns data.taskId
  GET  /recordInfo   -> poll ?taskId=... until state == success | fail
Then extract the result URL, download the PNG, and write a `.task.json` sidecar
next to each PNG recording task_id, model, prompt, credits, duration, result_url.

CONFIGURATION
-------------
  - `KIE_AI_API_KEY` is read from a local `.env` via python-dotenv. It is never
    printed (see `redact()`); only a redacted preview ever reaches stdout.
  - Ad definitions live in an external `prompts.json` (list of
    {label, stem, prompt}) so no ad copy is hardcoded in this file. Copy
    `prompts.example.json` to `prompts.json` and edit it.

CLI
---
  python generate_ads.py                       # DRY RUN (default): prints payloads
  python generate_ads.py --live                # execute the paid generations
  python generate_ads.py --only cheap-part     # run only ads whose stem matches
  python generate_ads.py --out ./output        # output directory (default ./output)
  python generate_ads.py --prompts ./prompts.json
  python generate_ads.py --aspect-ratio 4:5 --quality basic --output-format png

WINDOWS-SAFE
------------
UTF-8 stdout/stderr reconfigure and ASCII-only prints, so it runs on the cp1252
Windows console without UnicodeEncodeError.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values

if sys.platform == "win32":
    # cp1252 consoles choke on non-ASCII; force UTF-8 and replace on error.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SCRIPT_DIR = Path(__file__).resolve().parent

# Local .env holding KIE_AI_API_KEY (never committed; see .env.example).
ENV_PATH = SCRIPT_DIR / ".env"

# Kie AI Jobs API.
BASE_URL = "https://api.kie.ai/api/v1/jobs"
MODEL = "seedream/5-pro-text-to-image"

# Defaults (all overridable on the CLI).
DEFAULT_ASPECT_RATIO = "3:4"    # portrait; 4:5 also common for Meta feed
DEFAULT_QUALITY = "basic"       # basic == 1K
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_PROMPTS = SCRIPT_DIR / "prompts.json"
DEFAULT_OUT = SCRIPT_DIR / "output"


# --------------------------------------------------------------------------- #
# Key loading (never printed)
# --------------------------------------------------------------------------- #
def load_api_key(env_path: Path = ENV_PATH) -> str:
    """Load KIE_AI_API_KEY from the local .env. Raises if missing."""
    if env_path.exists():
        values = dotenv_values(env_path)
        key = (values.get("KIE_AI_API_KEY") or "").strip().strip('"').strip("'")
        if key:
            print(f"  key loaded from: {env_path.name} (value redacted)")
            return key
    raise RuntimeError(
        f"KIE_AI_API_KEY not found. Create {env_path.name} with a single line:\n"
        f"    KIE_AI_API_KEY=your_key_here\n"
        f"(get a key at kie.ai). See .env.example."
    )


def redact(key: str) -> str:
    """Return a safe-to-print preview of a secret; never reveals the full key."""
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


# --------------------------------------------------------------------------- #
# Prompt loading
# --------------------------------------------------------------------------- #
def load_prompts(prompts_path: Path) -> list[dict]:
    """Load ad definitions from prompts.json (list of {label, stem, prompt})."""
    if not prompts_path.exists():
        raise RuntimeError(
            f"prompts file not found: {prompts_path}\n"
            f"Copy prompts.example.json to prompts.json and edit it."
        )
    raw = prompts_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise RuntimeError("prompts.json must be a JSON list of ad objects.")

    ads: list[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise RuntimeError(f"prompts.json entry {i} is not an object.")
        missing = [k for k in ("label", "stem", "prompt") if not item.get(k)]
        if missing:
            raise RuntimeError(
                f"prompts.json entry {i} missing required field(s): {missing}. "
                f"Each entry needs label, stem, prompt."
            )
        ads.append({"label": item["label"], "stem": item["stem"], "prompt": item["prompt"]})

    stems = [a["stem"] for a in ads]
    dupes = {s for s in stems if stems.count(s) > 1}
    if dupes:
        raise RuntimeError(f"prompts.json has duplicate stems (outputs would collide): {sorted(dupes)}")
    return ads


# --------------------------------------------------------------------------- #
# Payload / API
# --------------------------------------------------------------------------- #
def build_payload(prompt: str, aspect_ratio: str, quality: str, output_format: str) -> dict:
    return {
        "model": MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "quality": quality,
            "output_format": output_format,
            "nsfw_checker": False,
        },
    }


def create_task(payload: dict, key: str) -> tuple[str, dict]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/createTask", json=payload, headers=headers, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"Kie createTask error: {data}")
    return data["data"]["taskId"], data


def poll_task(task_id: str, key: str, max_attempts: int = 60, interval: int = 5) -> tuple[object, int, dict]:
    headers = {"Authorization": f"Bearer {key}"}
    last_data: dict = {}
    for attempt in range(max_attempts):
        resp = requests.get(
            f"{BASE_URL}/recordInfo", params={"taskId": task_id}, headers=headers, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        last_data = data
        state = data.get("state")
        cost = int(data.get("costTime", 0) or 0)
        print(f"  [{attempt + 1}/{max_attempts}] state={state} cost={cost}ms")
        if state == "success":
            result = data.get("resultJson")
            if isinstance(result, str):
                result = json.loads(result)
            return result, cost, data
        if state == "fail":
            print(f"  FAILED: {data.get('failCode')} - {data.get('failMsg')}", file=sys.stderr)
            return None, cost, data
        time.sleep(interval)
    print("  TIMEOUT polling Kie task", file=sys.stderr)
    return None, 0, last_data


def extract_result_url(result) -> str | None:
    """Pull the first image URL out of Kie's resultJson (several shapes seen)."""
    if isinstance(result, list) and result:
        return str(result[0])
    if isinstance(result, dict):
        for k in ("resultUrls", "images", "url", "image_url", "output"):
            val = result.get(k)
            if isinstance(val, list) and val:
                return str(val[0])
            if isinstance(val, str):
                return val
    return None


def download_result(url: str, out_path: Path) -> Path:
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    return out_path


def extract_credits(final_data: dict) -> object:
    if not isinstance(final_data, dict):
        return None
    return (
        final_data.get("creditsConsumed")
        or final_data.get("credits")
        or final_data.get("cost")
        or final_data.get("consumeCredits")
    )


# --------------------------------------------------------------------------- #
# Per-ad generation (one paid createTask + poll)
# --------------------------------------------------------------------------- #
def generate_ad(ad: dict, key: str, out_dir: Path, aspect_ratio: str, quality: str, output_format: str) -> int:
    out_png = out_dir / f"{ad['stem']}.{output_format}"
    out_task_json = out_dir / f"{ad['stem']}.task.json"
    payload = build_payload(ad["prompt"], aspect_ratio, quality, output_format)

    print(f"\n### {ad['label']} ###")
    print(f"Creating Kie task (model={MODEL}, quality={quality}) ...")
    started = time.time()
    task_id, create_resp = create_task(payload, key)
    print(f"Task: {task_id}\nPolling (timeout ~5 min) ...")
    result, cost_ms, final_data = poll_task(task_id, key)
    duration_s = round(time.time() - started, 1)
    result_url = extract_result_url(result)

    saved = None
    if result_url:
        saved = download_result(result_url, out_png)
        size_kb = round(saved.stat().st_size / 1024, 1)
        print(f"Saved: {saved} ({size_kb} KB)")
    else:
        print("No result URL returned.", file=sys.stderr)

    credits = extract_credits(final_data)

    entry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": ad["label"],
        "stem": ad["stem"],
        "model": MODEL,
        "task_id": task_id,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "output_format": output_format,
        "prompt": ad["prompt"],
        "cost_time_ms": cost_ms,
        "duration_seconds": duration_s,
        "credits_consumed": credits,
        "result_url": result_url,
        "output": str(saved) if saved else None,
        "create_response": create_resp,
        "final_record": final_data,
    }
    out_task_json.parent.mkdir(parents=True, exist_ok=True)
    out_task_json.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Task JSON: {out_task_json}")
    print(json.dumps({
        "task_id": task_id,
        "duration_seconds": duration_s,
        "cost_time_ms": cost_ms,
        "credits": credits,
        "output": entry["output"],
    }, indent=2))
    return 0 if saved else 1


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Meta ad statics with baked-in headline text via the Kie AI Jobs API."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Print payloads, make no paid call (default)")
    group.add_argument("--live", action="store_true", help="Execute the paid generations sequentially")
    parser.add_argument("--only", default=None, help="Run only ads whose stem contains this substring (retry-safe)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory (default ./output)")
    parser.add_argument("--prompts", default=str(DEFAULT_PROMPTS), help="Path to prompts.json (default ./prompts.json)")
    parser.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, help="Aspect ratio (default 3:4)")
    parser.add_argument("--quality", default=DEFAULT_QUALITY, help="Quality (default basic == 1K)")
    parser.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT, help="Output format (default png)")
    args = parser.parse_args()

    live = args.live  # dry-run is the default when --live not passed
    out_dir = Path(args.out).resolve()
    prompts_path = Path(args.prompts).resolve()

    ads = load_prompts(prompts_path)
    selected_ads = ads if not args.only else [a for a in ads if args.only in a["stem"]]

    if not selected_ads:
        print(f"ERROR: --only '{args.only}' matched no ads.", file=sys.stderr)
        return 2

    key = load_api_key()

    # Show selected payloads (Authorization header redacted; no paid call yet).
    for ad in selected_ads:
        payload = build_payload(ad["prompt"], args.aspect_ratio, args.quality, args.output_format)
        print(f"\n=== createTask payload: {ad['label']} (Authorization header redacted) ===")
        print(f"POST {BASE_URL}/createTask")
        print(f"Authorization: Bearer {redact(key)}")
        print("Content-Type: application/json")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("=" * 70)

    if not live:
        est_credits = len(selected_ads) * 7
        print(
            f"\nDRY RUN - no paid call made. {len(selected_ads)} ad(s) selected "
            f"(~{est_credits} credits if run live). Re-run with --live to generate."
        )
        return 0

    print(f"\nLIVE MODE - generating {len(selected_ads)} ad(s) sequentially into {out_dir}")
    overall = 0
    for ad in selected_ads:
        rc = generate_ad(ad, key, out_dir, args.aspect_ratio, args.quality, args.output_format)
        overall = overall or rc

    return overall


if __name__ == "__main__":
    raise SystemExit(main())
