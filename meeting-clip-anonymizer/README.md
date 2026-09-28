# Meeting Clip Anonymizer

Turn a recorded call (Zoom/Meet/Fathom) into polished, branded short clips — while **protecting the
other participant's identity**: their **voice is pitch-shifted (anonymized)** and their **face is never
shown**. You keep their words (the value); they stay unrecognizable.

Built for repurposing coaching calls / sales calls / podcasts into YouTube/Shorts content in a
consistent on-brand editing style, with a one-command **cloud** pipeline (no load on your laptop).

---

## ⭐ The hero feature: voice augmentation (anonymization)

`voice_anonymize.py` deepens a chosen speaker's voice so it can't be recognized, **without** changing
their words, timing, or your own voice.

```bash
# deepen the other person's voice in the spans where they speak, and bleep two PII windows
python voice_anonymize.py call.mp4 out.mp4 --intervals 0:9,41:48 --pitch 0.82 \
       --bleep 12.3:12.8,40.1:41.0
```

**How it works (no ML, instant, deterministic — pure ffmpeg):**

```
asetrate=SR*P , aresample=SR , atempo=1/P
```

- `asetrate*P` + `aresample` scales **pitch by P** (and duration by 1/P).
- `atempo=1/P` restores the **original duration** without undoing the pitch shift → perfect lip-sync.
- `P < 1.0` = **deeper** voice. Use **0.80–0.86** for a clearly-anonymized but natural male voice
  (not a chipmunk). `P > 1.0` = higher.

Only the intervals you pass get shifted, so **your** voice stays untouched.

### How to get "which intervals is the other person speaking?"
1. **Speaker-view detection (most robust):** in Zoom/Meet speaker view, the active tile is whoever is
   talking. Template-match the on-screen **name label** to find when the other person is on screen →
   those are their speech intervals. Works even when two voices sound alike on the same mic.
2. **Diarization (pyannote):** supported, but **unreliable for two similar same-mic voices** — it gave
   contradictory results in our tests. Verify before trusting it; the speaker-view method is safer.
3. **Manual:** just list the intervals.

> Lesson learned the hard way: for similar voices on one call mic, **Zoom's own speaker view beats
> diarization.** A "substantial" cut to the other person's tile (≥0.8s) = they're talking → shift that.

---

## What the full pipeline does

For each clip you define (a start/end in the recording), it:
1. **Removes silence / hesitations** (Silero VAD + an energy check) for tight pacing.
2. **Hides the other person's face** — when the call cuts to them, it shows a branded card instead
   (logo + animated bullet points), so their face is never on screen.
3. **Anonymizes their voice** (the hero feature above) on the spans where they speak.
4. **Bleeps PII** (names, $ figures) in audio *and* masks it in captions.
5. **Adds your branded editing style** — kinetic captions on the question, circled key phrases + overlay
   cards on your answer, background music with ducking, gentle Ken-Burns zoom.
6. **Renders** the final 1080p clip on a remote box (so your machine stays free).

---

## Install

```bash
pip install -r requirements.txt          # ffmpeg must also be on PATH
```

- **Python 3.10+**, **ffmpeg** (system).
- For silence removal: `torch` (CPU is fine) — Silero VAD downloads on first run.
- For bullet cards: `Pillow`, `numpy`.
- Rendering uses a self-hosted [Remotion](https://remotion.dev) lane (optional — you can stop after the
  base cut/anonymize and edit elsewhere).

### Quickstart (just the anonymizer)
```bash
python voice_anonymize.py input.mp4 output.mp4 --intervals 0:9,41:48 --pitch 0.82
```

### Full pipeline (cloud)
See `SKILL.md`. Configure `config.example.json`, put your recording + transcript on the box, then:
```bash
bash pipeline/render_clip.sh <clip-name>        # assemble + render, all server-side
```

---

## Files
| File | Purpose |
|------|---------|
| `voice_anonymize.py` | ⭐ Standalone voice anonymizer (pitch shift + bleep). Use this alone or in the pipeline. |
| `pipeline/assemble_clips.py` | Cut clip, remove silence, hide face (branded cards), anonymize voice, bleep PII → base video + meta. |
| `pipeline/build_manifest.py` | Author the branded editing (captions / circled phrases / cards / music / zoom) from the transcript. |
| `pipeline/make_bullet_card.py` | Render the branded "logo + gold divider + animated bullets" card shown while the other person is hidden. |
| `pipeline/classify_speakers.py` | Speaker-view detection: template-match the on-screen name label to know who's on screen. |
| `pipeline/silence_removal.py` | Silero VAD speech-segment detection. |
| `pipeline/render_clip.sh` | One-command cloud pipeline: assemble → manifest → render. |
| `pipeline/cloud_clip.ps1` | Windows launcher: sync scripts, run on cloud, download result. |
| `config.example.json` | Clip definitions, brand colors, pitch factor, PII bleep list. |

## Privacy & ethics
This tool exists to let creators share *advice* from calls **without exposing the other person**.
Always have consent to record, and to publish — anonymization reduces, but does not eliminate,
identifiability (word choice, story details can still identify someone). Redact specifics (names,
locations, figures) via the bleep list, and get sign-off before publishing.

## License
MIT — do whatever, no warranty.
