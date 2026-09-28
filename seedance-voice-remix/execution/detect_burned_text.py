"""Detect burned-in captions in each shot and record it in shots.json.

The TopView source ads have their captions baked into the pixels. Any shot
carrying them is unusable under a new voiceover, so every shot has to be
classified â€” and midpoint thumbnails miss text that appears elsewhere in the
shot, which is why this samples across the whole shot instead.

Detection signal: TopView captions are bright glyphs with a dark outline. A
pixel that is very bright while a neighbour a few pixels away is very dark is a
"stroke edge". Sky, white walls and the presenter's cream suit are smooth and
score near zero; text scores heavily, and only inside a narrow band of rows.

Writes has_burned_text + text_windows (seconds, relative to the shot) back into
assets/scenes/shots.json. Existing manual annotations are kept unless --force.

Usage:
    python -X utf8 execution/detect_burned_text.py --validate   # check known cases first
    python -X utf8 execution/detect_burned_text.py
    python -X utf8 execution/detect_burned_text.py --force --fps 3
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
    print("ERROR: needs numpy and Pillow (pip install numpy pillow)", file=sys.stderr)
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOTS_JSON = PROJECT_ROOT / "assets" / "scenes" / "shots.json"

SAMPLE_W = 360          # frames are analysed small; glyph strokes survive fine
BRIGHT = 218            # a caption glyph pixel — tuned 2026-08-14, see --validate
DARK = 110              # its outline. Biased to over-flag: a missed caption ends
                        # up in the finished video, an over-flagged shot only costs
                        # us footage we have plenty of.
STROKE_GAP = 3          # px between glyph and outline
ROW_MIN = 6             # stroke pixels needed for a row to look like text
BAND_MIN_ROWS = 4       # consecutive text-ish rows needed to call it a caption
SIDE_MARGIN = 0.10      # ignore the outer 10% each side

# Shots whose state was established by eye earlier â€” used by --validate.
KNOWN_TEXT = [
    "33e0efdf-scene_0__s1", "33e0efdf-scene_0__s4", "93e36439-scene_0__s1",
    "93e36439-scene_2__s1", "a9caef6d-scene_0__s1", "a9caef6d-scene_0__s4",
]
KNOWN_CLEAN = [
    "33e0efdf-scene_0__s2", "33e0efdf-scene_0__s3", "93e36439-scene_1__s1",
    "a9caef6d-scene_0__s2", "a9caef6d-scene_0__s3",
]


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def sample_frames(video: Path, start: float, duration: float, fps: float, out_dir: Path) -> list[Path]:
    """One ffmpeg call per shot â€” much faster than seeking per frame."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(video),
           "-vf", f"fps={fps},scale={SAMPLE_W}:-2", str(out_dir / "f_%04d.png")]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return sorted(out_dir.glob("f_*.png"))


def frame_has_text(path: Path, bright: int = BRIGHT, dark: int = DARK,
                   row_min: int = ROW_MIN, band_rows: int = BAND_MIN_ROWS) -> bool:
    """True when a horizontal band of outlined bright strokes is present.

    Only HORIZONTAL neighbours are compared: glyph stems produce bright/dark
    transitions left-to-right, whereas a horizon or a roofline is a vertical
    gradient and scores nothing.
    """
    grey = np.asarray(Image.open(path).convert("L"), dtype=np.int16)
    height, width = grey.shape
    x0, x1 = int(width * SIDE_MARGIN), int(width * (1 - SIDE_MARGIN))
    grey = grey[:, x0:x1]

    is_bright = grey >= bright
    # a darker pixel STROKE_GAP away horizontally, on either side
    dark_left = np.zeros_like(is_bright)
    dark_right = np.zeros_like(is_bright)
    dark_left[:, STROKE_GAP:] = grey[:, :-STROKE_GAP] <= dark
    dark_right[:, :-STROKE_GAP] = grey[:, STROKE_GAP:] <= dark
    stroke = is_bright & (dark_left | dark_right)

    row_counts = stroke.sum(axis=1)
    columns = np.arange(stroke.shape[1])
    centre = stroke.shape[1] / 2.0

    # Captions are centred; foliage sparkle, water glints and the presenter's
    # cream suit produce stroke pixels too, but they sit off to one side. So a
    # row only counts as text when its stroke pixels straddle the centre line.
    texty = np.zeros(stroke.shape[0], dtype=bool)
    for row in np.nonzero(row_counts >= row_min)[0]:
        xs = columns[stroke[row]]
        centroid = xs.mean()
        if abs(centroid - centre) <= 0.16 * stroke.shape[1] and xs.min() < centre < xs.max():
            texty[row] = True

    run = 0
    for value in texty:
        run = run + 1 if value else 0
        if run >= band_rows:
            return True
    return False


