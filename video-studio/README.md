# Video Studio

A cloud video-processing pipeline for solo creators: upload raw recordings, clone your voice, and let the studio re-voice, assemble, and deliver finished MP4s — all running 24/7 in the cloud.

## What it does

1. **Voice cloning** — upload 2–3 voice samples; a private clone is created via the Fish Audio API.
2. **Automated post-production** — for each project: strip the original audio, generate a cloned-voice voiceover from your script, optionally overlay AI b-roll, and render the final MP4 with ffmpeg.
3. **Delivery** — finished renders can be uploaded via FTP to your website.

## Structure (pnpm monorepo)

| Path | What |
|---|---|
| `artifacts/video-studio` | React + Vite frontend (dashboard, library, scripts, voices, projects, jobs, settings) |
| `artifacts/api-server` | Express 5 API + in-process job worker (ffmpeg, Fish Audio, FTP) |
| `lib/db` | Drizzle ORM schema (PostgreSQL) |
| `lib/api-spec` | OpenAPI spec — source of truth for the API |
| `lib/api-client-react`, `lib/api-zod` | Generated client hooks + request validation |

## Pipeline steps (jobs)

`extract_audio → transcribe? → generate_voiceover → generate_broll? → assemble → deliver?`

Jobs are queued with dependencies, run one at a time (ffmpeg is CPU-heavy), survive restarts, and can be canceled/retried from the UI.

## Configuration (environment secrets — never commit values)

| Secret | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL |
| `FISH_AUDIO_API_KEY` | Voice cloning + TTS + transcription (requires funded **API** credit) |
| `FTP_HOST` / `FTP_USER` / `FTP_PASSWORD` (+ `FTP_DIR`, `FTP_SECURE`) | Delivery target |
| `BROLL_PROVIDER` (+ provider key) | Optional AI b-roll; steps fail with a clear message until configured |
| Object storage vars | Managed by Replit App Storage |

## Running

Built for Replit: `pnpm install`, then the `web` and `API Server` workflows. Auth is Replit Auth; all routes require login.

**Deployment note:** use an always-on server (Reserved VM), not autoscale — the job worker runs inside the API server and renders take minutes.
