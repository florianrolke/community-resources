#!/usr/bin/env python3
"""Build a starter luxury overlay manifest from timed beats."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def seconds_to_frame(seconds: float, fps: int) -> int:
    return int(round(seconds * fps))


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_manifest(config: dict[str, Any]) -> dict[str, Any]:
    fps = int(config.get("fps", 30))
    width = int(config.get("width", 1920))
    height = int(config.get("height", 1080))
    duration_seconds = float(config["duration_seconds"])
    default_sfx = config.get("default_sfx", {})

    overlays = []
    sfx_cues = []
    jump_cuts = []

    for index, beat in enumerate(config.get("beats", []), start=1):
        start_frame = seconds_to_frame(float(beat["start"]), fps)
        duration_frames = seconds_to_frame(float(beat.get("duration", 5.0)), fps)
        kind = beat.get("kind", "fade_up_key")

        overlay = {
            "kind": kind,
            "startFrame": start_frame,
            "durationFrames": duration_frames,
            "eyebrow": beat.get("eyebrow", ""),
            "title": beat["title"],
            "goldTitle": beat.get("goldTitle", ""),
            "body": beat.get("body", ""),
            "bullets": beat.get("bullets", []),
            "accentColor": beat.get("accentColor", "#c9a96e"),
            "side": beat.get("side", "left"),
            "revealSpeed": beat.get("revealSpeed", "normal"),
        }

        for key in ("numberTarget", "numberPrefix", "numberSuffix", "numberLabel", "numberSubLabel"):
            if key in beat:
                overlay[key] = beat[key]

        overlays.append(overlay)

        sfx_file = beat.get("sfx") or default_sfx.get(kind)
        if sfx_file:
            sfx_cues.append(
                {
                    "id": f"{kind}-{index}-in",
                    "startFrame": start_frame,
                    "file": sfx_file,
                    "volume": float(beat.get("sfxVolume", config.get("sfx_volume", 0.32))),
                }
            )

        if beat.get("returnSfx"):
            sfx_cues.append(
                {
                    "id": f"{kind}-{index}-return",
                    "startFrame": start_frame + duration_frames - seconds_to_frame(0.18, fps),
                    "file": beat["returnSfx"],
                    "volume": float(beat.get("returnSfxVolume", config.get("sfx_volume", 0.32))),
                }
            )

        if beat.get("zoom"):
            jump_cuts.append(
                {
                    "id": f"zoom-{index}",
                    "startFrame": start_frame,
                    "durationFrames": seconds_to_frame(float(beat.get("zoomRamp", 0.3)), fps),
                    "zoom": float(beat["zoom"]),
                    "resetFrame": start_frame + duration_frames,
                    "reason": beat.get("reason", beat["title"]),
                }
            )

    ticker = config.get("ticker", {})
    ticker_bands = []
    if ticker.get("items"):
        ticker_bands.append(
            {
                "startFrame": seconds_to_frame(float(ticker.get("start", 0)), fps),
                "durationFrames": seconds_to_frame(float(ticker.get("duration", duration_seconds)), fps),
                "items": ticker["items"],
                "emphasis": ticker.get("emphasis", ticker["items"][0]),
            }
        )

    return {
        "videoSrc": config["videoSrc"],
        "fps": fps,
        "width": width,
        "height": height,
        "durationFrames": seconds_to_frame(duration_seconds, fps),
        "overlays": overlays,
        "tickerBands": ticker_bands,
        "sfxCues": sfx_cues,
        "videoEffects": {"jumpCuts": jump_cuts},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="JSON config with videoSrc, duration_seconds, and beats")
    parser.add_argument("--out", required=True, help="Output manifest JSON path")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    manifest = build_manifest(config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
