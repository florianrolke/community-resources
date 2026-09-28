# Gemini Master Analysis Prompt

> Single comprehensive prompt for full video style extraction. Copy and paste into Gemini 1.5 Pro with a video URL or upload.

---

```
You are a senior video editor and motion graphics specialist analyzing YouTube content for replication in an automated pipeline.

## VIDEO TO ANALYZE
[PASTE VIDEO URL OR UPLOAD VIDEO]

Analyze this video using precise editorial terminology. Output machine-readable specifications that can be fed directly into FFmpeg (editing) and Remotion (graphics) pipelines.

---

## PART A: HEAVY LIFTING / EDITING ANALYSIS

### A1. PACING & RHYTHM
Measure and report:
- Average shot duration (seconds)
- Cuts per minute (CPM) for:
  - Intro (first 60 seconds)
  - Body (main content)
  - Outro (final 60 seconds)
- Pacing curve: Does it accelerate, decelerate, or stay constant?
- Speed change triggers: What causes pacing shifts?

### A2. SILENCE REMOVAL / JUMP CUTS
Analyze pause handling:
- Estimated silence threshold (in seconds) - how short can pauses be before they're cut?
- Padding around speech (in milliseconds)
- Cut style: Hard cuts or J-cuts (audio leads video)?
- Jump cut frequency: Every sentence? Every paragraph? Only on hesitations?
- Percentage of detected pauses that appear to be removed (estimate)

Important distinctions:
- Sentence boundaries = pacing edits (cut without zoom)
- Paragraph boundaries = structural edits (eligible for zoom change)

### A3. ZOOM ARCHITECTURE
Identify zoom patterns:

**The Creep (Ken Burns / slow push-in)**
- Used on segments longer than X seconds?
- Start scale and end scale (e.g., 1.0 → 1.08)
- Easing: Linear, ease-in, ease-out?
- Duration of zoom cycle

**The Punch (emphasis zoom)**
- Scale jump amount (e.g., 1.10x, 1.25x)
- Trigger: New paragraph? Topic shift? Emphasis word?
- Is it animated or instant (cut-based)?

**The Reset**
- When does scale return to 1.0?
- Trigger: Chapter marker? Rule definition? Major topic shift?

**Alternation Pattern**
- Do zooms alternate (1.0 → 1.08 → 1.0 → 1.08)?
- Or do they stack progressively?

### A4. AUDIO ENGINEERING
Analyze audio treatment:
- Estimated loudness (LUFS): -14, -16, or other?
- Background music presence: Yes/No
- Music ducking: Does music lower when speech occurs?
  - Estimated duck amount (dB)
  - Attack speed: Fast or slow?
  - Release speed: Fast or slow?
- Audio quality: Is there compression, EQ, or enhancement?

### A5. CUT MASKING
When jump cuts remove significant pauses (>300ms):
- Are they masked with zoom changes?
- Are there micro-dissolves (crossfades)?
- Or are they hard cuts?

---

## PART B: MOTION GRAPHICS (MOGRAPH) ANALYSIS

### B1. GRAPHICS INVENTORY
List every type of on-screen graphic element:
- [ ] Title card (opening)
- [ ] Lower thirds (name/title identification)
- [ ] Kinetic typography (animated emphasis words)
- [ ] Full-screen graphics (chapter cards, transitions)
- [ ] Quote callouts / text boxes
- [ ] Data visualizations (charts, statistics)
- [ ] Icons / pictograms
- [ ] B-roll inserts
- [ ] End card / CTA
- [ ] Progress bars / timers
- [ ] Logo animations
- [ ] Other: _______

### B2. OVERLAY DENSITY & TRIGGERS
Analyze when graphics appear:
- Maximum duration without a visual change (in seconds)
- Estimated overlays per minute
- What triggers an overlay?
  - [ ] Static segment exceeding X seconds
  - [ ] Key nouns mentioned
  - [ ] Numbers or statistics spoken
  - [ ] Rule definitions ("Rule #1", "The first lesson")
  - [ ] Named entities (people, companies, places)
  - [ ] Topic/chapter transitions

### B3. KINETIC TYPOGRAPHY SPECIFICS
For animated text overlays:
- Selection priority: What gets highlighted?
  1. Rule definitions / frameworks (highest)
  2. Numbers / statistics
  3. Key abstract nouns
  4. Named entities
- Duration on screen (seconds)
- Position: Center, lower third, custom?
- Animation style: Pop, slide, scale, typewriter?
- Font style: Serif, sans-serif, display?
- Case: ALL CAPS, Title Case, sentence case?

### B4. LOWER THIRD SPECIFICATIONS
- When does it first appear? (seconds from start)
- Duration on screen
- Components: Name only? Name + title? Name + title + accent bar?
- Animation: Slide in, fade, scale?
- Position: Standard lower third or custom?

### B5. TYPOGRAPHY SYSTEM
Document the text hierarchy:
| Element | Font Style | Weight | Size (relative) | Color |
|---------|------------|--------|-----------------|-------|
| Headlines | | | | |
| Subheads | | | | |
| Body text | | | | |
| Captions | | | | |

### B6. COLOR PALETTE
- Primary color (hex if identifiable):
- Secondary color:
- Accent/highlight color:
- Text on dark background:
- Text on light background:
- Background overlay treatment (solid, gradient, blur, opacity %):

### B7. ANIMATION LANGUAGE
For each element type, describe:
- Entry animation (how it appears)
- Hold duration
- Exit animation (how it leaves)
- Easing curve (linear, ease-in, ease-out, bounce, elastic)
- Timing in frames or seconds

### B8. SPATIAL RULES
- Safe zones (where graphics never appear):
- Common positions (grid system if detectable):
- Relationship to speaker (never covers face? specific offset?):
- Z-depth (do graphics appear behind or in front of B-roll?):

### B9. SOUND DESIGN FOR GRAPHICS
- Do graphics have sound effects?
- Whoosh on entry?
- Click/pop on text appearance?
- Musical stingers on chapter cards?

---

## PART C: PATTERN RECOGNITION RULES

Identify semantic triggers the system should detect:

| Pattern | Detection Signal | Recommended Action |
|---------|------------------|-------------------|
| Visual Reset | Speaker says "Number [X]" or "The [X] Lesson" | Reset zoom to 1.0, show chapter card |
| Zoom In | Speaker lowers volume/pitch (intimacy) | Apply punch zoom |
| B-Roll Trigger | Mention of specific entity (person, company, place) | Insert relevant B-roll |
| Overlay Trigger | Segment > 7.5s without visual change | Add kinetic text |
| Emphasis Word | Intensity words (always, never, crucial) | Consider zoom or text overlay |

---

## PART D: COMPARATIVE BENCHMARKING

Compare this video's style to known benchmarks:

| Metric | This Video | Iman Gadzhi | Liam Ottley | Sharran Srivatsaa |
|--------|------------|-------------|-------------|-------------------|
| Cuts per minute (body) | | ~15-18 | ~12-15 | ~10-14 |
| Silence threshold | | ~0.15s | ~0.25s | ~0.15s |
| Zoom frequency | | High | Medium | High |
| Overlay density | | Every 8-10s | Every 12-15s | Every 7-10s |
| Music presence | | Yes (subtle) | Yes | Yes (prominent) |

---

## OUTPUT FORMAT

Provide analysis as structured JSON:

{
  "meta": {
    "video_url": "",
    "channel": "",
    "video_duration": "",
    "analysis_date": "",
    "style_descriptors": ["", "", ""]
  },

  "pacing": {
    "avg_shot_duration_seconds": 0,
    "cuts_per_minute": {
      "intro": 0,
      "body": 0,
      "outro": 0
    },
    "pacing_curve": "accelerating | decelerating | constant | variable"
  },

  "silence_removal": {
    "estimated_threshold_seconds": 0,
    "padding_ms": 0,
    "cut_style": "hard_cut | j_cut",
    "jump_cut_frequency": "every_sentence | every_paragraph | hesitations_only"
  },

  "zoom": {
    "creep": {
      "enabled": true,
      "start_scale": 1.0,
      "end_scale": 1.08,
      "ease": "linear",
      "apply_when": "segment_duration > Xs"
    },
    "punch": {
      "scale": 1.10,
      "trigger": "new_paragraph | topic_shift | emphasis"
    },
    "reset": {
      "trigger": "chapter_marker | rule_definition"
    },
    "alternation_pattern": "binary | progressive | none"
  },

  "audio": {
    "target_lufs": -16,
    "music_present": true,
    "music_duck_db": -15,
    "duck_attack_ms": 10,
    "duck_release_ms": 800
  },

  "overlays": {
    "density_max_seconds": 7.5,
    "overlays_per_minute": 0,
    "kinetic_text_triggers": [],
    "lower_third": {
      "start_seconds": 0,
      "duration_seconds": 0
    }
  },

  "graphics_package": {
    "typography": {
      "primary_font_style": "",
      "headline_weight": "",
      "case_style": ""
    },
    "colors": {
      "primary": "",
      "accent": "",
      "background_overlay": ""
    },
    "animation": {
      "entry_style": "",
      "exit_style": "",
      "easing": ""
    }
  },

  "pattern_rules": {
    "visual_reset_trigger": "",
    "zoom_in_trigger": "",
    "b_roll_trigger": "",
    "overlay_trigger": ""
  },

  "ffmpeg_recommendations": {
    "silence_min_duration": 0,
    "silence_padding_ms": 0,
    "progressive_zoom_end": 1.08,
    "loudnorm_target_lufs": -16
  }
}

---

## IMPORTANT ANALYSIS GUIDELINES

1. **Be specific with numbers** - Don't say "fast pacing", say "22 cuts per minute"
2. **Use editor-native vocabulary** - Jump cut, punch-in, Ken Burns, lower third, kinetic typography
3. **Distinguish mechanics from intent**:
   - Sentence boundaries = pacing edits
   - Paragraph boundaries = structural edits
4. **Note what's NOT present** - Absence of B-roll is as important as presence
5. **Flag automation challenges** - Which techniques require human judgment vs. can be automated?
```
