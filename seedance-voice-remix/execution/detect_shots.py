"""Split scene clips into their TRUE shots using ffmpeg scene detection.

The TopView exports are not single scenes — the 30s files are finished 4-shot ads.
Cutting them at arbitrary time marks lands mid-shot and juxtaposes unrelated
footage. This script finds the real cut points and registers every shot
individually so the remixer picks from clean shots.

Reads  assets/scenes/scenes.json   (from extract_topview_scenes.py)
Writes assets/scenes/shots.json    (one entry per shot)
       assets/scenes/_shots/<shot_id>.jpg      midpoint thumbnail
       assets/scenes/_shots/<shot_id>-strip.jpg 4-frame strip (to eyeball burned-in text)

Usage:
    python -X utf8 execution/detect_shots.py
    python -X utf8 execution/detect_shots.py --threshold 0.25 --min-shot 1.5
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENES_DIR = PROJECT_ROOT / "assets" / "scenes"
MANIFEST = SCENES_DIR / "scenes.json"
SHOTS_DIR = SCENES_DIR / "_shots"
SHOTS_JSON = SCENES_DIR / "shots.json"

PTS_RE = re.compile(r"pts_time[:=]\s*([0-9.]+)")


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def detect_cuts(video: Path, threshold: float) -> list[float]:
    """Return timestamps where ffmpeg sees a hard cut."""
    cmd = [
        "ffmpeg", "-v", "info", "-i", str(video),
        "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
        "-an", "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    blob = (result.stdout or "") + (result.stderr or "")
    cuts = sorted({round(float(m), 3) for m in PTS_RE.findall(blob)})
    # A "cut" in the first fraction of a second is the opening frame, not a real cut.
    return [c for c in cuts if c > 0.5]


def build_shots(duration: float, cuts: list[float], min_shot: float) -> list[tuple[float, float]]:
    """Turn cut points into (start, end) ranges, absorbing slivers into the previous shot."""
    bounds = [0.0] + cuts + [duration]
    shots: list[tuple[float, float]] = []
    for start, end in zip(bounds, bounds[1:]):
        if end - start < min_shot and shots:
            shots[-1] = (shots[-1][0], end)  # too short to stand alone
        elif end - start >= 0.2:
            shots.append((start, end))
    return shots


def grab_frame(video: Path, out_jpg: Path, at_seconds: float) -> bool:
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(at_seconds, 0):.3f}", "-i", str(video),
           "-frames:v", "1", "-q:v", "3", str(out_jpg)]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out_jpg.exists()


def grab_strip(video: Path, out_jpg: Path, start: float, end: float) -> bool:
    """4 evenly spaced frames side by side — enough to spot burned-in captions."""
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    span = end - start
    offsets = [start + span * f for f in (0.1, 0.37, 0.63, 0.9)]
    tmp_dir = out_jpg.parent / f".strip_{out_jpg.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, offset in enumerate(offsets):
        frame = tmp_dir / f"f{index}.jpg"
        if grab_frame(video, frame, offset):
            frames.append(frame)
    if not frames:
        return False
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for frame in frames:
        cmd += ["-i", str(frame)]
    filters = "".join(f"[{i}:v]scale=250:445[s{i}];" for i in range(len(frames)))
    filters += "".join(f"[s{i}]" for i in range(len(frames))) + f"hstack=inputs={len(frames)}[out]"
    cmd += ["-filter_complex", filters, "-map", "[out]", "-frames:v", "1", "-q:v", "3", str(out_jpg)]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return out_jpg.exists()


def main() -> int:
    parser = argparse.ArgumentParser(description="Split scene clips into their true shots.")
    parser.add_argument("--threshold", type=float, default=0.25, help="Scene-change sensitivity (lower = more cuts)")
    parser.add_argument("--min-shot", type=float, default=1.5, help="Shots shorter than this merge into the previous")
    parser.add_argument("--no-strips", action="store_true", help="Skip the 4-frame strips")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        die("ffmpeg not found on PATH.")
    if not MANIFEST.exists():
        die(f"{MANIFEST} not found. Run extract_topview_scenes.py first.")

    scenes = json.loads(MANIFEST.read_text(encoding="utf-8")).get("scenes", [])
    if not scenes:
        die("No scenes in the manifest.")

    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    all_shots: list[dict] = []

    for scene in scenes:
        video = Path(scene.get("abs_path", ""))
        if not video.is_file():
            video = PROJECT_ROOT / scene["path"]
        if not video.is_file():
            print(f"  ! missing file for {scene['id']}, skipping")
            continue

        duration = float(scene.get("duration", 0))
        cuts = detect_cuts(video, args.threshold)
        shots = build_shots(duration, cuts, args.min_shot)
        print(f"[{scene['id']}] {duration:.1f}s -> {len(shots)} shot(s); cuts at "
              f"{', '.join(f'{c:.2f}s' for c in cuts) if cuts else 'none'}")

        for index, (start, end) in enumerate(shots, start=1):
            shot_id = f"{scene['id']}__s{index}"
            entry = {
                "id": shot_id,
                "scene": scene["id"],
                "source": scene["path"],
                "abs_path": str(video),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "resolution": scene.get("resolution", ""),
                "has_burned_text": None,   # fill in after eyeballing the strip
                "description": "",
            }
            thumb = SHOTS_DIR / f"{shot_id}.jpg"
            if grab_frame(video, thumb, start + (end - start) / 2):
                entry["thumbnail"] = str(thumb.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if not args.no_strips:
                strip = SHOTS_DIR / f"{shot_id}-strip.jpg"
                if grab_strip(video, strip, start, end):
                    entry["strip"] = str(strip.relative_to(PROJECT_ROOT)).replace("\\", "/")
            all_shots.append(entry)
            print(f"    {shot_id:<28} {start:>6.2f}s -> {end:>6.2f}s  ({end - start:>5.2f}s)")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "threshold": args.threshold,
        "min_shot": args.min_shot,
        "shot_count": len(all_shots),
        "total_duration": round(sum(s["duration"] for s in all_shots), 3),
        "shots": all_shots,
    }
    SHOTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{len(all_shots)} shots across {len(scenes)} files, "
          f"{payload['total_duration']:.1f}s total")
    print(f"Manifest: {SHOTS_JSON}")
    print(f"Frames:   {SHOTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
