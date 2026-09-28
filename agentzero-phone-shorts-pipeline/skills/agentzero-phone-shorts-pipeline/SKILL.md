---
name: agentzero-phone-shorts-pipeline
description: Use when setting up, operating, or improving the AgentZero phone-to-server short-form video pipeline: mobile upload page, server-side FFmpeg rendering, smooth silence removal, Whisper transcription, intro/logo/SFX assembly, captions, metadata, and optional YouTube upload.
---

# AgentZero Phone Shorts Pipeline

Use this skill when the user wants to install, debug, tune, or extend a phone-to-server short-form video workflow for AgentZero.

## Core Outcome

The user records on a phone, uploads through a small browser page, and the server renders the short. The local machine should not render.

## Architecture

- Upload server: `tools/phone_upload_server.py`
- Render worker: `tools/phone_render_worker.py`
- Live pipeline folder: `/app/work_dir/assets/agentzero_pipeline/`
- Upload inbox: `/app/work_dir/assets/agentzero_uploads/shorts_test/`
- Outputs: `/app/work_dir/assets/agentzero_outputs/`
- Editable config: `/app/work_dir/assets/agentzero_pipeline/pipeline_config.json`

## Locked Edit Preset

Preserve the smooth silence-removal behavior unless the user explicitly asks to change it:

- `silencedetect=noise=-28dB:d=0.18`
- `35ms` padding
- `120ms` minimum kept segment
- Whisper word-gap fallback with `0.22s` max gap
- Remap caption timestamps after structural cuts

## Render Modes

Prefer forward-moving edits.

- Listicle: hook/promise -> logo stinger -> resume at first item
- Generic teaser: 2-3 value nuggets -> logo stinger -> main content
- Damaged upload: fail before render using stability checks and `ffprobe`

## Assets

Users bring their own licensed assets:

- `logo/logo.png`
- bamboo/cut whoosh
- logo cinematic whoosh
- reveal chime
- optional music bed

Never commit actual private media, OAuth tokens, `.env`, uploads, or outputs.

## No-Redeploy Loop

Daily tuning should happen in the mounted live pipeline folder:

- `pipeline_config.json`
- `phone_render_worker.py`
- `audio/`
- `logo/`

Set `AGENTZERO_PIPELINE_SYNC_CODE=false` so redeploys do not overwrite live tuning files.

Redeploy only when baking stable code into the image or changing Docker/supervisor wiring.

## Verification Checklist

After rendering, inspect:

- `metadata.json`
- `asset_manifest.json`
- `sfx_events.json`
- `resource_usage.json`
- final video URL

Confirm:

- logo appears in the final video
- SFX paths point to real branded assets, not missing files
- captions are burned and synced
- YouTube upload is skipped unless OAuth is configured

## Security Rules

- Do not expose `.env`, API keys, OAuth files, or private media.
- Default YouTube publishing to disabled/private in public examples.
- Public repos should contain placeholders and instructions, not private assets.
