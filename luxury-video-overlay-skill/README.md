# Luxury Video Overlay Skill

Codex skill and Remotion asset kit for turning long-form talking-head videos into premium green/gold edits with overlay cards, full-screen statements, animated bullet reveals, continuous ticker bands, timed sound effects, and held emphasis zooms.

The intended architecture is:

1. **Agent Zero** performs deterministic video editing on a server: silence removal, speech padding, base jump cuts, audio enhancement, and transcript generation.
2. **Remotion** renders the visual layer: cards, tickers, full-screen slides, SFX cues, and emphasis zooms.
3. **Codex skill** guides the agent so the edit can be repeated without rebuilding the whole workflow from memory.

## What Is Included

- `skills/luxury-video-overlays/SKILL.md` - the Codex skill.
- `skills/luxury-video-overlays/assets/remotion/` - reusable Remotion components and composition.
- `skills/luxury-video-overlays/scripts/` - install, manifest generation, and secret scanning helpers.
- `skills/luxury-video-overlays/references/` - workflow, design system, example manifest, and a 3-paragraph Skool post.

No private raw videos, rendered videos, `.env` files, API keys, tokens, or server details are included.

## Install The Skill

Copy the skill folder into your Codex skills directory:

```bash
cp -R skills/luxury-video-overlays ~/.codex/skills/
```

On Windows PowerShell:

```powershell
Copy-Item -Recurse .\skills\luxury-video-overlays "$env:USERPROFILE\.codex\skills\"
```

Then ask Codex to use `luxury-video-overlays` when editing a long-form talking-head video.

## Agent Zero Handoff

Agent Zero should produce:

```text
.tmp/edited_base.mp4
.tmp/transcript.json
```

Generic example:

```bash
python execution/core/jump_cut_vad_parallel.py input.mp4 .tmp/edited_base.mp4 --enhance-audio
python execution/core/fast_transcribe.py .tmp/edited_base.mp4 .tmp/transcript.json
```

Keep your real `.env` only on your local machine or server. Use `.env.example` for public documentation.

## Install Remotion Assets

From this repo:

```bash
python skills/luxury-video-overlays/scripts/install_remotion_assets.py --remotion-root /path/to/remotion-editor
```

Then register `LuxuryTalkingHeadEditWrapper` in your Remotion `src/Root.tsx` using your project's normal props-loading pattern.

## Build A Starter Manifest

Create a beat config similar to `examples/beat-config.example.json`, then run:

```bash
python skills/luxury-video-overlays/scripts/build_luxury_manifest.py --config examples/beat-config.example.json --out props/luxury-manifest.json
```

Place the video and SFX files referenced in the manifest inside Remotion `public/`, then render:

```bash
npx remotion render LuxuryTalkingHeadEdit out/luxury-edit.mp4 --props=props/luxury-manifest.json
```

For a 1080p master:

```bash
ffmpeg -i out/luxury-edit.mp4 -vf scale=1920:1080:flags=lanczos -c:v libx264 -crf 18 -preset slow -c:a aac -b:a 192k out/luxury-edit-1080p.mp4
```

## Publish Safely

Before pushing a fork or sharing a zip:

```bash
python skills/luxury-video-overlays/scripts/scan_for_secrets.py .
git status --short
```

Do not publish `.env`, credentials, tokens, raw private videos, rendered private videos, confidential transcripts, or server IPs.

## Skool Post

The ready-to-use 3-paragraph Skool post is here:

```text
skills/luxury-video-overlays/references/skool-post.md
```
