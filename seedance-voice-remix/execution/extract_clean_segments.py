"""Recover usable footage from shots that carry burned-in captions part of the time.

detect_burned_text.py records WHEN text is on screen (`text_windows`). A shot whose
caption runs 2.0-8.4s is still clean from 0-2.0s. Those gaps are perfectly good
b-roll and were being thrown away — with 46 of 72 shots flagged, most of the
library was locked out over a caption that only covers part of the shot.

Appends derived sub-shots (id `<shot>__cN`) to assets/scenes/shots.json with
has_burned_text=false, so build_vo_edit.py picks them up like any other shot.
Re-running replaces previously derived entries rather than stacking duplicates.

Usage:
    python -X utf8 execution/extract_clean_segments.py
    python -X utf8 execution/extract_clean_segments.py --min 2.0 --margin 0.6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOTS_JSON = PROJECT_ROOT / "assets" / "scenes" / "shots.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover caption-free segments from flagged shots.")
    parser.add_argument("--min", type=float, default=1.8, help="Shortest segment worth keeping")
    parser.add_argument("--margin", type=float, default=0.5,
                        help="Safety padding around each text window (detector samples at 2.5fps, "
                             "so windows are quantised to 0.4s)")
    args = parser.parse_args()

    if not SHOTS_JSON.exists():
        print(f"ERROR: {SHOTS_JSON} not found.", file=sys.stderr)
        return 1

    payload = json.loads(SHOTS_JSON.read_text(encoding="utf-8"))
    shots = [s for s in payload.get("shots", []) if not s.get("derived")]

    derived: list[dict] = []
    for shot in shots:
        if not shot.get("has_burned_text"):
            continue
        windows = shot.get("text_windows") or []
        duration = shot["duration"]
        if not windows:
            continue

        # Pad each text window, then walk the gaps between them.
        blocked = sorted((max(w[0] - args.margin, 0.0), min(w[1] + args.margin, duration))
                         for w in windows)
        merged: list[list[float]] = []
        for start, end in blocked:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])

        cursor = 0.0
        gaps: list[tuple[float, float]] = []
        for start, end in merged:
            if start - cursor >= args.min:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if duration - cursor >= args.min:
            gaps.append((cursor, duration))

        for index, (start, end) in enumerate(gaps, 1):
            derived.append({
                "id": f"{shot['id']}__c{index}",
                "scene": shot["scene"],
                "source": shot["source"],
                "abs_path": shot["abs_path"],
                "start": round(shot["start"] + start, 3),
                "end": round(shot["start"] + end, 3),
                "duration": round(end - start, 3),
                "resolution": shot.get("resolution", ""),
                "has_burned_text": False,
                "derived": True,
                "derived_from": shot["id"],
                "description": f"caption-free {start:.1f}-{end:.1f}s of {shot['id']}",
            })

    kept = [s for s in payload.get("shots", []) if not s.get("derived")]
    payload["shots"] = kept + derived
    payload["derived_count"] = len(derived)
    clean = [s for s in payload["shots"] if s.get("has_burned_text") is False]
    payload["clean_count"] = len(clean)
    payload["clean_duration"] = round(sum(s["duration"] for s in clean), 2)
    SHOTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"{'DERIVED SHOT':<34} {'LEN':>6}  FROM")
    print("-" * 78)
    for entry in sorted(derived, key=lambda d: -d["duration"])[:40]:
        print(f"{entry['id']:<34} {entry['duration']:>5.1f}s  {entry['derived_from']}")
    print("-" * 78)
    print(f"recovered {len(derived)} segments, {sum(d['duration'] for d in derived):.1f}s")
    print(f"clean pool is now {len(clean)} shots / {payload['clean_duration']:.1f}s "
          f"(was {len(kept) - len([s for s in kept if s.get('has_burned_text')])} native)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
