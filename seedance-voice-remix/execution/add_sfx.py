"""Mix SFX hits (and optionally a music bed) onto a finished cut.

Follows the density rules the shorts renderer already uses: hits land on section
changes rather than every cut, and never closer together than --min-gap. Assets
come from Resources/sfx and Resources/music.

Usage:
    python -X utf8 execution/add_sfx.py --video in.mp4 --out out.mp4 \
        --hit 0.0:luxury-thump.wav:0.5 \
        --hit 6.12:luxury-whoosh.wav:0.35 \
        --hit 24.10:luxury-ding.wav:0.4

    # add a music bed under everything
    python -X utf8 execution/add_sfx.py --video in.mp4 --out out.mp4 \
        --hit 0:luxury-thump.wav:0.5 --music mfcc-optimistic-positive.mp3 --music-gain 0.06

List what's available:
    python -X utf8 execution/add_sfx.py --list
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = PROJECT_ROOT / "Resources" / "sfx"
MUSIC_DIR = PROJECT_ROOT / "Resources" / "music"


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        die(f"ffprobe failed for {path}")
    return float(result.stdout.strip())


def resolve_sfx(name: str) -> Path:
    path = Path(name)
    if path.is_file():
        return path
    candidate = SFX_DIR / name
    if candidate.is_file():
        return candidate
    die(f"SFX not found: {name} (looked in {SFX_DIR})")


def parse_hits(raw_hits: list[str], min_gap: float) -> list[dict]:
    hits = []
    for raw in raw_hits:
        parts = raw.split(":")
        if len(parts) < 2:
            die(f"bad --hit {raw!r}; expected time:file[:gain]")
        try:
            at = float(parts[0])
        except ValueError:
            die(f"bad time in --hit {raw!r}")
        gain = float(parts[2]) if len(parts) > 2 else 0.35
        hits.append({"at": at, "path": resolve_sfx(parts[1]), "gain": gain, "name": parts[1]})

    hits.sort(key=lambda h: h["at"])
    kept: list[dict] = []
    for hit in hits:
        if kept and hit["at"] - kept[-1]["at"] < min_gap:
            print(f"  ! dropping {hit['name']} at {hit['at']:.2f}s — only "
                  f"{hit['at'] - kept[-1]['at']:.2f}s after the previous hit (min {min_gap}s)")
            continue
        kept.append(hit)
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description="Mix SFX hits and optional music onto a cut.")
    parser.add_argument("--list", action="store_true", help="List available SFX/music and exit")
    parser.add_argument("--video", help="Input video (its audio is kept as the voice bed)")
    parser.add_argument("--out", help="Output video")
    parser.add_argument("--hit", action="append", default=[], metavar="TIME:FILE[:GAIN]")
    parser.add_argument("--music", help="Music file (name inside Resources/music, or a path)")
    parser.add_argument("--music-gain", type=float, default=0.06)
    parser.add_argument("--voice-gain", type=float, default=1.0)
    parser.add_argument("--min-gap", type=float, default=0.8, help="Minimum spacing between hits")
    args = parser.parse_args()

    if args.list:
        print(f"SFX ({SFX_DIR}):")
        for f in sorted(SFX_DIR.glob("*")):
            if f.is_file():
                print(f"  {f.name}")
        print(f"\nMusic ({MUSIC_DIR}):")
        for f in sorted(MUSIC_DIR.glob("*")):
            if f.is_file():
                print(f"  {f.name}")
        return 0

    if not args.video or not args.out:
        die("--video and --out are required (or use --list)")
    if not shutil.which("ffmpeg"):
        die("ffmpeg not found on PATH.")

    video = Path(args.video)
    if not video.is_file():
        die(f"input video not found: {video}")
    duration = probe_duration(video)

    hits = parse_hits(args.hit, args.min_gap)
    music_path = None
    if args.music:
        music_path = Path(args.music) if Path(args.music).is_file() else MUSIC_DIR / args.music
        if not music_path.is_file():
            die(f"music not found: {args.music}")

    print(f"Video: {video.name} ({duration:.2f}s)")
    for hit in hits:
        print(f"  {hit['at']:>6.2f}s  {hit['name']:<22} gain {hit['gain']}")
    if music_path:
        print(f"  music: {music_path.name} @ {args.music_gain}")
    if not hits and not music_path:
        die("nothing to add — pass --hit and/or --music")

    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", str(video)]
    for hit in hits:
        cmd += ["-i", str(hit["path"])]
    if music_path:
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]

    filters = [f"[0:a]volume={args.voice_gain}[voice]"]
    mix_labels = ["[voice]"]

    for index, hit in enumerate(hits, start=1):
        delay_ms = int(hit["at"] * 1000)
        filters.append(
            f"[{index}:a]volume={hit['gain']},adelay={delay_ms}|{delay_ms},"
            f"apad=whole_dur={duration}[sfx{index}]"
        )
        mix_labels.append(f"[sfx{index}]")

    if music_path:
        music_index = len(hits) + 1
        fade_start = max(duration - 1.5, 0.0)
        filters.append(
            f"[{music_index}:a]volume={args.music_gain},"
            f"afade=t=in:st=0:d=1.0,afade=t=out:st={fade_start:.2f}:d=1.5,"
            f"atrim=0:{duration}[music]"
        )
        mix_labels.append("[music]")

    filters.append(
        "".join(mix_labels)
        + f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0:normalize=0[mixed]"
    )
    filters.append("[mixed]alimiter=limit=0.97,loudnorm=I=-14:TP=-1.5:LRA=11[outa]")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[outa]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(out_path)]

    print(f"\nMixing -> {out_path.name} ...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        die(f"ffmpeg exited with code {result.returncode}")

    print(f"\nDone: {out_path}  ({probe_duration(out_path):.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
