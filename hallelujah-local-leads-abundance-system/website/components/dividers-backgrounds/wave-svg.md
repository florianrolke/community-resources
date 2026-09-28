# Wave SVG Divider
> An inline SVG wave shape in accent color at low opacity, placed between sections for organic visual flow

## Preview
- Live: Used in design_polish.py output across multiple sites

## What It Does
Inserts an inline SVG with a smooth sine-wave path between sections. The wave uses the accent color at very low opacity (0.06) so it acts as a subtle textural break rather than a hard line. The SVG scales to full width using `preserveAspectRatio="none"`, ensuring it stretches across any viewport width without distortion of the wave pattern.

## Code
```html
<!-- Standard wave divider -->
<div class="wave-divider">
  <svg viewBox="0 0 1440 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,30 C240,55 480,5 720,30 C960,55 1200,5 1440,30 L1440,60 L0,60 Z"
          fill="var(--accent, #C9A96E)" fill-opacity="0.06"/>
  </svg>
</div>

<!-- Inverted wave (flipped vertically for bottom of section) -->
<div class="wave-divider wave-divider--flip">
  <svg viewBox="0 0 1440 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,30 C240,55 480,5 720,30 C960,55 1200,5 1440,30 L1440,60 L0,60 Z"
          fill="var(--accent, #C9A96E)" fill-opacity="0.06"/>
  </svg>
</div>

<!-- Double wave (more complex shape) -->
<div class="wave-divider">
  <svg viewBox="0 0 1440 80" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,40 C180,65 360,15 540,40 C720,65 900,15 1080,40 C1260,65 1440,15 1440,40 L1440,80 L0,80 Z"
          fill="var(--accent, #C9A96E)" fill-opacity="0.04"/>
    <path d="M0,50 C240,70 480,25 720,50 C960,75 1200,25 1440,50 L1440,80 L0,80 Z"
          fill="var(--accent, #C9A96E)" fill-opacity="0.03"/>
  </svg>
</div>

<!-- White variant (for non-gold themes) -->
<div class="wave-divider">
  <svg viewBox="0 0 1440 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,30 C240,55 480,5 720,30 C960,55 1200,5 1440,30 L1440,60 L0,60 Z"
          fill="#ffffff" fill-opacity="0.04"/>
  </svg>
</div>

<style>
.wave-divider {
  width: 100%;
  overflow: hidden;
  line-height: 0;
  margin: -1px 0; /* Prevent subpixel gaps */
}

.wave-divider svg {
  display: block;
  width: 100%;
  height: 60px;
}

/* Flipped variant */
.wave-divider--flip {
  transform: scaleY(-1);
}

/* Taller wave */
.wave-divider--tall svg {
  height: 90px;
}

/* Shorter wave */
.wave-divider--short svg {
  height: 35px;
}
</style>
```

## Dependencies
- CSS custom property `--accent` for wave fill color (falls back to gold)
- No JavaScript required
- Inline SVG (no external file needed)

## When To Use
- **Industry fit**: Organic brands, wellness, food & beverage, creative -- any brand that benefits from softness
- **Best for**: Transitioning between sections of different background colors, adding organic movement to otherwise geometric layouts
- **Pairs well with**: gold-gradient-line (use wave for organic sections, gradient line for structured sections), environmental-bleed (layered ambient effects)

## Injection Point
Place between two `<section>` elements. For a section with a darker background transitioning to lighter, place the wave at the top of the darker section. Use `--flip` when placing at the bottom. The `margin: -1px` prevents any hairline gaps between the wave and adjacent sections.
