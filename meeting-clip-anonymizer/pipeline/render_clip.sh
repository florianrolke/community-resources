#!/bin/bash
# CLOUD clip pipeline — assemble + manifest + render, all on your server. Zero local CPU.
# Usage:  bash render_clip.sh <clipname>
#         CLIP_SRC=/path/other.mp4 bash render_clip.sh <clipname>   (different recording)
# Names map to the example scripts (assemble_clips.py / build_manifest.py); rename if you renamed them.
set -e
CLIP="$1"
[ -z "$CLIP" ] && { echo "usage: render_clip.sh <clipname>"; exit 1; }
# --- CONFIGURE for your server ---
CA=${CLIP_ASSEMBLY_DIR:-$HOME/clip-assembly}        # work dir: recording, transcript, scripts, assets
PY=${CLIP_PYTHON:-$HOME/venv/bin/python}            # python with torch / Pillow / numpy
HP=${REMOTION_HOST_DIR:-$HOME/remotion-editor}      # Remotion project (host path)
CP=${REMOTION_CONTAINER_DIR:-$HP}                   # Remotion project path INSIDE the render container
WORKER=${REMOTION_WORKER:-remotion-worker}          # docker container name
COMP=${REMOTION_COMPOSITION:-LuxuryCourseHybridEdit}
# ----------------------------------
cd "$CA"
export CLIP_SRC=${CLIP_SRC:-$CA/recording.mp4}
export CLIP_VAD=$CA/silence_removal.py
export CLIP_BG=$CA/branded_bg.png
export CLIP_LOGO=$CA/logo.png
export CLIP_BROLL=$CA/broll
export HF_HUB_DISABLE_SYMLINKS_WARNING=1
echo "[$(date +%T)] assemble  $CLIP"
$PY assemble_clips.py "$CLIP"
echo "[$(date +%T)] manifest  $CLIP"
$PY build_manifest.py "$CLIP"
cp "${CLIP}-base.mp4" "$HP/public/"
cp "${CLIP}-props.json" "$HP/props/"
echo "[$(date +%T)] render    $CLIP"
docker exec -w "$CP" "$WORKER" bash -lc "npx remotion render $COMP out/${CLIP}-1080p.mp4 --props=props/${CLIP}-props.json --scale=3 --concurrency=2 --codec=h264 --crf=23 --log=error"
echo "[$(date +%T)] DONE -> $HP/out/${CLIP}-1080p.mp4"
ls -la "$HP/out/${CLIP}-1080p.mp4"
