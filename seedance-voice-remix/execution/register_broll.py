"""Register external b-roll clips (Kling, VOSU, stock) into the shot library.

Generated clips often open with a white flash or a fade-up that is a rendering
artifact rather than content — 7 of 9 Kling clips did. `--trim-head` skips it so
the shot starts on real picture. Brightness at the head is measured and reported
so the trim can be checked rather than assumed.

Appends entries to assets/scenes/shots.json with has_burned_text=null; run
detect_burned_text.py afterwards to classify them properly.

Usage:
    python -X utf8 execution/register_broll.py --folder "./broll-downloads" \
        --prefix kling --trim-head 1.6
    python -X utf8 execution/register_broll.py --folder <dir> --prefix vosu --auto-trim
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("ERROR: needs numpy and Pillow", file=sys.stderr)
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOTS_JSON = PROJECT_ROOT / "assets" / "scenes" / "shots.json"
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}
WHITE = 200.0          # mean luminance above this reads as a flash frame


def probe(video: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(video)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        return {}
    data = json.loads(out.stdout)
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "duration": round(float(data.get("format", {}).get("duration", 0)), 3),
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
    }


def head_brightness(video: Path, times: tuple[float, ...]) -> list[float]:
    tmp = Path(tempfile.mkdtemp(prefix="head_"))
    values = []
    try:
        for t in times:
            frame = tmp / f"{t:.2f}.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                            "-frames:v", "1", "-vf", "scale=160:-2", str(frame)], capture_output=True)
            values.append(float(np.asarray(Image.open(frame).convert("L")).mean())
                          if frame.exists() else float("nan"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Register external b-roll into shots.json.")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--prefix", default="broll", help="Id prefix, e.g. kling")
    parser.add_argument("--trim-head", type=float, default=0.0, help="Seconds to skip at the start")
    parser.add_argument("--trim-tail", type=float, default=0.0)
    parser.add_argument("--auto-trim", action="store_true",
                        help="Measure the white flash per clip and trim just past it")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: folder not found: {folder}", file=sys.stderr)
        return 1
    if not SHOTS_JSON.exists():
        print(f"ERROR: {SHOTS_JSON} not found.", file=sys.stderr)
        return 1

    clips = sorted(p for p in folder.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES)
    if not clips:
        print("no video files found")
        return 1

    payload = json.loads(SHOTS_JSON.read_text(encoding="utf-8"))
    existing = {s["id"] for s in payload.get("shots", [])}
    probe_times = (0.0, 0.4, 0.8, 1.2, 1.6, 2.0)

    added: list[dict] = []
    print(f"{'ID':<18} {'SIZE':<11} {'DUR':>6} {'TRIM':>6}  HEAD BRIGHTNESS")
    print("-" * 92)
    for index, clip in enumerate(clips, 1):
        info = probe(clip)
        if not info.get("duration"):
            print(f"  ! unreadable: {clip.name}")
            continue

        levels = head_brightness(clip, probe_times)
        trim = args.trim_head
        if args.auto_trim:
            trim = 0.0
            for t, level in zip(probe_times, levels):
                if level > WHITE:
                    trim = t + 0.4
            trim = round(min(trim, info["duration"] * 0.4), 2)

        shot_id = f"{args.prefix}-{index:02d}"
        if shot_id in existing:
            print(f"  = {shot_id} already registered, skipping")
            continue

        start = round(trim, 3)
        end = round(info["duration"] - args.trim_tail, 3)
        added.append({
            "id": shot_id,
            "scene": f"{args.prefix}-broll",
            "source": str(clip),
            "abs_path": str(clip),
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
            "resolution": f"{info['width']}x{info['height']}",
            "has_burned_text": None,
            "external": True,
            "description": f"{args.prefix} b-roll, head trimmed {start:.2f}s",
        })
        flag = "  <- white flash" if levels[0] > WHITE else ""
        print(f"{shot_id:<18} {info['width']}x{info['height']:<6} {info['duration']:>5.1f}s "
              f"{start:>5.2f}s  " + " ".join(f"{v:>4.0f}" for v in levels) + flag)

    if args.dry_run:
        print(f"\n(dry run) would add {len(added)} clips")
        return 0

    payload["shots"] = payload.get("shots", []) + added
    clean = [s for s in payload["shots"] if s.get("has_burned_text") is False]
    payload["clean_count"] = len(clean)
    payload["clean_duration"] = round(sum(s["duration"] for s in clean), 2)
    SHOTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("-" * 92)
    print(f"added {len(added)} clips, {sum(a['duration'] for a in added):.1f}s usable after trimming")
    print("Now run:  python -X utf8 execution/detect_burned_text.py   (classifies the new entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
