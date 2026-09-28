# Iman Gadzhi Style Profile

> Frozen style parameters extracted from Iman Gadzhi video analysis. Use this profile for Agent Zero + Remotion.

---

## Style Summary

**Authority-driven, high-energy business content** with:
- Aggressive text animations in first 30 seconds
- Word-level highlighting synced to speech
- Tilted/angled kinetic typography
- Physical metaphor backgrounds (desk, paper, collage)
- High contrast color emphasis

---

## PART A: INTRO TEXT ANIMATIONS (First 30 Seconds)

> These text animations appear OVER the talking head video. They function like enhanced captions but with motion design.

### A1. Headline Phrases

For major sentences/phrases at the start:

```json
{
  "component_type": "text_highlight_caption",
  "text_role": "headline_phrase",

  "text_structure": {
    "animation_unit": "phrase",
    "highlight_sequence": "speech_synced",
    "max_words_visible_at_once": 4,
    "line_wrapping_behavior": "balance"
  },

  "spatial": {
    "anchor": "center",
    "x_percent": 50,
    "y_percent": 50,
    "max_width_percent": 80,
    "rotation_degrees": 0
  },

  "transform": {
    "entry_style": "fade_in_scale_up",
    "scale": { "from": 1.0, "to": 1.05 },
    "opacity": { "from": 0, "to": 1 },
    "easing": "ease_out"
  },

  "timing": {
    "entry_duration_frames": 10,
    "hold_duration_seconds": 2.5,
    "exit_behavior": "hard_cut"
  },

  "color": {
    "base_text": "white",
    "highlight": "none",
    "intonation_alignment": false
  },

  "context": {
    "talking_head_visible": true,
    "face_avoidance": true,
    "first_30s_priority": true
  }
}
```

### A2. Emphasis Phrases (The Signature Style)

For keywords and emphasis moments—**this is the Iman Gadzhi signature**:

```json
{
  "component_type": "kinetic_text_phrase",
  "text_role": "emphasis_phrase",

  "text_structure": {
    "animation_unit": "word",
    "highlight_sequence": "left_to_right",
    "max_words_visible_at_once": 3,
    "line_wrapping_behavior": "single_line"
  },

  "spatial": {
    "anchor": "center",
    "x_percent": 50,
    "y_percent": 55,
    "max_width_percent": 90,
    "rotation_degrees": -3,
    "angle_static": true,
    "position_drift": true
  },

  "transform": {
    "entry_style": "pop_in",
    "scale": { "from": 0.9, "to": 1.0 },
    "opacity": { "from": 0, "to": 1 },
    "easing": "ease_out_back"
  },

  "timing": {
    "entry_duration_frames": 6,
    "hold_duration_seconds": 2.0,
    "exit_behavior": "hard_cut"
  },

  "color": {
    "base_text": "white",
    "highlight": "accent",
    "color_change_strategy": "per_word",
    "intonation_alignment": true
  },

  "context": {
    "talking_head_visible": true,
    "face_avoidance": false,
    "first_30s_priority": true
  }
}
```

### A3. Color & Angle Patterns

**Master reference for text styling:**

| Property | Value | Notes |
|----------|-------|-------|
| Base text color | `#FFFFFF` (white) | High contrast |
| Highlight colors | `#FF9999` (salmon pink), `#FFFF00` (bright yellow) | On semantic keywords only |
| Rotation (narrative) | 0° | Standard sentences |
| Rotation (emphasis) | -2° to -4° | Tilted for keywords |
| Scale pop on emphasis | 1.1x | On vowel stress |
| Easing | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Slight overshoot |

**Intonation Alignment Rule:**
> Visual scale pop (1.1x) occurs exactly on the vowel stress of the emphasized word.

---

## PART B: BACKGROUND TAKEOVER GRAPHICS

> These graphics REPLACE the talking head entirely. The video disappears and only the animated graphic is visible.

### B1. Explainer Graphic Scene (Paper/Desk Metaphor)

```json
{
  "component_type": "explainer_graphic_scene",
  "visibility_mode": "replaces_video",

  "background": {
    "type": "desk_surface_with_paper_prop",
    "primary_color": "#121212",
    "secondary_color": "white_paper_texture",
    "noise_or_grain": true,
    "lighting_style": "top_down_vignette"
  },

  "foreground_elements": [
    {
      "element_type": "text",
      "hierarchy_order": 1,
      "anchor": "center",
      "x_percent": 50,
      "y_percent": 50,
      "max_width_percent": 80,
      "rotation_degrees": 0,
      "content_type": "headline"
    }
  ],

  "motion": {
    "entry_animation": "typewriter_reveal",
    "animated_properties": ["opacity", "character_count"],
    "entry_duration_frames": 12,
    "easing": "linear"
  },

  "timing": {
    "minimum_duration_seconds": 3.0,
    "typical_duration_seconds": 2.5,
    "exit_behavior": "hard_cut"
  },

  "trigger": "chapter_announcement"
}
```

### B2. Framework Scene (Collage/Cutout Style)

