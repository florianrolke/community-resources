# Seedance Voice Remix

Turn a folder of existing AI-generated video clips into original vertical shorts, narrated in your
own cloned voice, with word-synced captions, punch-ins, sound effects and a music bed.

Built to solve a specific problem: you have footage, but it is *finished ads* — complete with
burned-in captions and copy you cannot reuse. This pipeline pulls the usable footage out of it and
builds genuinely new videos on top.

**Everything runs locally with ffmpeg.** The only paid service is Fish Audio, and cloned-voice
narration is free on their `s2.1-pro-free` model.

---

## What it does

```
zips of clips ──► real shot boundaries ──► which shots have burned-in captions
                                                    │
                                     recover the caption-free gaps inside them
                                                    │
your script ──► cloned voice ──► word timings ──► cut picture to the voice
                                                    │
                              captions ──► SFX + music ──► finished 1080x1920 short
```

## Why each stage exists

Most of these steps exist because a naive version failed in a specific way:

| Stage | Script | The problem it solves |
|---|---|---|
| Ingest | `extract_topview_scenes.py` | unpack exports, probe, thumbnail, build a manifest |
| Shot detection | `detect_shots.py` | **a "scene" export is often a finished multi-shot ad.** Cutting at arbitrary time marks lands mid-shot and juxtaposes unrelated footage |
| Caption detection | `detect_burned_text.py` | source ads have text baked into the pixels, which contradicts any new voiceover. Finds it automatically |
| Segment recovery | `extract_clean_segments.py` | a shot with text from 2–8s is still clean from 0–2s. Nearly doubled the usable pool |
| External b-roll | `register_broll.py` | registers generated clips, auto-trimming the white intro flash they often start with |
| Transcription | `transcribe_scenes.py` | word-level timings, used to mine the source and to time captions |
| Voice | `fish_audio_client.py` | clone a voice, generate narration, check credit |
| Pacing | `speed_up_vo.py` | 1.2x without pitch shift, rescaling the word timings so no re-transcription is needed |
| The edit | `build_vo_edit.py` | cuts picture to the voiceover: phrase-aligned, hook cutting, punch-ins, tail |
| Captions | see note below | word-synced burned-in captions |
| Sound | `add_sfx.py` | SFX hits on section changes plus an optional music bed |

## Quick start

```bash
pip install -r requirements.txt          # plus ffmpeg on your PATH
cp .env.example .env                     # add your Fish Audio key

# 1. build the shot library (once per batch of footage)
python -X utf8 execution/extract_topview_scenes.py --downloads "/path/to/zips"
python -X utf8 execution/detect_shots.py
python -X utf8 execution/detect_burned_text.py --validate   # sanity-check the detector first
python -X utf8 execution/detect_burned_text.py
python -X utf8 execution/extract_clean_segments.py

# 2. clone your voice (once) — free, needs 1–2 min of clean solo speech
python -X utf8 execution/fish_audio_client.py clone-voice --name "Me" --samples sample.mp3 --save

# 3. per video
python -X utf8 execution/fish_audio_client.py tts \
    --text-file assets/stories/example-vo-script.txt \
    --voice <model_id> --model s2.1-pro-free --out assets/vo/x.mp3 --yes
#    ...transcribe x.mp3 to x.words.json (whisper, word timestamps)...
python -X utf8 execution/speed_up_vo.py --in assets/vo/x.mp3 --words assets/vo/x.words.json \
    --speed 1.2 --out assets/vo/x-fast.mp3

python -X utf8 execution/build_vo_edit.py \
    --voiceover assets/vo/x-fast.mp3 --words assets/vo/x-fast.words.json \
    --shots <id1,id2,id3,...> --name my-short \
    --max-beat 4.0 --hook-cuts 3 --hook-window 3.0 --tail 1.6 --dry-run
```

**Always `--dry-run` first.** It prints the beat table — which shot plays under which line, for how
long — and warns if the picture is shorter than the voice.

## Settings that matter

- `--max-beat 4.0` with long shots gives a calm ~3s rhythm. `3.0` mixed with short clips reads as
  choppy. This is the single biggest lever on how the edit *feels*.
- `--hook-cuts 3 --hook-window 3.0` slices the opening into three equal beats regardless of sentence
  boundaries. Pair with sound effects at 0.0 / 1.0 / 2.0 so the hook works visually and audibly.
- `--tail 1.6` holds picture past the final word. TTS leaves only ~0.3s, which cuts the call to
  action off and clips the last caption.

## Things learned the hard way

- **A shot list ranked purely by "most footage remaining" lets one long clip dominate the edit.**
  Rank by how long since a shot was last on screen, with footage left as the tiebreak.
- **Fill a continuous timeline, not per-phrase.** Allocating only across phrases leaves the pauses
  between them uncovered, and the picture ends up short.
- **Divide each span into equal chunks.** Splitting only when a shot runs dry leaves sub-second
  scraps that flash on screen.
- **Force `-ar 48000` after any `loudnorm`** — it emits 192 kHz and the AAC encoder then lands on 96 kHz.
- **The caption detector should over-flag.** A missed caption ships in the finished video; an
  over-flagged shot only costs footage you probably have more of.
- **Match your b-roll to what you are selling.** A brief written around the problem (dark rooms, 4am
  kitchens) is wrong for an offer selling optimism.

## Captions

The caption renderer used in the original build depends on a private font/thumbnail module, so it is
not included here. Any word-synced caption burner works — it needs the same whisper-shaped
`words.json` this pipeline already produces. `build_vo_edit.py` leaves the word timings valid, so
captions can be burned before or after the sound stage.

## Requirements

- Python 3.10+
- **ffmpeg and ffprobe** on your PATH
- A Fish Audio account for voice cloning (free tier is enough)
- Whisper (or any transcriber) producing word-level timestamps

## Licence

MIT. No warranty — this was built for one campaign and generalised afterwards.
