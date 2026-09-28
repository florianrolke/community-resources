# Design System

## Visual Language

Base palette:

- Forest: `#09240f`
- Deep forest: `#06180b`
- Cream: `#f6f2ec`
- Gold: `#c9a96e`
- Bright gold: `#f6d27f`
- Red accent: `#990000`
- Copper: `#b87333`

The look should feel like premium advisory, financial engineering, and editorial documentary graphics. Use green/gold as the main identity, with red only for contrast, warnings, or mistake sections.

## Overlay Types

Use these categories:

- `number_counter`: opener, statistics, numbered mistake/rule reveal.
- `gp_preloader_card`: elegant intro animation before revealing card content.
- `bullet_reveal`: checklist or sequential point reveal.
- `fade_up_key`: short key insight with text moving up and fading in.
- `full_screen_statement`: major point, rule, or quote over a cream angled cut.
- `recap`: summary near the end.

Remove or skip the three-icon hover-card block unless the user explicitly asks for it. In long-form video, the same feel works better as sequential text reveals than as a static three-card row.

## Timing

Use roughly one overlay every 8-12 seconds. Break this rule when the transcript needs breathing room.

Suggested defaults:

- Opener/count: 3-5 seconds
- Split card: 4-6 seconds
- Bullet reveal: 5-7 seconds
- Full-screen statement: 4-6 seconds
- Recap: 5-8 seconds

Use faster animation timing for the first two overlays so the video starts with energy.

## SFX and Motion Pairing

Every motion event should have a sound counterpart:

- Card in: whoosh
- Card out or return to talking head: soft whoosh
- Bullet appears: paper crumple, paper fold, or click
- Key phrase emphasis: notification-style bing with subtle vibration texture
- Number counter: soft tick, riser, or chime
- Full-screen statement: low hit plus riser

Default SFX cue volume: `0.28-0.36`. Adjust by ear against voiceover.

## Zooms and Jump Cuts

Use zooms for emphasis words, hand gestures, or emotionally important sentence starts. Hold the zoom until the next overlay boundary; do not immediately zoom back out unless the user asks for a pulse effect.

If programmatic hand-gesture detection is needed later, use a separate computer-vision pass such as MediaPipe or frame-difference/optical-flow analysis. Default to transcript and audio emphasis cues unless the project already has gesture metadata.
