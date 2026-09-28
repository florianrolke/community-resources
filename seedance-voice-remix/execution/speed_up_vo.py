"""Speed up a voiceover without changing its pitch, and rescale its word timings.

ffmpeg's atempo compresses time uniformly, so the transcript stays valid after
dividing every timestamp by the same factor. That avoids a second trip to the
whisper box just to re-time audio we already have timings for.

Usage:
    python -X utf8 execution/speed_up_vo.py --in assets/vo/x.mp3 --words assets/vo/x.words.json \
        --speed 1.2 --out assets/vo/x-fast.mp3
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Speed up a VO and rescale its word timings.")
    parser.add_argument("--in", dest="src", required=True)
    parser.add_argument("--words", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--speed", type=float, default=1.2, help="1.2 = 20%% faster")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        die("ffmpeg not found on PATH.")
    if not 0.5 <= args.speed <= 2.0:
        die("atempo only accepts 0.5-2.0 in a single pass; chain filters for more.")

    src, words_path, out = Path(args.src), Path(args.words), Path(args.out)
    for path in (src, words_path):
        if not path.is_file():
            die(f"not found: {path}")

    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-filter:a", f"atempo={args.speed}", "-b:a", "128k", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        die(f"ffmpeg failed: {result.stderr.strip()[:300]}")

    data = json.loads(words_path.read_text(encoding="utf-8"))

    def rescale(entry: dict) -> dict:
        for key in ("start", "end"):
            if key in entry and entry[key] is not None:
                entry[key] = round(entry[key] / args.speed, 3)
        return entry

    if data.get("words"):
        data["words"] = [rescale(w) for w in data["words"]]
    for segment in data.get("segments", []):
        rescale(segment)
        segment["words"] = [rescale(w) for w in segment.get("words", [])]
    if data.get("duration"):
        data["duration"] = round(data["duration"] / args.speed, 3)

    words_out = out.with_suffix("").with_suffix(".words.json") \
        if out.suffix else Path(str(out) + ".words.json")
    words_out = out.parent / (out.stem + ".words.json")
    words_out.write_text(json.dumps(data, indent=2), encoding="utf-8")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print(f"{src.name} -> {out.name} at {args.speed}x")
    print(f"  audio  {float(probe.stdout.strip()):.2f}s")
    print(f"  words  {words_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
