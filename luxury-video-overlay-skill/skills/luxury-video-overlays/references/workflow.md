# Workflow: Agent Zero to Luxury Remotion Overlays

## Architecture

Use a two-stage video pipeline:

1. Agent Zero performs deterministic editing:
   - Silence removal with speech padding
   - Base jump cuts
   - Audio enhancement
   - Transcript generation
2. Remotion performs visual packaging:
   - Luxury overlay cards
   - Full-screen statements
   - Bottom ticker
   - Timed SFX cues
   - Held emphasis zooms

This separation keeps heavy video processing reliable while allowing fast visual iteration.

## Generic Agent Zero Server Setup

Use this as a public-safe checklist. Do not publish real IP addresses, private domains, secrets, or `.env` files.

Required server context:

- Ubuntu VPS or other Linux server with persistent storage
- FFmpeg installed and available on PATH
- Python environment for Agent Zero execution scripts
- Node.js environment for Remotion rendering, if rendering on the same server
- Optional process manager or deployment layer such as Docker, Coolify, or systemd
- `.env` created locally from `.env.example`, never committed

Example setup:

```bash
git clone <agent-zero-repo-url> agent-zero
cd agent-zero
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Fill `.env` on the server only. Use placeholders in docs.

## Agent Zero Handoff

Run the base edit and transcript steps:

```bash
python execution/core/jump_cut_vad_parallel.py input.mp4 .tmp/edited_base.mp4 --enhance-audio
python execution/core/fast_transcribe.py .tmp/edited_base.mp4 .tmp/transcript.json
```

Expected handoff:

```text
.tmp/edited_base.mp4
.tmp/transcript.json
```

The transcript should contain timed speech segments. Segment formats vary; adapt the manifest builder if your transcript schema differs.

## Remotion Install

Install the skill assets into an existing Remotion project:

```bash
python skills/luxury-video-overlays/scripts/install_remotion_assets.py --remotion-root <path-to-remotion-editor>
```

Register the composition in `src/Root.tsx`:

```tsx
import LuxuryTalkingHeadEditWrapper from "./compositions/LuxuryTalkingHeadEdit";

<Composition
  id="LuxuryTalkingHeadEdit"
  component={LuxuryTalkingHeadEditWrapper}
  durationInFrames={manifest.durationFrames}
  fps={manifest.fps}
  width={manifest.width}
  height={manifest.height}
  defaultProps={{ manifest }}
/>
```

Use your own project's props-loading pattern if it already has one.

## Render

Place the edited base video and SFX files in Remotion `public/`, then render:

```bash
npx remotion render LuxuryTalkingHeadEdit out/luxury-edit.mp4 --props=props/luxury-manifest.json
```

Export 1080p if your render is not already 1920x1080:

```bash
ffmpeg -i out/luxury-edit.mp4 -vf scale=1920:1080:flags=lanczos -c:v libx264 -crf 18 -preset slow -c:a aac -b:a 192k out/luxury-edit-1080p.mp4
```

## Version History

For every strong iteration, save:

- Manifest JSON
- Render command
- Output file path
- Screenshots around key overlays
- Short process log explaining what changed and why

Keep restore folders descriptive, for example:

```text
render-logs/restore-v5-2026-06-01/
```
