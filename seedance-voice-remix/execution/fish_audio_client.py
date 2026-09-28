"""Fish Audio API client — voice cloning, TTS, ASR, credit balance.

Ported from the video-studio repo's proven `fish.ts` call shapes.
Docs: https://docs.fish.audio   Base URL: https://api.fish.audio

Requires FISH_AUDIO_API_KEY in the project .env.

Usage:
    python -X utf8 execution/fish_audio_client.py credit
    python -X utf8 execution/fish_audio_client.py clone-voice --name "My Voice" --samples a.wav b.wav
    python -X utf8 execution/fish_audio_client.py list-voices
    python -X utf8 execution/fish_audio_client.py tts --text "Hello" --voice <model_id> --out .tmp/vo.mp3
    python -X utf8 execution/fish_audio_client.py tts --text-file script.txt --voice <id> --out vo.mp3
    python -X utf8 execution/fish_audio_client.py asr --audio vo.mp3 --out vo_transcript.json

Cost note: voice cloning is free; TTS on model `s1` is $15 per 1M UTF-8 bytes
(~$0.02 per minute of speech). `tts` prints an estimate and requires --yes to
spend credits, per the workspace rule on paid API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: the `requests` package is required. Install it with: pip install requests", file=sys.stderr)
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

BASE_URL = "https://api.fish.audio"
DEFAULT_TTS_MODEL = "s1"
USD_PER_MILLION_BYTES = 15.0  # s1 and s2.1-pro rate, verified 2026-08-13


def load_api_key() -> str:
    """Read FISH_AUDIO_API_KEY from the environment or the project .env."""
    key = os.environ.get("FISH_AUDIO_API_KEY", "").strip()
    if key:
        return key

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "FISH_AUDIO_API_KEY":
                return value.strip().strip('"').strip("'")

    print(
        "ERROR: FISH_AUDIO_API_KEY not found.\n"
        "  1. Sign up at https://fish.audio and create an API key\n"
        f"  2. Add a line to {ENV_FILE}:  FISH_AUDIO_API_KEY=your_key_here",
        file=sys.stderr,
    )
    raise SystemExit(1)


def auth_headers(extra: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {load_api_key()}"}
    if extra:
        headers.update(extra)
    return headers


def check_response(response: requests.Response, action: str) -> None:
    if response.ok:
        return
    detail = response.text[:500]
    print(f"ERROR: {action} failed — HTTP {response.status_code}\n{detail}", file=sys.stderr)
    raise SystemExit(1)


def estimate_tts_cost(text: str) -> tuple[int, float]:
    """Return (utf-8 byte count, estimated USD) for a TTS request."""
    byte_count = len(text.encode("utf-8"))
    return byte_count, byte_count / 1_000_000 * USD_PER_MILLION_BYTES


# ---------------------------------------------------------------- commands


def cmd_credit(args: argparse.Namespace) -> int:
    response = requests.get(f"{BASE_URL}/wallet/self/api-credit", headers=auth_headers(), timeout=30)
    check_response(response, "credit lookup")
    data = response.json()
    print(json.dumps(data, indent=2))
    credit = data.get("credit")
    if credit is not None:
        print(f"\nAvailable credit: ${float(credit):.4f}")
    return 0


def cmd_clone_voice(args: argparse.Namespace) -> int:
    samples = [Path(s) for s in args.samples]
    missing = [s for s in samples if not s.is_file()]
    if missing:
        print(f"ERROR: sample file(s) not found: {', '.join(str(m) for m in missing)}", file=sys.stderr)
        return 1

    print(f"Cloning voice {args.name!r} from {len(samples)} sample(s):")
    for s in samples:
        print(f"  - {s.name} ({s.stat().st_size / 1024:.0f} KB)")
    print("Fish Audio wants 10s minimum, ideally 1-2 minutes of clean solo speech.\n")

    data = {
        "type": "tts",
        "title": args.name,
        "description": args.description,
        "train_mode": "fast",
        "visibility": "private",
        "enhance_audio_quality": "true",
    }
    files = []
    handles = []
    try:
        for s in samples:
            handle = open(s, "rb")
            handles.append(handle)
            files.append(("voices", (s.name, handle, "application/octet-stream")))
        response = requests.post(f"{BASE_URL}/model", headers=auth_headers(), data=data, files=files, timeout=300)
    finally:
        for handle in handles:
            handle.close()

    check_response(response, "voice cloning")
    result = response.json()
    model_id = result.get("_id") or result.get("id")
    print(json.dumps(result, indent=2)[:1500])
    print(f"\nVoice model id: {model_id}")
    print(f"Use it with:  --voice {model_id}")

    if args.save:
        registry = PROJECT_ROOT / "assets" / "voices.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {"voices": []}
        existing["voices"].append({
            "name": args.name,
            "model_id": model_id,
            "provider": "fish",
            "samples": [str(s) for s in samples],
        })
        registry.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        print(f"Saved to {registry}")
    return 0


def cmd_list_voices(args: argparse.Namespace) -> int:
    response = requests.get(
        f"{BASE_URL}/model",
        headers=auth_headers(),
        params={"self": "true", "page_size": 50},
        timeout=60,
    )
    check_response(response, "voice listing")
    data = response.json()
    items = data.get("items", data if isinstance(data, list) else [])
    if not items:
        print("No voice models found on this account.")
        return 0
    print(f"{'MODEL ID':<30} {'TITLE':<30} STATE")
    print("-" * 74)
    for item in items:
        print(f"{item.get('_id', item.get('id', '?')):<30} {str(item.get('title', ''))[:29]:<30} {item.get('state', '')}")
    return 0


def cmd_tts(args: argparse.Namespace) -> int:
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    else:
        text = args.text
    if not text:
        print("ERROR: no text supplied (use --text or --text-file).", file=sys.stderr)
        return 1

    byte_count, cost = estimate_tts_cost(text)
    is_free = "free" in args.model.lower()
    print(f"Text: {len(text)} chars / {byte_count} UTF-8 bytes")
    if is_free:
        print(f"Estimated cost: $0.0000 (model {args.model} is the free, rate-limited tier)")
    else:
        print(f"Estimated cost: ${cost:.4f} (model {args.model} @ ${USD_PER_MILLION_BYTES}/1M bytes)")
    print(f"Voice: {args.voice or 'provider default (no reference_id)'}")
    print(f"Preview: {text[:160]}{'...' if len(text) > 160 else ''}\n")

    if not args.yes and not is_free:
        print("This is a PAID API call. Re-run with --yes to proceed.")
        return 2

    payload = {
        "text": text,
        "format": args.format,
        "mp3_bitrate": 128,
        "normalize": True,
        "latency": "normal",
    }
    if args.voice:
        payload["reference_id"] = args.voice
    response = requests.post(
        f"{BASE_URL}/v1/tts",
        headers=auth_headers({"Content-Type": "application/json", "model": args.model}),
        json=payload,
        timeout=300,
    )
    check_response(response, "TTS")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    print(f"Wrote {out} ({len(response.content) / 1024:.0f} KB)")
    return 0


def cmd_asr(args: argparse.Namespace) -> int:
    audio = Path(args.audio)
    if not audio.is_file():
        print(f"ERROR: audio file not found: {audio}", file=sys.stderr)
        return 1

    with open(audio, "rb") as handle:
        response = requests.post(
            f"{BASE_URL}/v1/asr",
            headers=auth_headers(),
            files={"audio": (audio.name, handle, "application/octet-stream")},
            data={"ignore_timestamps": "false", **({"language": args.language} if args.language else {})},
            timeout=300,
        )
    check_response(response, "ASR")
    result = response.json()

    print(result.get("text", "")[:2000])
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fish Audio client (voice clone / TTS / ASR).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("credit", help="Show remaining API credit").set_defaults(func=cmd_credit)

    clone = sub.add_parser("clone-voice", help="Create a cloned voice model from audio samples")
    clone.add_argument("--name", required=True, help="Title for the voice model")
    clone.add_argument("--samples", nargs="+", required=True, help="Audio sample files")
    clone.add_argument("--description", default="Cloned via fish_audio_client.py")
    clone.add_argument("--save", action="store_true", help="Append the model id to assets/voices.json")
    clone.set_defaults(func=cmd_clone_voice)

    sub.add_parser("list-voices", help="List voice models on this account").set_defaults(func=cmd_list_voices)

    tts = sub.add_parser("tts", help="Generate speech (PAID — needs --yes)")
    tts.add_argument("--text", help="Text to speak")
    tts.add_argument("--text-file", help="File containing the text to speak")
    tts.add_argument("--voice", help="Voice model id (reference_id); omit for the provider default voice")
    tts.add_argument("--out", required=True, help="Output audio path")
    tts.add_argument("--model", default=DEFAULT_TTS_MODEL, help="TTS model header (default: s1)")
    tts.add_argument("--format", default="mp3", choices=["mp3", "wav", "opus"])
    tts.add_argument("--yes", action="store_true", help="Confirm the paid call")
    tts.set_defaults(func=cmd_tts)

    asr = sub.add_parser("asr", help="Transcribe audio (returns timestamps)")
    asr.add_argument("--audio", required=True)
    asr.add_argument("--out", help="Write the full JSON response here")
    asr.add_argument("--language", help="Language hint, e.g. en / de")
    asr.set_defaults(func=cmd_asr)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