```json
{
  "component_type": "explainer_graphic_scene",
  "visibility_mode": "replaces_video",

  "background": {
    "type": "desk_surface",
    "motion": "subtle_parallax",
    "dominant_tone": "neutral",
    "physical_metaphor": "collage_on_desk"
  },

  "foreground_elements": [
    {
      "element_type": "icon_cutout",
      "hierarchy_order": 2,
      "anchor": "center",
      "x_percent": 50,
      "y_percent": 50,
      "max_width_percent": 40,
      "rotation_degrees": -5
    },
    {
      "element_type": "text_label",
      "hierarchy_order": 1,
      "anchor": "top_center",
      "x_percent": 50,
      "y_percent": 20,
      "max_width_percent": 90,
      "rotation_degrees": 0
    }
  ],

  "motion": {
    "entry_animation": "scale_up_bounce",
    "animated_properties": ["scale", "rotation"],
    "entry_duration_frames": 15,
    "exit_behavior": "slide_out_up",
    "easing": "ease_out_back"
  },

  "timing": {
    "hold_duration_seconds": 9,
    "is_reused": true
  },

  "trigger": "visual_metaphor_description"
}
```

### B3. Table/Comparison Scene

```json
{
  "component_type": "table_scene",
  "visibility_mode": "replaces_video",

  "background": {
    "type": "paper",
    "motion": "static",
    "dominant_tone": "light",
    "physical_metaphor": "printed_document"
  },

  "foreground_elements": [
    {
      "element_type": "logo_icon",
      "anchor": "center_left",
      "x_percent": 30,
      "y_percent": 50,
      "max_width_percent": 15
    },
    {
      "element_type": "logo_icon",
      "anchor": "center_right",
      "x_percent": 70,
      "y_percent": 50,
      "max_width_percent": 15
    }
  ],

  "motion": {
    "entry_animation": "stamp_impact",
    "animated_properties": ["scale", "opacity"],
    "entry_duration_frames": 8,
    "easing": "ease_out_expo"
  },

  "timing": {
    "hold_duration_seconds": 9,
    "exit_behavior": "hard_cut"
  },

  "trigger": "comparison_list"
}
```

### B4. Background Graphics Style Summary

| Property | Value |
|----------|-------|
| Background type | Desk surface with paper props |
| Primary color | Dark grey texture (#121212) |
| Secondary | White paper texture |
| Grain/noise | Yes |
| Lighting | Top-down vignette |
| Dominant elements | Grid tables, criteria circles |
| Layout logic | Centered paper layout |
| Typography style | Printed document aesthetic |
| Entry motion | Slide-in with physics |
| Internal animation | Typewriter or row reveal |
| Motion speed | Medium naturalistic |
| Easing | `cubic-bezier(0.25, 1, 0.5, 1)` |
| Paper slide duration | 20 frames |
| Transition in/out | Slide directional |

---

## PART C: GLOBAL MOTION PATTERNS

### Entry Styles (in order of frequency)
1. `scale_up_fade_in` - Default for most text
2. `stamp_impact` - For emphasis moments
3. `typewriter` - For explainer scenes

### Exit Styles
- `hard_cut` - Almost always (no fade out)

### Typical Easing
```css
cubic-bezier(0.34, 1.56, 0.64, 1)
```
This creates a slight overshoot (bounce) effect.

### Timing Averages
| Property | Value |
|----------|-------|
| Average text duration | 2.2 seconds |
| Entry duration | 6-15 frames |
| Hold duration | 54-90 frames |
| Exit duration | 6-10 frames |

---

## PART D: TRIGGER CONDITIONS

### When to use Intro Text Animation
| Transcript Pattern | Action |
|-------------------|--------|
| Sentence with emphasis word | Use `kinetic_text_phrase` |
| Opening hook statement | Use `text_highlight_caption` |
| Key promise/benefit | Use `text_highlight_caption` |

### When to use Background Takeover
| Transcript Pattern | Action |
|-------------------|--------|
| "Rule #1", "The first lesson" | Use `explainer_graphic_scene` |
| "Let me show you..." | Use `framework_scene` |
| "X vs Y", "Compare..." | Use `table_scene` |
| Process/steps explanation | Use `explainer_graphic_scene` |

---

## PART E: REMOTION COMPONENT MAPPING

Map this style profile to Remotion components:

| Style Profile Component | Remotion Component |
|------------------------|-------------------|
| `text_highlight_caption` | `<IntroTextAnimation />` |
| `kinetic_text_phrase` | `<KineticEmphasisText />` |
| `explainer_graphic_scene` | `<BackgroundTakeover />` |
| `table_scene` | `<ComparisonTable />` |
| `framework_scene` | `<FrameworkDiagram />` |

---

## Usage Example

When Agent Zero analyzes a transcript and finds:
> "There are three rules you need to know..."

It should output:
```json
{
  "type": "text_highlight_caption",
  "start_time": "00:04.200",
  "duration_sec": 2.2,
  "text": "THREE RULES",
  "style_profile": "iman_emphasis_phrase",
  "rotation_degrees": -3,
  "color_highlight": "#FFFF00"
}
```

This maps directly to Remotion props.
