# Course Kinetic Text Style Spec

## Visual Language

This style is for course-like talking-head videos, not subtitle tracks.

Use selective emphasis moments across the transcript:

- One meaningful kinetic text event every 8-14 seconds.
- Place events on idea boundaries, not rigid clock intervals.
- Use short lines: 2 lines, usually 2-4 words per line.
- Do not show the whole transcript.

## Typography

- Font: `Inter`, `Montserrat`, or a similar bold sans-serif.
- Weight: `900`.
- Text color: `#FFFFFF`.
- Letter spacing: `-0.02em`.
- Placement: lower third.
- Shadow: subtle dark shadow for readability.

## Environmental Shade

Add a bottom shade behind text:

```css
linear-gradient(
  to top,
  rgba(0, 0, 0, 0.5) 0%,
  rgba(0, 0, 0, 0.34) 34%,
  rgba(0, 0, 0, 0) 64%
)
```

## Text Motion

Text enters with a lift-and-pop:

- `translateY(30px)` to `0px`
- Scale `0.8` to `1.0`, with slight overshoot
- Duration around 12 frames
- Spring: `stiffness: 180`, `damping: 12`, `mass: 1`

## Champagne Highlight

Highlight strips use the luxury palette:

```css
linear-gradient(
  92deg,
  rgba(214, 181, 109, 0.72),
  rgba(240, 214, 138, 0.9)
)
```

Strip behavior:

- Appears 2 frames after text.
- Rotated about `-1.7deg`.
- Slight radius: `4px`.
- Animated with `scaleX()`.

## Circle Emphasis

Use an SVG ellipse with stroke reveal:

- Stroke: `#F0D68A`.
- Stroke width: `8`.
- Animate `strokeDashoffset` from full length to `0`.
- Duration: about 15 frames.
- Easing: `bezier(0.33, 1, 0.68, 1)`.

## Face Zooms

When a word is circled, zoom the talking-head video, not the word.

Punch-in defaults:

- Zoom: `1.07` to `1.085`.
- Duration: 90-112 frames.
- Spring entrance.
- Short ease-out near the end.

Slow push-in defaults:

- Use only 1-3 times in a long-form video.
- Duration: about 5 seconds.
- Zoom: `1.04` to `1.06`.
- Use for sustained thesis moments.

## Flash Transitions

Use a 10-frame white/cool flash at section resets:

- Frame 0: `0%`
- Frame 4: `58-75%`
- Frame 10: `0%`

Pair with a whoosh SFX and optional snap zoom.

## SFX Timing

- Text hit: short pop/tap.
- Circled word + face punch: bell/ding.
- Flash or scene reset: whoosh.
- Slow push-in start: very subtle whoosh or airy riser.

Keep SFX restrained. They should support emphasis, not fight speech.
