# Image Hero Ken Burns
> Slow cinematic zoom-and-pan animation on the client's actual hero image with triple overlay

## Preview
- Live: https://dunkertons-demo.client.of.florianrolke.com

## What It Does
Applies a continuous Ken Burns zoom-and-pan CSS animation to the client's own hero image (not stock footage). The image slowly scales between 1x and 1.18x while panning subtly in different directions over a 25-second cycle. Uses the same triple-overlay system as video-hero but with slightly lighter opacity (0.45 base wash instead of 0.55). Brand tinting via SVG feColorMatrix is optional.

## Code
```html
<!-- Optional: SVG brand tint filter (inject at top of <body>) -->
<svg style="position:absolute;width:0;height:0;overflow:hidden;" aria-hidden="true">
  <defs>
    <filter id="brandTint" color-interpolation-filters="sRGB">
      <feColorMatrix type="saturate" values="0"/>
      <feColorMatrix type="matrix" values="0.04 0 0 0 0.96 0.14 0 0 0 0.86 0.06 0 0 0 0.94 0 0 0 1 0"/>
    </filter>
  </defs>
</svg>

<!-- Ken Burns CSS (inject in <head>) -->
<style>
@keyframes animKenBurns {
  0%   { transform: scale(1) translate(0, 0); }
  25%  { transform: scale(1.12) translate(-1.5%, -1%); }
  50%  { transform: scale(1.18) translate(-2.5%, 0.5%); }
  75%  { transform: scale(1.1) translate(0.5%, -1.5%); }
  100% { transform: scale(1.06) translate(1%, -0.5%); }
}
.anim-image-hero img { transition: opacity 0.5s; }
</style>

<!-- Image background (first child of hero section) -->
<div class="anim-image-hero" style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <img src="CLIENT_HERO_IMAGE_URL" alt=""
       style="width:100%;height:100%;object-fit:cover;filter:url(#brandTint);animation:animKenBurns 25s ease-in-out infinite alternate;will-change:transform;">
  <!-- Overlay 1: flat dark wash (lighter than video-hero) -->
  <div style="position:absolute;inset:0;background:rgba(0,0,0,0.45);"></div>
  <!-- Overlay 2: radial vignette -->
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.65) 100%);"></div>
  <!-- Overlay 3: scanline texture -->
  <div style="position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.02) 2px, rgba(0,0,0,0.02) 4px);"></div>
</div>

<!-- Hero content (must be position:relative; z-index:1) -->
<div style="position:relative; z-index:1;">
  <h1>Your Headline Here</h1>
</div>
```

## Dependencies
- No JS libraries required
- CSS `@keyframes` block in `<head>` or `<style>` tag
- Hero section needs `position: relative; overflow: hidden; min-height: 70vh`
- Client's actual hero image URL (scraped via Firecrawl or provided)

## When To Use
- **Industry fit:** Food & beverage, hospitality, real estate, agriculture, lifestyle brands — anything with strong existing photography
- **Best for:** Sites where the client's own imagery tells the story better than stock video
- **Pairs well with:** scroll-reveal, monospace-labels

## Injection Point
First child of the hero section. The `<style>` block with `@keyframes animKenBurns` goes in `<head>`. Hero container needs `position: relative; overflow: hidden; min-height: 70vh`.

**Source:** `execution/animate_static_page.py` — `inject_image_hero()`
