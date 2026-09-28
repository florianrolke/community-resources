# Gold Gradient Line
> A full-width horizontal line that fades from transparent to accent color and back, creating an elegant section divider

## Preview
- Live: ALL luxury sites (https://delta-vega-luxury.preview.florianrolke.com, https://teamsiok-luxury.preview.florianrolke.com, etc.)

## What It Does
Creates a single-pixel horizontal line using a CSS gradient that fades from transparent at both edges to the accent color in the center. At 30% opacity, it acts as a refined section separator that is visible enough to define boundaries without creating harsh visual breaks. The simplest and most universally used divider across all deployed luxury redesigns.

## Code
```html
<!-- Standalone divider -->
<div class="divider-gradient"></div>

<!-- With extra vertical spacing -->
<div class="divider-gradient divider-gradient--spacious"></div>

<!-- Inside a container (constrained width) -->
<div style="max-width: 1200px; margin: 0 auto; padding: 0 2rem;">
  <div class="divider-gradient"></div>
</div>

<style>
.divider-gradient {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent, #C9A96E), transparent);
  opacity: 0.3;
  margin: 3rem 0;
}

/* Extra spacing variant */
.divider-gradient--spacious {
  margin: 5rem 0;
}

/* Tight spacing (inside cards/sections) */
.divider-gradient--tight {
  margin: 1.5rem 0;
}

/* No margin (when parent handles spacing) */
.divider-gradient--flush {
  margin: 0;
}

/* Brighter variant for more definition */
.divider-gradient--bright {
  opacity: 0.5;
}

/* White variant (for non-gold themes) */
.divider-gradient--white {
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
  opacity: 0.15;
}

/* Short variant (centered, 60% width) */
.divider-gradient--short {
  max-width: 60%;
  margin-left: auto;
  margin-right: auto;
}
</style>
```

## Dependencies
- CSS custom property `--accent` for the gradient color (falls back to gold #C9A96E)
- No JavaScript required
- Works on any background color

## When To Use
- **Industry fit**: Universal -- used on every single luxury redesign
- **Best for**: Separating any two sections, inside cards between content blocks, above/below testimonials
- **Pairs well with**: Every other component -- this is the default section divider

## Injection Point
Place between any two `<section>` elements as a sibling, or inside a section to separate content blocks. For full-width effect, place outside the container. For contained width, place inside the max-width container.
