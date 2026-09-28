# Install Guide

This guide assumes you already have AgentZero deployed on a Linux server through Docker or Coolify.

## 1. Server Requirements

Minimum practical test box:

- Linux VPS
- Docker
- 4 vCPU recommended
- 8-16 GB RAM recommended
- 80+ GB disk if you keep uploads and rendered outputs
- FFmpeg available in the container
- Python available in the container

Optional Python packages:

```bash
pip install -r requirements-optional.txt
```

If you use the AgentZero Docker image, install these in the same venv/runtime used by AgentZero.

## 2. Add The Upload And Render Scripts

Copy these into your AgentZero fork:

```text
tools/phone_upload_server.py
tools/phone_render_worker.py
tools/agentzero_pipeline_defaults/
```

Copy the launcher into the image filesystem:

```text
docker/run/fs/exe/run_upload_server.sh
```

Make it executable:

```bash
chmod +x /exe/run_upload_server.sh
```

## 3. Start The Upload Server

If your image uses supervisor, add a program like:

```ini
[program:run_upload_server]
command=/exe/run_upload_server.sh
environment=AGENTZERO_UPLOAD_DIR="/app/work_dir/assets/agentzero_uploads/shorts_test",AGENTZERO_UPLOAD_HOST="0.0.0.0",AGENTZERO_UPLOAD_PORT="8080"
user=root
stopwaitsecs=10
stdout_logfile=/dev/stdout
stderr_logfile=/dev/stderr
```

Expose port `8080` in Coolify or your reverse proxy as a second app domain.

## 4. Create The Live Pipeline Folder

Inside the container or mounted assets volume:

```bash
mkdir -p /app/work_dir/assets/agentzero_pipeline/audio/brand
mkdir -p /app/work_dir/assets/agentzero_pipeline/logo
mkdir -p /app/work_dir/assets/agentzero_uploads/shorts_test
mkdir -p /app/work_dir/assets/agentzero_outputs
cp /git/agent-zero/tools/agentzero_pipeline_defaults/pipeline_config.example.json \
  /app/work_dir/assets/agentzero_pipeline/pipeline_config.json
```

The live config lets you change editing behavior without rebuilding Docker.

## 5. Add Your Own Assets

Put your own licensed assets here:

```text
/app/work_dir/assets/agentzero_pipeline/logo/logo.png
/app/work_dir/assets/agentzero_pipeline/audio/brand/soundreality-whoosh-bamboo-389752.mp3
/app/work_dir/assets/agentzero_pipeline/audio/brand/lordsonny-whoosh-cinematic-161021.mp3
/app/work_dir/assets/agentzero_pipeline/audio/brand/soft-bell-ding-485895.mp3
/app/work_dir/assets/agentzero_pipeline/audio/music_bed.wav
```

The filenames are examples. You can also update paths in `pipeline_config.json`.

## 6. Configure Environment Variables

Start from `.env.example`. Do not commit real `.env` files.

Recommended test values:

```bash
YOUTUBE_UPLOAD_ENABLED=false
YOUTUBE_PRIVACY_STATUS=private
WHISPER_MODEL=base
AGENTZERO_PIPELINE_SYNC_CODE=false
```

Optional LLM:

```bash
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4.1-mini
LLM_MAX_COST_PER_JOB_USD=0.20
```

The render still works without OpenRouter; it falls back to local deterministic metadata and intro selection.

## 7. Test From Your Phone

1. Open your upload domain on your phone.
2. Choose a `.mov` or `.mp4` clip.
3. Upload and wait for the percentage to complete.
4. Click render on the file row.
5. Watch `/render-status` or the page status.
6. Open `final.mp4` from the output link.

The worker rejects partial or damaged uploads using file stability checks and `ffprobe`.

## 8. YouTube Upload

Keep YouTube disabled until local renders look good.

To enable publishing:

1. Create a Google OAuth desktop/web client.
2. Generate `credentials.json`.
3. Generate `token.json` with `https://www.googleapis.com/auth/youtube.upload`.
4. Mount them into:

```text
/app/work_dir/assets/youtube/credentials.json
/app/work_dir/assets/youtube/token.json
```

Then set:

```bash
YOUTUBE_UPLOAD_ENABLED=true
YOUTUBE_PRIVACY_STATUS=private
```

Use `private` until you are fully confident.
