"""Transcribe every scene clip to word-level JSON via the remote box faster-whisper.

Word timings are what let us cut on phrase boundaries instead of arbitrary time
marks, and they feed render_captions.py directly (same whisper-1 verbose shape).

Audio extraction is local (cheap, audio-only); the transcription runs on the
remote box so your machine stays free.

Writes assets/scenes/transcripts/<scene_id>.json

Usage:
    python -X utf8 execution/transcribe_scenes.py
    python -X utf8 execution/transcribe_scenes.py --model medium --only 93e36439-scene_0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "execution"))

SCENES_DIR = PROJECT_ROOT / "assets" / "scenes"
MANIFEST = SCENES_DIR / "scenes.json"
TRANSCRIPT_DIR = SCENES_DIR / "transcripts"
TMP_AUDIO = PROJECT_ROOT / ".tmp" / "scene-audio"


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def extract_audio(video: Path, out_mp3: Path) -> bool:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video),
           "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(out_mp3)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"  ! audio extraction failed: {result.stderr.strip()[:200]}")
        return False
    return out_mp3.exists()


def summarise(data: dict) -> str:
    words = data.get("words") or [w for s in data.get("segments", []) for w in s.get("words", [])]
    text = (data.get("text") or "").strip()
    return f"{len(words)} words | {text[:110]}{'...' if len(text) > 110 else ''}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe scene clips on the remote box.")
    parser.add_argument("--model", default="small", help="faster-whisper model (small/medium/large-v3)")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--only", help="Transcribe just this scene id")
    parser.add_argument("--force", action="store_true", help="Re-transcribe even if the JSON exists")
    args = parser.parse_args()

    try:
        import whisper_hostinger_client as whisper
    except Exception as exc:  # noqa: BLE001
        die(f"could not import whisper_hostinger_client ({exc}). Check execution/hostinger.py credentials.")

    if not MANIFEST.exists():
        die(f"{MANIFEST} not found. Run extract_topview_scenes.py first.")

    scenes = json.loads(MANIFEST.read_text(encoding="utf-8")).get("scenes", [])
    if args.only:
        scenes = [s for s in scenes if s["id"] == args.only]
        if not scenes:
            die(f"scene {args.only!r} not found in the manifest.")

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    done, skipped, failed = 0, 0, 0

    for scene in scenes:
        scene_id = scene["id"]
        out_json = TRANSCRIPT_DIR / f"{scene_id}.json"
        if out_json.exists() and not args.force:
            print(f"[{scene_id}] transcript exists, skipping (--force to redo)")
            skipped += 1
            continue

        video = Path(scene.get("abs_path", ""))
        if not video.is_file():
            video = PROJECT_ROOT / scene["path"]
        if not video.is_file():
            print(f"[{scene_id}] source missing, skipping")
            failed += 1
            continue

        print(f"[{scene_id}] extracting audio ...")
        mp3 = TMP_AUDIO / f"{scene_id}.mp3"
        if not extract_audio(video, mp3):
            failed += 1
            continue

        try:
            data = whisper.transcribe(str(mp3), str(out_json), model=args.model, threads=args.threads)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! transcription failed: {exc}")
            failed += 1
            continue

        print(f"  {summarise(data)}")
        done += 1

    print(f"\n{done} transcribed, {skipped} skipped, {failed} failed")
    print(f"Transcripts: {TRANSCRIPT_DIR}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
