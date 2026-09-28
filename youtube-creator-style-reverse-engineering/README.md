# YouTube Creator Style Reverse-Engineering

A system for systematically reverse-engineering the visual editing style, motion graphics,
and pacing of successful YouTube creators using Google's Gemini API — then converting the
extracted patterns into reusable, frozen "style profiles" that can drive a programmatic
video editing pipeline (FFmpeg + Remotion).

The core philosophy: **extract motion grammar once, apply it infinitely**. Instead of
manually cloning a creator's edit timeline, Gemini extracts *reusable rules* (rotation
ranges, color triggers, zoom logic, pacing targets), and those rules get applied
programmatically to new content.

## Pipeline Overview

```
1. SELECT REFERENCE VIDEOS (3-5 from one creator)
        |
        v
2. ANALYZE WITH GEMINI (two separate passes)
   - Graphics Package pass  -> typography, color system, motion, spatial rules
   - Heavy Lifting pass     -> silence removal, jump cuts, zoom logic, audio, pacing
        |
        v
3. EXTRACT TO FROZEN STYLE PROFILE (JSON)
   - Style-level parameters, not per-video timestamps
   - Versioned (v1, v2, ...) as styles evolve
        |
        v
4. CONVERT TO REMOTION MANIFEST
   - tools/gemini_to_remotion_bridge.py
   - Timestamp parsing, color-name -> hex, component-type mapping
        |
        v
5. APPLY TO YOUR OWN VIDEO
   - Detect emphasis words/moments in your transcript
   - Apply the frozen style's rules to your content
   - Render with Remotion
```

A separate, complementary pipeline (`skills/analyze-thumbnails/`) uses Gemini's vision
model to deconstruct YouTube thumbnails into Background -> Graphics -> Text layers,
extracting design patterns (color psychology, composition, scroll-stopper elements).

## What's in this repo

| Path | What it is |
|---|---|
| [`skills/creator-style-analysis/SKILL.md`](skills/creator-style-analysis/SKILL.md) | Full framework for analyzing a creator's visual & content style: typography, color, rotation, motion, pacing, hook structure. Includes a detailed Iman Gadzhi case study (the signature -3 deg kinetic typography, color psychology, Remotion component mapping) plus shorter breakdowns of other creators (Paddy Galloway, Hormozi, Aprilynne Alter, Jack Roberts/Harut). |
| [`skills/creator-style-extraction-prompts/SKILL.md`](skills/creator-style-extraction-prompts/SKILL.md) | Production-ready, copy-paste Gemini prompt templates for the two analysis passes (Graphics Package + Heavy Lifting), the JSON output schemas, the "style-level vs instance-level" distinction, common extraction mistakes, and recommended Gemini/AI Studio configuration. |
| [`prompts/gemini_master_prompt.md`](prompts/gemini_master_prompt.md) | A single, comprehensive all-in-one prompt covering pacing/zoom/audio (Part A), motion graphics inventory (Part B), pattern-recognition trigger rules (Part C), and comparative benchmarking against known creators (Part D). Useful when you want one prompt instead of two separate passes. |
| [`profiles/iman_gadzhi_style_profile.md`](profiles/iman_gadzhi_style_profile.md) | An example **frozen style profile** — the output of running the extraction prompts against Iman Gadzhi's content. Shows the target JSON shape: intro text animation specs, kinetic typography parameters, spatial/timing/color rules. |
| [`tools/gemini_to_remotion_bridge.py`](tools/gemini_to_remotion_bridge.py) | Schema converter. Takes raw Gemini analysis JSON and converts it into a Remotion-compatible "GraphicsManifest": parses timestamp strings into frame numbers, maps semantic color names (e.g. `"salmon_pink"`) to hex values, and maps Gemini's component types to Remotion component names. |
| [`skills/analyze-thumbnails/`](skills/analyze-thumbnails/) | Batch thumbnail analysis pipeline using Gemini's vision model. Deconstructs thumbnails into Background / Graphics / Text layers (based on a layered design philosophy), scoring contrast, composition, color psychology, and predicted CTR. |

## Setup

```bash
pip install google-generativeai python-dotenv pillow
# or the newer SDK:
pip install google-genai
```

Copy `.env.example` to `.env` and add your key:

```
GOOGLE_GEMINI_API_KEY=your_key_here
```

## Quick Start: Extracting a Creator's Style

1. Pick 3-5 recent videos from the creator you want to analyze.
2. In Google AI Studio (or via the API), run the **Graphics Package** prompt from
   [`skills/creator-style-extraction-prompts/SKILL.md`](skills/creator-style-extraction-prompts/SKILL.md)
   against each video. Enable URL Context / video input, structured (JSON) output;
   disable code execution, function calling, and search grounding.
3. Run the **Heavy Lifting** prompt from the same file against the same videos.
4. Aggregate the outputs across videos into one frozen style profile (see
   [`profiles/iman_gadzhi_style_profile.md`](profiles/iman_gadzhi_style_profile.md) for the target shape).
5. Convert the profile to a Remotion manifest:

```bash
python tools/gemini_to_remotion_bridge.py --input gemini_output.json --output manifest.json --fps 30
```

6. Feed the manifest + your own transcript into your Remotion project to render in the
   extracted style.

## Quick Start: Analyzing Thumbnails

```bash
python skills/analyze-thumbnails/scripts/test_gemini_models.py     # confirm API access + list models
python skills/analyze-thumbnails/scripts/test_single_thumbnail.py  # single-image smoke test + cost estimate
python skills/analyze-thumbnails/scripts/analyze_thumbnail_images.py  # full batch run
```

See [`skills/analyze-thumbnails/SKILL.md`](skills/analyze-thumbnails/SKILL.md) for the full
layered JSON schema, cost/performance numbers, and design philosophy.

## Notes

- This is an **analysis framework**, not a scraper — it does not download or redistribute
  any creator's video/image content. You provide your own reference videos/thumbnails.
- The example style profile and creator references (Iman Gadzhi, Sharran Srivatsaa,
  Hormozi, Paddy Galloway, Aprilynne Alter, MrBeast, Jack Roberts/Harut) are included
  purely as **named style benchmarks** for educational/research purposes — extracted
  patterns describe editing/motion-graphics *techniques*, not any creator's proprietary
  content.
- No API keys or credentials are included in this repo. Use `.env.example` as a template.
