#!/bin/bash

. "/ins/setup_venv.sh" "$@"

export AGENTZERO_UPLOAD_DIR="${AGENTZERO_UPLOAD_DIR:-/app/work_dir/assets/agentzero_uploads/shorts_test}"
export AGENTZERO_UPLOAD_HOST="${AGENTZERO_UPLOAD_HOST:-0.0.0.0}"
export AGENTZERO_UPLOAD_PORT="${AGENTZERO_UPLOAD_PORT:-8080}"
export AGENTZERO_PIPELINE_DIR="${AGENTZERO_PIPELINE_DIR:-/app/work_dir/assets/agentzero_pipeline}"
export AGENTZERO_PIPELINE_CONFIG="${AGENTZERO_PIPELINE_CONFIG:-$AGENTZERO_PIPELINE_DIR/pipeline_config.json}"
export AGENTZERO_PIPELINE_SYNC_CODE="${AGENTZERO_PIPELINE_SYNC_CODE:-true}"

mkdir -p "$AGENTZERO_PIPELINE_DIR/defaults" "$AGENTZERO_PIPELINE_DIR/audio" "$AGENTZERO_PIPELINE_DIR/logo"

cp /git/agent-zero/tools/phone_upload_server.py "$AGENTZERO_PIPELINE_DIR/defaults/phone_upload_server.py"
cp /git/agent-zero/tools/phone_render_worker.py "$AGENTZERO_PIPELINE_DIR/defaults/phone_render_worker.py"
if [ -d /git/agent-zero/tools/agentzero_pipeline_defaults ]; then
  cp -R /git/agent-zero/tools/agentzero_pipeline_defaults/. "$AGENTZERO_PIPELINE_DIR/defaults/"
fi

if [ -d "$AGENTZERO_PIPELINE_DIR/defaults/audio" ]; then
  cp -Rn "$AGENTZERO_PIPELINE_DIR/defaults/audio/." "$AGENTZERO_PIPELINE_DIR/audio/" 2>/dev/null || true
fi

if [ -d "$AGENTZERO_PIPELINE_DIR/defaults/logo" ]; then
  cp -Rn "$AGENTZERO_PIPELINE_DIR/defaults/logo/." "$AGENTZERO_PIPELINE_DIR/logo/" 2>/dev/null || true
fi

if [ "$AGENTZERO_PIPELINE_SYNC_CODE" = "true" ] || [ "$AGENTZERO_PIPELINE_SYNC_CODE" = "1" ]; then
  cp "$AGENTZERO_PIPELINE_DIR/defaults/phone_upload_server.py" "$AGENTZERO_PIPELINE_DIR/phone_upload_server.py"
  cp "$AGENTZERO_PIPELINE_DIR/defaults/phone_render_worker.py" "$AGENTZERO_PIPELINE_DIR/phone_render_worker.py"
else
  if [ ! -f "$AGENTZERO_PIPELINE_DIR/phone_upload_server.py" ]; then
    cp "$AGENTZERO_PIPELINE_DIR/defaults/phone_upload_server.py" "$AGENTZERO_PIPELINE_DIR/phone_upload_server.py"
  fi
  if [ ! -f "$AGENTZERO_PIPELINE_DIR/phone_render_worker.py" ]; then
    cp "$AGENTZERO_PIPELINE_DIR/defaults/phone_render_worker.py" "$AGENTZERO_PIPELINE_DIR/phone_render_worker.py"
  fi
fi

if [ ! -f "$AGENTZERO_PIPELINE_CONFIG" ] && [ -f "$AGENTZERO_PIPELINE_DIR/defaults/pipeline_config.json" ]; then
  cp "$AGENTZERO_PIPELINE_DIR/defaults/pipeline_config.json" "$AGENTZERO_PIPELINE_CONFIG"
fi

echo "[phone-upload] Live pipeline dir: $AGENTZERO_PIPELINE_DIR"
echo "[phone-upload] Live pipeline config: $AGENTZERO_PIPELINE_CONFIG"
echo "[phone-upload] Sync code from image defaults: $AGENTZERO_PIPELINE_SYNC_CODE"

exec python "$AGENTZERO_PIPELINE_DIR/phone_upload_server.py"