def analyse_shot(shot: dict, fps: float, thresholds: dict | None = None) -> tuple[bool, list[list[float]]]:
    thresholds = thresholds or {}
    video = Path(shot.get("abs_path", ""))
    if not video.is_file():
        video = PROJECT_ROOT / shot["source"]
    if not video.is_file():
        return False, []

    tmp = Path(tempfile.mkdtemp(prefix="btext_"))
    try:
        frames = sample_frames(video, shot["start"], shot["duration"], fps, tmp)
        if not frames:
            return False, []
        flags = [frame_has_text(f, **thresholds) for f in frames]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    windows: list[list[float]] = []
    start_idx = None
    for i, flag in enumerate(flags + [False]):
        if flag and start_idx is None:
            start_idx = i
        elif not flag and start_idx is not None:
            windows.append([round(start_idx / fps, 2), round(i / fps, 2)])
            start_idx = None
    return any(flags), windows


def main() -> int:
    parser = argparse.ArgumentParser(description="Flag shots with burned-in captions.")
    parser.add_argument("--fps", type=float, default=2.5, help="Frames sampled per second of shot")
    parser.add_argument("--force", action="store_true", help="Overwrite existing has_burned_text values")
    parser.add_argument("--validate", action="store_true", help="Only check the known-answer shots")
    parser.add_argument("--bright", type=int, default=BRIGHT, help="Glyph brightness threshold")
    parser.add_argument("--dark", type=int, default=DARK, help="Outline darkness threshold")
    parser.add_argument("--row-min", type=int, default=ROW_MIN, help="Stroke pixels per text-ish row")
    parser.add_argument("--band-rows", type=int, default=BAND_MIN_ROWS, help="Consecutive rows to confirm")
    args = parser.parse_args()
    thresholds = {"bright": args.bright, "dark": args.dark,
                  "row_min": args.row_min, "band_rows": args.band_rows}

    if not shutil.which("ffmpeg"):
        die("ffmpeg not found on PATH.")
    if not SHOTS_JSON.exists():
        die(f"{SHOTS_JSON} not found. Run detect_shots.py first.")

    payload = json.loads(SHOTS_JSON.read_text(encoding="utf-8"))
    shots = payload.get("shots", [])

    if args.validate:
        wanted = {s: True for s in KNOWN_TEXT} | {s: False for s in KNOWN_CLEAN}
        by_id = {s["id"]: s for s in shots}
        passed = failed = 0
        print(f"{'SHOT':<28} {'EXPECT':<8} {'GOT':<8} RESULT")
        print("-" * 62)
        for shot_id, expected in wanted.items():
            if shot_id not in by_id:
                print(f"{shot_id:<28} {'-':<8} {'-':<8} MISSING from shots.json")
                continue
            got, _ = analyse_shot(by_id[shot_id], args.fps, thresholds)
            ok = got == expected
            passed, failed = passed + ok, failed + (not ok)
            print(f"{shot_id:<28} {str(expected):<8} {str(got):<8} {'ok' if ok else 'MISMATCH'}")
        print("-" * 62)
        print(f"{passed} passed, {failed} failed")
        return 0 if failed == 0 else 1

    print(f"{'SHOT':<28} {'DUR':>6}  {'TEXT?':<6} WINDOWS (s into shot)")
    print("-" * 84)
    changed = 0
    for shot in shots:
        if shot.get("has_burned_text") is not None and not args.force:
            print(f"{shot['id']:<28} {shot['duration']:>5.1f}s  "
                  f"{str(shot['has_burned_text']):<6} (kept)")
            continue
        has_text, windows = analyse_shot(shot, args.fps, thresholds)
        shot["has_burned_text"] = has_text
        shot["text_windows"] = windows
        changed += 1
        pretty = ", ".join(f"{w[0]:.1f}-{w[1]:.1f}" for w in windows[:4]) if windows else ""
        print(f"{shot['id']:<28} {shot['duration']:>5.1f}s  {str(has_text):<6} {pretty}")

    clean = [s for s in shots if s.get("has_burned_text") is False]
    payload["clean_duration"] = round(sum(s["duration"] for s in clean), 2)
    payload["clean_count"] = len(clean)
    SHOTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("-" * 84)
    print(f"{changed} shots analysed | CLEAN: {len(clean)}/{len(shots)} shots, "
          f"{payload['clean_duration']:.1f}s of usable footage")
    print(f"Written: {SHOTS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
