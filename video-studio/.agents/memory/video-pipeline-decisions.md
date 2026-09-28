---
name: Video pipeline product decisions
description: User-confirmed choices for the voice-clone + video processing project (Aug 2026)
---

Decisions confirmed by the user (2026-08-09), before first build:

- **Voice provider: Fish Audio** — user explicitly chose it over ElevenLabs. Clone is created via their API (`POST /model`, multipart audio samples → model id; TTS references that model id). Key stored as `FISH_AUDIO_API_KEY` secret. Do not silently switch providers.
  **Why:** user's stated preference; they may already use Fish Audio elsewhere.
- **Intake: direct upload in the app first**; user deferred the choice ("you tell me what is better"). Google Drive sync is an approved later add-on, not required for v1.
- **B-roll: AI-generated clips**, designed pluggable — user says they can get access to better video-model APIs and wants them usable via API key later.
- **Hostinger: delivery target, not compute.** Finished MP4s auto-upload via FTP/SFTP. User states they already have "a full video editing pipeline on Hostinger" and will share its files — review those before building the render/assembly step to integrate rather than duplicate.
- Cloud autonomy matters to the user: processing must run with their computer offline (publish the app; job queue).

Added during the first build (2026-08-09):

- **Publish target must be Reserved VM, not autoscale.** The job queue is an in-process worker inside the API server and ffmpeg renders run for minutes; autoscale can kill it mid-render or scale to zero with jobs queued.
- **Replit Auth gates the whole app** — object-storage uploads require an authenticated session, so even as a single-user tool nothing works logged out. Media serving (`/api/storage/objects/...`) checks the session, not per-object ACLs, because worker-generated assets have no ACL policy.
- **B-roll gate:** pipeline treats b-roll as optional; jobs fail with a clear message unless `BROLL_PROVIDER` env + provider implementation exist. Delivery expects `FTP_HOST/FTP_USER/FTP_PASSWORD` (+ optional `FTP_DIR`, `FTP_SECURE`).

**How to apply:** any session building or extending this pipeline should keep Fish Audio as the voice layer, keep b-roll providers swappable, and check whether the user's Hostinger pipeline files have been shared before redesigning rendering.
