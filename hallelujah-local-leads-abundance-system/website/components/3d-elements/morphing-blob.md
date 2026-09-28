# Morphing Blob
> Organic SVG shape that smoothly morphs between amorphous forms with a gooey blur effect

## Preview
- Live: concept component (from luxury-elements-v7 Effect 5)

## What It Does
Pure SVG animation using SMIL `<animate>` tags to morph between 3 organic blob keyframes over 12 seconds. A feGaussianBlur + feColorMatrix SVG filter creates the signature "goo" merging effect. Zero JavaScript, zero external dependencies -- works everywhere SVGs render.

## Code
```html
<!-- Morphing Blob - Pure SVG, Zero JS -->
<svg viewBox="0 0 500 500" width="400" height="400" style="display:block;margin:0 auto;"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="blob-goo">
      <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur"/>
      <feColorMatrix in="blur" mode="matrix"
        values="1 0 0 0 0
                0 1 0 0 0
                0 0 1 0 0
                0 0 0 20 -10" result="goo"/>
      <feBlend in="SourceGraphic" in2="goo"/>
    </filter>
    <linearGradient id="blob-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <!-- Replace stops with brand colors -->
      <stop offset="0%" stop-color="#b76e79"/>
      <stop offset="50%" stop-color="#d4a574"/>
      <stop offset="100%" stop-color="#b76e79"/>
    </linearGradient>
  </defs>

  <g filter="url(#blob-goo)">
    <path fill="url(#blob-grad)" opacity="0.7">
      <animate attributeName="d" dur="12s" repeatCount="indefinite"
        values="
          M250,100 C320,100 400,160 400,250 C400,340 320,400 250,400 C180,400 100,340 100,250 C100,160 180,100 250,100 Z;
          M250,120 C340,80 420,180 380,270 C340,360 280,420 200,380 C120,340 80,280 120,200 C160,120 200,100 250,120 Z;
          M260,90 C350,110 410,200 370,290 C330,380 260,410 190,370 C120,330 90,250 110,180 C130,110 200,80 260,90 Z;
          M250,100 C320,100 400,160 400,250 C400,340 320,400 250,400 C180,400 100,340 100,250 C100,160 180,100 250,100 Z
        "/>
    </path>

    <!-- Secondary smaller blob for goo interaction -->
    <circle cx="330" cy="170" r="35" fill="url(#blob-grad)" opacity="0.5">
      <animate attributeName="cx" dur="12s" repeatCount="indefinite"
        values="330;290;350;330"/>
      <animate attributeName="cy" dur="12s" repeatCount="indefinite"
        values="170;210;150;170"/>
      <animate attributeName="r" dur="12s" repeatCount="indefinite"
        values="35;45;30;35"/>
    </circle>
  </g>
</svg>

<!-- Full-width background variant -->
<!--
<div style="position:absolute;inset:0;z-index:0;display:flex;align-items:center;justify-content:center;pointer-events:none;opacity:0.3;">
  [paste the SVG above here]
</div>
-->
```

## Dependencies
- None (pure SVG with SMIL animation, zero JavaScript, zero libraries)

## When To Use
- **Industry fit**: Creative agencies, med spa, hospitality, wellness, beauty
- **Best for**: Hero decorative accent, about section background, behind testimonials
- **Pairs well with**: gradient-text, character-reveal, wave-svg, gold-gradient-line

## Injection Point
As a decorative element inside any section. For a background effect, wrap in an absolutely-positioned container at `z-index: 0` with low opacity (0.2-0.4). For a standalone accent, place beside or behind text content. Works at any size -- the SVG viewBox scales responsively.
