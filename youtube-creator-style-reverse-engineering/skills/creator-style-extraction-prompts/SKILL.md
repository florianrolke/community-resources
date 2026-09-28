# Creator Style Extraction Prompts

**Objective:** Production-ready Gemini prompt templates for reverse-engineering any creator's video style into frozen, reusable parameter profiles that Agent Zero and Remotion can execute.

**Mission Connection:** Enables repeatable quality across video production by separating style extraction from execution — extract once, apply infinitely.

---

## Table of Contents

1. [Separation of Concerns](#1-separation-of-concerns)
2. [Master Prompt Template - Graphics Package](#2-master-prompt-template---graphics-package)
3. [Master Prompt Template - Heavy Lifting](#3-master-prompt-template---heavy-lifting)
4. [JSON Output Schemas](#4-json-output-schemas)
5. [Creator Style Profiles](#5-creator-style-profiles)
6. [Workflow](#6-workflow)
7. [Common Extraction Mistakes](#7-common-extraction-mistakes)
8. [Gemini Configuration](#8-gemini-configuration)

---

## 1. Separation of Concerns

### Why Separate Analysis Passes

**The 3-Layer Architecture:**
```
Layer 1: Directive (What to do)    → SOPs in directives/
Layer 2: Orchestration (Decisions) → Agent Zero / Claude
Layer 3: Execution (Do the work)   → Python scripts, FFmpeg, Remotion
```

**90% accuracy per step = 59% success over 5 steps.**
Push complexity into deterministic scripts. Keep LLMs focused on decision-making.

### Heavy Lifting vs Visual Information Layer (VIL)

**Heavy Lifting (Agent Zero Domain):**
- Silence removal thresholds
- Jump cut density (which cuts to make)
- Zoom logic (scale states and transitions)
- Audio treatment (loudness, ducking)
- Pacing curves (CPM targets)

**Visual Information Layer (VIL - Graphics Domain):**
- Typography system
- Color palette behavior
- Animation language (entry/exit/easing)
- Trigger logic (when graphics appear)
- Spatial rules (positioning, safe zones)
- Sound design (whooshes, pops, stingers)

### Style-Level vs Instance-Level JSON

**Instance-Level (what happened in one video):**
```json
{
  "timestamp_start": "01:00.500",
  "timestamp_end": "01:03.000",
  "rotation_degrees": -3
}
```
✅ Useful for validation
❌ NOT what Agent Zero should consume

**Style-Level (reusable pattern):**
```json
{
  "rotation_range_deg": [-4, -2],
  "typical_duration_seconds": 2.2,
  "highlight_trigger": "intonation_synced"
}
```
✅ THIS is what Agent Zero needs
✅ Frozen, versioned, reusable

**Key Principle:**
> Gemini extracts motion grammar, Agent Zero applies it to your content.

---

## 2. Master Prompt Template - Graphics Package

### Copy-Paste Gemini Prompt for Graphics Analysis

```
You are a senior motion graphics systems analyst.

Your task is to reverse-engineer the MOTION GRAPHICS STYLE
used in this YouTube video.

This analysis is NOT for editing a specific video.
It is for extracting reusable parameters that can be
applied programmatically in Remotion (React / TSX).

You must NOT:
- Output timestamps for individual instances
- Output per-video placement instructions
- Invent new animation styles
- Describe aesthetics subjectively
- Recommend improvements

You must:
- Describe ONLY what is visibly used
- Express findings as reusable parameters
- Focus on behavior, not content
- Separate overlay graphics from full-screen takeovers

━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS SCOPE (ONLY THESE)
━━━━━━━━━━━━━━━━━━━━━━

A) INTRO TEXT ANIMATION STYLE (FIRST 30 SECONDS)
B) BACKGROUND / TAKEOVER GRAPHICS STYLE

━━━━━━━━━━━━━━━━━━━━━━
A) INTRO TEXT ANIMATION STYLE
━━━━━━━━━━━━━━━━━━━━━━

Analyze the first 30 seconds and extract:

1. TEXT BEHAVIOR
- word_level_animation (true/false)
- emphasis_trigger (intonation | keywords | phrases)
- words_visible_at_once (typical range)
- animation_granularity (word | phrase)

2. COLOR SYSTEM (CRITICAL)
- base_text_color_role (e.g. white, neutral)
- highlight_text_color_role (e.g. accent, warning)
- highlight_persistence (momentary | sustained)
- color_change_trigger (intonation | emphasis_word)
- contrast_level (high | medium)
- palette_references (actual hex if identifiable)

3. TRANSFORM CHARACTERISTICS
- typical_rotation_range_deg (e.g. -4 to -2)
- scale_range (e.g. 0.9 → 1.05)
- drift_present (true/false)
- drift_axis (x | y | none)
- transform_metaphor (describe the motion feeling)

4. SPATIAL RULES
- typical_anchor (center | lower_center)
- y_position_range_percent
- max_width_percent
- safe_zone_respected (true)

5. TIMING PROFILE
- typical_entry_duration_frames
- typical_hold_duration_frames
- typical_exit_duration_frames
- max_total_duration_seconds
- easing_function (if inferable)

━━━━━━━━━━━━━━━━━━━━━━
B) BACKGROUND / TAKEOVER GRAPHICS STYLE
━━━━━━━━━━━━━━━━━━━━━━

Analyze scenes where the talking head disappears and extract:

1. VISIBILITY MODE
- replaces_video (always true for this section)

2. BACKGROUND TREATMENT
- background_type (solid | texture | desk_surface)
- primary_color_role
- secondary_color_role
- noise_or_grain (true/false)
- lighting_style (if visible)

3. ELEMENT TYPES
- dominant_elements (text | tables | diagrams | icons)
- layout_logic (centered | grid | stacked)
- typography_style (printed | digital | handwritten)

4. MOTION PROFILE
- entry_motion_type (slide | scale | fade | cut)
- internal_element_animation (typewriter | reveal | none)
- motion_speed (slow | medium | fast)
- easing_profile (if inferable)

5. TIMING CONSTRAINTS
- minimum_scene_duration_seconds
- typical_scene_duration_seconds
- transition_in_type (cut | slide)
- transition_out_type (cut | slide)

━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━

Output structured JSON with TWO TOP-LEVEL OBJECTS:

{
  "intro_text_animation_style": {},
  "background_graphics_style": {}
}

No timestamps.
No prose.
No commentary.
No creative suggestions.

If a parameter cannot be determined, omit it.
Precision and restraint are mandatory.
```

---

## 3. Master Prompt Template - Heavy Lifting

### Copy-Paste Gemini Prompt for Heavy Lifting Analysis

```
You are a senior video editor and motion graphics director analyzing structural editing decisions.

Your task is to reverse-engineer the EDITING STYLE
used in this YouTube video.

This analysis feeds a programmatic video editing pipeline (Agent Zero → FFmpeg → Remotion).
You are extracting PATTERNS, not creating a frame-by-frame edit plan.

You must NOT:
- Output specific timestamps for YOUR video
- Recommend graphics or visual effects
- Describe aesthetics or "feel"
- Invent effects not present in the reference

You must:
- Describe cutting patterns as rules
- Express silence removal as thresholds
- Define zoom logic as scale states
- Focus on editorial mechanics, not visuals

━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS OBJECTIVES
━━━━━━━━━━━━━━━━━━━━━━

1. SILENCE REMOVAL PARAMETERS
- Minimum silence duration that gets cut (in seconds)
- Padding preserved around speech (in milliseconds)
- Whether micro-pauses (<200ms) are removed
- Special handling for emotional or narrative moments

2. JUMP CUT DENSITY
- Percentage of detected silences that result in cuts
- Frequency pattern (every cut? every 2nd? every 3rd?)
- Sections where jump cuts are avoided (list triggers)
- Target cuts per minute (CPM) if detectable

3. ZOOM LOGIC (SCALE STATES)
Define zoom as discrete states, not animations:
- 1.00 → Base framing
- 1.05-1.08 → Light emphasis
- 1.10 → Punch
- 1.25+ → Aggressive (use sparingly)

For each zoom state:
- When is it applied? (paragraph start, rule definition, etc.)
- When does it reset to 1.0?
- Is there creeping zoom (gradual scale increase)?
- Creeping zoom threshold (segments >5s?)

4. ZOOM-ON-CUT FREQUENCY
- What percentage of jump cuts include a zoom change?
- Scale differential (e.g. 1.0 → 1.08)
- Avoided on: micro-cuts, emotional moments, storytelling

5. TRANSITIONS
- Default transition (hard cut assumed)
- When are crossfades used? (duration in frames)
- When are dip-to-black used? (chapter markers)
- Any other transition types?

6. AUDIO TREATMENT
- Target loudness (LUFS)
- Music ducking parameters (dB reduction, attack/release)
- Audio enhancement chain (compression, EQ, normalization)
- Whether background music is used

7. PACING ANALYSIS
- Overall cuts per minute (CPM)
- First 30 seconds CPM (usually higher)
- Cut density variation across video
- Visual change frequency (max seconds static)

━━━━━━━━━━━━━━━━━━━━━━
SPECIAL FOCUS: FIRST 30 SECONDS
━━━━━━━━━━━━━━━━━━━━━━

The first 30 seconds require different intensity:
- Target CPM (18-25 typical for YouTube)
- Earlier emphasis via zoom/cuts
- Whether graphics or kinetic text appear sooner
- Core promise clarity timing

━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━

{
  "silence_removal": {
    "min_silence_seconds": 0.0,
    "padding_ms": 0,
    "remove_micro_pauses": true/false
  },

  "jump_cut_profile": {
    "cut_percentage_of_silences": "40-60%",
    "avoid_on": [],
    "target_cpm": 0
  },

  "zoom_logic": {
    "scale_states": {
      "base": 1.0,
      "emphasis": 1.08,
      "punch": 1.10
    },
    "zoom_on_cut_percentage": "25-40%",
    "creeping_zoom": {
      "enabled": true/false,
      "threshold_seconds": 5,
      "start_scale": 1.0,
      "end_scale": 1.15
    },
    "reset_triggers": []
  },

  "transitions": {
    "default": "hard_cut",
    "crossfade_usage": "",
    "dip_to_black_usage": ""
  },

  "audio_profile": {
    "target_lufs": -16,
    "music_ducking_db": -15,
    "enhancement_chain": []
  },

  "pacing": {
    "overall_cpm": 0,
    "first_30s_cpm": 0,
    "max_static_seconds": 3
  }
}

No prose. No explanations. No timestamps.
```

---

## 4. JSON Output Schemas

### Graphics Package Structure

```json
{
  "intro_text_animation_style": {
    "text_behavior": {
      "word_level_animation": true,
      "emphasis_trigger": "phrase_boundary",
      "words_visible_at_once": "3-6",
      "animation_granularity": "word"
    },
    "color_system": {
      "base_text_color_role": "#FFFFFF",
      "highlight_text_color_role": "#FF9999",
      "highlight_persistence": "sustained",
      "color_change_trigger": "intonation",
      "contrast_level": "high"
    },
    "transform_characteristics": {
      "typical_rotation_range_deg": "-4 to -2",
      "scale_range": "0.9 -> 1.0",
      "drift_present": true,
      "drift_axis": "y",
      "transform_metaphor": "tilted_emphasis"
    },
    "spatial_rules": {
      "typical_anchor": "center",
      "y_position_range_percent": "50-60",
      "max_width_percent": 85,
      "safe_zone_respected": true
    },
    "timing_profile": {
      "typical_entry_duration_frames": 6,
      "typical_hold_duration_frames": 66,
      "typical_exit_duration_frames": 10,
      "max_total_duration_seconds": 2.5,
      "easing_function": "ease_out_back"
    }
  },

  "background_graphics_style": {
    "visibility_mode": {
      "replaces_video": true
    },
    "background_treatment": {
      "background_type": "desk_surface_with_paper",
      "primary_color_role": "#121212",
      "secondary_color_role": "#FFFFFF",
      "noise_or_grain": true,
      "lighting_style": "top_down_vignette"
    },
    "element_types": {
      "dominant_elements": "tables_and_text",
      "layout_logic": "centered_paper",
      "typography_style": "printed_document"
    },
    "motion_profile": {
      "entry_motion_type": "slide_in_physics",
      "internal_element_animation": "typewriter",
      "motion_speed": "medium",
      "easing_profile": "cubic-bezier(0.25, 1, 0.5, 1)"
    },
    "timing_constraints": {
      "minimum_scene_duration_seconds": 3.0,
      "typical_scene_duration_seconds": 12.0,
      "transition_in_type": "slide",
      "transition_out_type": "slide"
    }
  }
}
```

### Heavy Lifting Profile Structure

```json
{
  "creator_name": "Iman Gadzhi",
  "video_analyzed": "https://youtube.com/watch?v=...",
  "analysis_date": "2026-02-16",

  "silence_removal": {
    "min_silence_seconds": 0.15,
    "padding_ms": 50,
    "remove_micro_pauses": true,
    "avoid_on": ["emotional_storytelling", "rhetorical_pause"]
  },

  "jump_cut_profile": {
    "cut_percentage_of_silences": "60-70%",
    "frequency_pattern": "every_2nd_or_3rd",
    "avoid_on": ["emotional_moments", "narrative_passages"],
    "target_cpm": 22
  },

  "zoom_logic": {
    "scale_states": {
      "base": 1.0,
      "light_emphasis": 1.08,
      "punch": 1.10,
      "aggressive": 1.25
    },
    "zoom_on_cut_percentage": "30%",
    "scale_differential": 0.08,
    "creeping_zoom": {
      "enabled": true,
      "threshold_seconds": 5,
      "start_scale": 1.0,
      "end_scale": 1.15
    },
    "apply_on": ["paragraph_start", "rule_definition"],
    "reset_triggers": ["chapter_marker", "topic_transition"]
  },

  "transitions": {
    "default": "hard_cut",
    "crossfade_frames": 4,
    "crossfade_usage": "large_time_compression",
    "dip_to_black_usage": "chapter_boundaries"
  },

  "audio_profile": {
    "target_lufs": -16,
    "music_ducking_db": -15,
    "ducking_attack_ms": 10,
    "ducking_release_ms": 800,
    "enhancement_chain": [
      "highpass=80Hz",
      "lowpass=12kHz",
      "eq_200Hz=-1dB",
      "eq_3kHz=+2dB",
      "acompressor=3:1",
      "loudnorm=-16LUFS"
    ]
  },

  "pacing": {
    "overall_cpm": 20,
    "first_30s_cpm": 24,
    "max_static_seconds": 3,
    "visual_change_frequency": "every_2-3s"
  }
}
```

---

## 5. Creator Style Profiles

### Iman Gadzhi (2 Videos Analyzed)

**Graphics Profile:**
- **Text Animation:** Tilted (-3°), word-by-word highlighting, intonation-synced color changes (white base, salmon pink/yellow accent)
- **Background Graphics:** Desk surface with paper metaphor, typewriter reveals, medium motion speed
- **Timing:** Fast (2.2s average text duration), aggressive first 30s

**Heavy Lifting Profile:**
- **Silence Removal:** Aggressive (0.15s threshold, 50ms padding)
- **Jump Cuts:** High density (60-70% of silences cut)
- **Zoom Logic:** Moderate use (30% of cuts), creeping zoom enabled
- **Pacing:** 22 CPM overall, 24 CPM first 30s

### Sharran Srivatsaa

**Graphics Profile:**
- **Text Animation:** Minimal kinetic text, clean lower thirds, restrained overlays
- **Background Graphics:** Rare takeovers, when used: clean diagrams or framework visuals
- **Timing:** Longer hold (3-4s), fewer interruptions

**Heavy Lifting Profile:**
- **Silence Removal:** Moderate (0.25-0.3s threshold)
- **Jump Cuts:** Conservative (40-50% of silences cut)
- **Zoom Logic:** Deliberate use (25% of cuts), scale states for emphasis
- **Pacing:** 18 CPM overall, authority-driven, allows breathing room

### Generic Business/Educational Template

**Balanced Defaults:**
- **Silence Threshold:** 0.3s
- **Jump Cut Density:** 40-60% of silences
- **Zoom on Cut:** 25-40%
- **CPM:** 18-22
- **Graphics:** Max 1 per 7.5s, never cover face
- **Audio:** -16 LUFS, music ducking -15dB

---

## 6. Workflow

### Step-by-Step Style Extraction Process

**1. Select Reference Videos (3-5 recommended)**
- Same creator
- Similar content type (educational, vlog, etc.)
- Recent (style evolves)
- Different topics (to capture consistent patterns, not one-off moments)

**2. Configure Gemini in Google AI Studio**

Enable:
- ✅ URL Context (required for visual analysis)
- ✅ Structured Outputs (JSON mode)
- ✅ File/Video Input (if available for higher accuracy)

Disable:
- ❌ Code Execution (hallucinated precision)
- ❌ Function Calling (wrong abstraction)
- ❌ Google Search Grounding (pollutes visual analysis)

**3. Run Gemini Graphics Analysis**

Paste the **Graphics Package prompt** (Section 2) and provide video URL or file.

Expected output: Style-level JSON with no timestamps.

**4. Run Gemini Heavy Lifting Analysis**

Paste the **Heavy Lifting prompt** (Section 3) and provide same video.

Expected output: Editing patterns, thresholds, ratios.

**5. Aggregate Patterns Across Videos**

If analyzing 3 videos:
- Look for consistency (e.g., all use -3° rotation)
- Average numeric values (e.g., 2.1s, 2.3s, 2.2s → 2.2s typical)
- Note variations (e.g., first 30s always faster)

**6. Create Frozen Profile**

Merge aggregated data into a single JSON file:
```
styles/
  iman-gadzhi-v1.json
  sharran-srivatsaa-v1.json
```

Version them (v1, v2) as styles evolve.

**7. Test with Agent Zero**

Give Agent Zero:
- Your video transcript
- The frozen style profile
- Heavy lifting editing rules

Agent Zero outputs: Remotion JSON with specific timestamps for YOUR video.

**8. Validate and Iterate**

- Does the output match the reference style?
- Are there missed patterns?
- Update the frozen profile if needed
- Re-run Agent Zero

---

## 7. Common Extraction Mistakes

### Mistake 1: Confusing Style with Instance

❌ **Wrong:**
```json
{
  "timestamp_start": "01:13.000",
  "rotation_degrees": -3
}
```

✅ **Right:**
```json
{
  "typical_rotation_range_deg": "-4 to -2",
  "rotation_trigger": "emphasis_phrase"
}
```

**Why it matters:** Agent Zero can't apply a timestamp from Iman's video to yours. It needs the **rule**, not the **example**.

### Mistake 2: Over-Specifying Unique Moments

❌ **Wrong:**
"At 2:15, text rotates -6° and turns purple during a product reveal."

✅ **Right:**
"Rotation typically -2 to -4°. Color changes on emphasis words."

**Why it matters:** One-off moments aren't style — they're content-specific. Extract the pattern, not the exception.

### Mistake 3: Missing Trigger Logic

❌ **Wrong:**
"Kinetic text appears."

✅ **Right:**
"Kinetic text appears on: emphasis words, rule introductions, numbered lists."

**Why it matters:** Agent Zero needs to know **when** to apply the style, not just **that** it exists.

### Mistake 4: Ignoring Timing Constraints

❌ **Wrong:**
"Text animation with highlighting."

✅ **Right:**
"Text animation: 6 frames entry, 66 frames hold, 10 frames exit. Max 2.5s total."

**Why it matters:** Remotion is frame-accurate. Timing isn't decoration — it's specification.

### Mistake 5: Mixing Graphics and Editing Analysis

❌ **Wrong:**
Running one analysis for "everything."

✅ **Right:**
Separate passes:
- Graphics analysis → VIL style profile
- Heavy lifting analysis → editing profile

**Why it matters:** These feed different parts of the pipeline. Mixing them creates ambiguous outputs.

### Mistake 6: Asking for Timestamps

❌ **Wrong:**
"Tell me when to place kinetic text in my video."

✅ **Right:**
"Extract the pattern: what triggers kinetic text placement?"

**Why it matters:** Gemini reverse-engineers. Agent Zero applies. Don't collapse roles.

### Mistake 7: Accepting Aesthetic Language

❌ **Wrong (from Gemini):**
"The text has a dynamic, energetic feel with smooth animations."

✅ **Right (force Gemini):**
"Scale: 0.9 → 1.0 over 6 frames. Easing: ease_out_back."

**Why it matters:** "Dynamic" doesn't compile. Parameters do.

---

## 8. Gemini Configuration

### Recommended Settings (Google AI Studio)

| Setting | Enable? | Reason |
|---------|---------|--------|
| **URL Context** | ✅ YES | Required for visual analysis |
| **Structured Outputs (JSON)** | ✅ YES | Deterministic, Agent Zero friendly |
| **File / Video Input** | ✅ YES (if available) | Highest accuracy for motion details |
| **Code Execution** | ❌ NO | Hallucinated precision, wrong layer |
| **Function Calling** | ❌ NO | Wrong abstraction (analysis, not action) |
| **Google Search Grounding** | ❌ NO | Pollutes visual truth with blog opinions |

### Why This Configuration Works

**URL Context:**
- Gemini can see frames, motion, color, rotation
- Without it: hallucinated "Iman Gadzhi style" based on internet articles

**Structured Outputs:**
- Forces parameter thinking
- Prevents prose/fluff
- Diffable, versionable, testable

**File/Video Input:**
- Frame-by-frame inspection
- Better detection of subtle motion (drift, tilt, color changes)

**No Code Execution:**
- Gemini invents math that looks precise but is wrong
- Timing belongs in Remotion, not Gemini

**No Function Calling:**
- Analysis ≠ action
- Forces brittle schemas prematurely

**No Search Grounding:**
- You want what's ON SCREEN, not what people SAY about it
- Injects bias and opinions

---

## Example: Using the Extracted Profiles

### Scenario: You have a 2-minute video to edit

**Inputs to Agent Zero:**
1. Your video transcript (with timestamps)
2. Iman Gadzhi frozen style profile (this skill extracted it)
3. Heavy lifting editing rules (silence thresholds, zoom logic)

**Agent Zero's Job:**
- Detect emphasis words in YOUR transcript
- Apply Iman's rotation/color rules to those moments
- Calculate timestamps for YOUR video
- Output Remotion JSON

**Remotion's Job:**
- Execute the JSON
- Render intro kinetic text with -3° tilt, salmon pink highlights
- Apply creeping zoom on segments >5s
- Cut silences ≥0.15s

**Result:**
Your video, edited in Iman's style, without manually reverse-engineering every parameter.

---

## Reference Materials

**Primary Sources:**
- `Resources/ProgrammaticEditingAnalysis/Mographanalysis1.md` (graphics analysis framework)
- `Resources/ProgrammaticEditingAnalysis/mographanalysis2.md` (parameter extraction deep dive)
- `Resources/ProgrammaticEditingAnalysis/heavyliftingeditinganalysis.md` (editing analysis framework)

**Related Skills:**
- `editing-talking-head-videos` (execution layer — uses these profiles)
- `processing-batches-with-checkpoints` (for analyzing multiple videos)

**Tools:**
- Google AI Studio (Gemini)
- Remotion (execution)
- Agent Zero (decision layer, future integration)

---

## Summary

**What this skill provides:**
1. Copy-paste Gemini prompts for graphics and editing analysis
2. JSON schemas that map directly to Remotion
3. Separation of style extraction (Gemini) from application (Agent Zero)
4. Frozen creator profiles (Iman Gadzhi, Sharran Srivatsaa)
5. Common mistakes and how to avoid them

**What this skill does NOT do:**
- Edit videos directly (that's execution layer)
- Apply styles to your videos (that's Agent Zero's job)
- Design new animations (only reverse-engineer existing)

**Core Philosophy:**
> Extract motion grammar once. Apply infinitely. Never clone timelines.

This is how professional broadcast systems scale. You're building the same thing for YouTube.
