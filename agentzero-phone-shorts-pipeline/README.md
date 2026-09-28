# AgentZero Phone Shorts Pipeline

Server-side short-form video rendering for AgentZero. Record a clip on your phone, open a tiny upload page, upload the video, and let your server render the short with silence removal, transcript-based intro selection, captions, logo stinger, branded SFX, and optional YouTube upload.

This package was built for a low-friction Hostinger/Coolify setup where the actual rendering happens on the server instead of a local laptop.

## What It Does

- Phone-friendly browser upload page with upload percentage.
- Upload stability and `ffprobe` validation so partial or damaged uploads are ignored.
- Locked smooth silence-removal preset:
  - `silencedetect=noise=-28dB:d=0.18`
  - `35ms` padding
  - `120ms` minimum kept segment
  - Whisper word-gap fallback at `0.22s`
- Local Whisper transcription.
- Transcript-based intro:
  - listicle intro: hook -> logo stinger -> resume forward
  - generic teaser: 2-3 nuggets -> logo stinger -> main content
- Logo reveal with whoosh and chime.
- Bamboo-style cut whooshes on selected jump cuts.
- Music bed with ducking under speech.
- Burned-in short-form captions.
- Metadata/title generation through OpenRouter when configured, with local fallback when not.
- Optional YouTube upload after successful render.

## Safety Defaults

This repo intentionally does not include:

- `.env`
- API keys
- YouTube OAuth credentials or tokens
- uploaded videos
- rendered outputs
- private logo files
- third-party SFX/music files

YouTube upload is disabled in `.env.example` and `pipeline_config.example.json`. Turn it on only after OAuth is working.

## Repository Contents

```text
tools/
  phone_upload_server.py
  phone_render_worker.py
  agentzero_pipeline_defaults/
    pipeline_config.example.json
    audio/brand/.gitkeep
    logo/.gitkeep
docker/run/fs/exe/run_upload_server.sh
docker/run/fs/etc/supervisor/conf.d/upload-server.conf.example
skills/agentzero-phone-shorts-pipeline/SKILL.md
docs/
  INSTALL.md
  SERVER_SETUP.md
  SKOOL_POST.md
```

## Quick Install Shape

1. Deploy AgentZero on a Linux server with Docker/Coolify.
2. Add the two Python scripts under `tools/` in your AgentZero fork/image.
3. Add `run_upload_server.sh` to `/exe/` in the running image.
4. Add a supervisor process for the upload server.
5. Expose port `8080` as a second Coolify domain, for example `agent-zero-upload.your-domain.com`.
6. Copy `pipeline_config.example.json` to `/app/work_dir/assets/agentzero_pipeline/pipeline_config.json`.
7. Add your own assets:
   - `/app/work_dir/assets/agentzero_pipeline/logo/logo.png`
   - `/app/work_dir/assets/agentzero_pipeline/audio/brand/soundreality-whoosh-bamboo-389752.mp3`
   - `/app/work_dir/assets/agentzero_pipeline/audio/brand/lordsonny-whoosh-cinematic-161021.mp3`
   - `/app/work_dir/assets/agentzero_pipeline/audio/brand/soft-bell-ding-485895.mp3`
   - optional `/app/work_dir/assets/agentzero_pipeline/audio/music_bed.wav`
8. Open the upload page from your phone, upload a clip, and click render.

See [docs/INSTALL.md](docs/INSTALL.md) for the full walkthrough.

## Environment Variables

Start from `.env.example`. Important values:

- `OPENROUTER_API_KEY`: optional. Used only for title/description/nugget analysis.
- `WHISPER_MODEL`: `base` is a good starting point for small servers.
- `YOUTUBE_UPLOAD_ENABLED`: keep `false` until OAuth is configured.
- `YOUTUBE_PRIVACY_STATUS`: recommended `private` while testing.
- `AGENTZERO_PIPELINE_SYNC_CODE=false`: lets you tune live pipeline files without redeploying on every edit.

## Server Resources

On a 4 vCPU / 16 GB RAM Hostinger VPS, tested 30-45 second iPhone clips rendered in roughly 2-3 minutes each with less than 1 GB max RSS for the Python process. Render time depends heavily on source bitrate, clip duration, Whisper model, and caption burn-in.

Run one render at a time on small VPS plans. Queueing is safer than parallel renders.

## Legal / Asset Notes

Bring your own licensed music, logo, and SFX. The filenames in the config are examples from the development setup, not bundled assets. If you use Pixabay or similar libraries, store source/license notes next to your assets.

## License

MIT. See [LICENSE](LICENSE).
