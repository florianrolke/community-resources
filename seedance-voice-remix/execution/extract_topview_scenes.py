"""Extract scene-export zips into the project scene library.

Reads zips matching --pattern from --downloads (never modifies or removes them),
unpacks each into assets/scenes/<zip-id-prefix>/, probes every clip with ffprobe,
grabs a mid-point thumbnail, and writes assets/scenes/scenes.json.

Per-zip subfolders matter: exports commonly name every clip inside them
`scene_0.mp4`, so flattening them into one directory would silently overwrite.

Usage:
    python -X utf8 execution/extract_topview_scenes.py --downloads ./exports
    python -X utf8 execution/extract_topview_scenes.py --downloads ./exports --pattern "*.zip"
    python -X utf8 execution/extract_topview_scenes.py --downloads ./exports --force
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENES_DIR = PROJECT_ROOT / "assets" / "scenes"
THUMBS_DIR = SCENES_DIR / "_thumbnails"
MANIFEST = SCENES_DIR / "scenes.json"

DEFAULT_DOWNLOADS = Path("./exports")
DEFAULT_PATTERN = "*.zip"

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"{name} not found on PATH. Install ffmpeg (it provides ffmpeg and ffprobe).")
    return path


def probe(video: Path) -> dict:
    """Return duration/resolution/fps/audio info for a clip via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"  ! ffprobe failed for {video.name}: {result.stderr.strip()[:200]}")
        return {}

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    info: dict = {
        "duration": round(float(data.get("format", {}).get("duration", 0.0)), 3),
        "size_mb": round(int(data.get("format", {}).get("size", 0)) / (1024 * 1024), 2),
        "has_audio": audio_stream is not None,
    }
    if video_stream:
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        info["width"] = width
        info["height"] = height
        info["resolution"] = f"{width}x{height}"
        info["orientation"] = "vertical" if height > width else ("square" if height == width else "horizontal")
        info["video_codec"] = video_stream.get("codec_name", "")
        rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
        try:
            num, _, den = rate.partition("/")
            info["fps"] = round(float(num) / float(den), 3) if float(den) else 0.0
        except (ValueError, ZeroDivisionError):
            info["fps"] = 0.0
    if audio_stream:
        info["audio_codec"] = audio_stream.get("codec_name", "")
        info["audio_sample_rate"] = audio_stream.get("sample_rate", "")
    return info


def make_thumbnail(video: Path, out_jpg: Path, at_seconds: float) -> bool:
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(at_seconds, 0):.3f}",
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "3",
        str(out_jpg),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not out_jpg.exists():
        print(f"  ! thumbnail failed for {video.name}: {result.stderr.strip()[:200]}")
        return False
    return True


def extract_zip(zip_path: Path, force: bool) -> tuple[Path, list[Path]]:
    """Unpack one zip into its own subfolder. Returns (dest_dir, extracted video paths)."""
    # analyzed_video_task_export_<32-hex>.zip -> keep the first 8 chars of the id
    stem = zip_path.stem
    zip_id = stem.replace("analyzed_video_task_export_", "")[:8] or stem[:8]
    dest = SCENES_DIR / zip_id
    dest.mkdir(parents=True, exist_ok=True)

    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = Path(entry.filename).name  # flatten; TopView entries are bare scene_N.mp4
            if not name or Path(name).suffix.lower() not in VIDEO_SUFFIXES:
                continue
            target = dest / name
            if target.exists() and not force:
                print(f"  = {zip_id}/{name} already extracted, skipping (use --force to overwrite)")
                extracted.append(target)
                continue
            with archive.open(entry) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"  + {zip_id}/{name} ({target.stat().st_size / (1024 * 1024):.1f} MB)")
            extracted.append(target)

    return dest, sorted(extracted)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract TopView scene zips into the project scene library.")
    parser.add_argument("--downloads", default=str(DEFAULT_DOWNLOADS), help="Folder holding the export zips")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="Glob for the zips to ingest")
    parser.add_argument("--force", action="store_true", help="Re-extract clips that already exist")
    parser.add_argument("--no-thumbnails", action="store_true", help="Skip thumbnail extraction")
    args = parser.parse_args()

    require_tool("ffprobe")
    if not args.no_thumbnails:
        require_tool("ffmpeg")

    downloads = Path(args.downloads)
    if not downloads.is_dir():
        die(f"Downloads folder not found: {downloads}")

    zips = sorted(downloads.glob(args.pattern))
    if not zips:
        die(f"No zips matching {args.pattern!r} in {downloads}")

    print(f"Found {len(zips)} export zip(s) in {downloads}\n")
    SCENES_DIR.mkdir(parents=True, exist_ok=True)

    scenes: list[dict] = []
    for zip_path in zips:
        print(f"[{zip_path.name}] {zip_path.stat().st_size / (1024 * 1024):.1f} MB")
        dest, clips = extract_zip(zip_path, args.force)
        for clip in clips:
            scene_id = f"{dest.name}-{clip.stem}"
            info = probe(clip)
            entry = {
                "id": scene_id,
                "source_zip": zip_path.name,
                "path": str(clip.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "abs_path": str(clip),
                "notes": "",
                **info,
            }
            if not args.no_thumbnails and info.get("duration"):
                thumb = THUMBS_DIR / f"{scene_id}.jpg"
                if make_thumbnail(clip, thumb, info["duration"] / 2):
                    entry["thumbnail"] = str(thumb.relative_to(PROJECT_ROOT)).replace("\\", "/")
            scenes.append(entry)
        print()

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_folder": str(downloads),
        "scene_count": len(scenes),
        "total_duration": round(sum(s.get("duration", 0.0) for s in scenes), 3),
        "scenes": scenes,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("=" * 78)
    print(f"{'SCENE ID':<22} {'DUR':>7}  {'RESOLUTION':<12} {'FPS':>6}  {'AUDIO':<6} {'MB':>7}")
    print("-" * 78)
    for s in scenes:
        print(
            f"{s['id']:<22} {s.get('duration', 0):>6.1f}s  {s.get('resolution', '?'):<12} "
            f"{s.get('fps', 0):>6.2f}  {'yes' if s.get('has_audio') else 'no':<6} {s.get('size_mb', 0):>7.1f}"
        )
    print("-" * 78)
    print(f"{len(scenes)} scenes, {manifest['total_duration']:.1f}s total")
    print(f"\nManifest: {MANIFEST}")
    if not args.no_thumbnails:
        print(f"Thumbnails: {THUMBS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
