# Video-Filled Text
> Giant headline letters filled with looping video or animated gradient — text becomes a viewport into motion

## Preview
- Concept only (not deployed yet)

## What It Does
Uses an SVG `clipPath` containing a text element to mask a video (or gradient) so it only shows through the letter shapes. The headline text becomes a window into the moving footage beneath. A CSS-only fallback provides gradient-filled text with a shimmer animation for cases where video is too heavy or unsupported. Best at very large sizes (font-size 180+ in SVG units) with heavy-weight display fonts.

## Code
```html
<!-- Google Font (inject in <head>) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@900&display=swap">

<!-- Video-filled text hero -->
<div style="position:relative;height:100vh;display:flex;align-items:center;justify-content:center;background:#0b0f1a;overflow:hidden;">

  <!-- SVG text mask with video fill -->
  <svg viewBox="0 0 1200 300" style="width:100%;max-width:72rem;padding:0 1rem;">
    <defs>
      <clipPath id="textClip">
        <text x="50%" y="55%" text-anchor="middle" dominant-baseline="middle"
              font-family="'Playfair Display', serif" font-weight="900" font-size="180">
          HEADLINE
        </text>
      </clipPath>
    </defs>
    <!-- Video texture applied via foreignObject inside clip -->
    <foreignObject width="100%" height="100%" clip-path="url(#textClip)">
      <div xmlns="http://www.w3.org/1999/xhtml" style="width:100%;height:100%;">
        <video autoplay muted loop playsinline
               style="width:100%;height:100%;object-fit:cover;">
          <source src="https://videos.pexels.com/video-files/7579971/7579971-uhd_2560_1440_25fps.mp4" type="video/mp4">
        </video>
      </div>
    </foreignObject>
  </svg>

  <!-- Subtitle below -->
  <p style="position:absolute;bottom:30%;color:rgba(255,255,255,0.4);font-size:0.875rem;text-transform:uppercase;letter-spacing:0.5em;font-weight:300;">
    Tagline or descriptor text
  </p>
</div>
```

### CSS-Only Fallback (gradient shimmer)

For lighter pages or when video is impractical:

```html
<style>
.video-text-fallback {
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: clamp(4rem, 12vw, 12rem);
  line-height: 1;
  background: linear-gradient(135deg, #7456f1, #c084fc, #7456f1);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 4s ease-in-out infinite;
}
@keyframes shimmer {
  0%, 100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}
</style>

<h1 class="video-text-fallback">HEADLINE</h1>
```

### Tips

- **Font choice matters:** Use weight 900 (Black) for maximum letter area. Thin fonts don't show enough video.
- **SVG viewBox:** Adjust `viewBox="0 0 1200 300"` and `font-size="180"` to fit the word length. Longer words need a wider viewBox or smaller font-size.
- **Multi-line:** Use multiple `<text>` elements at different `y` positions within the same `<clipPath>`.
- **Video selection:** Choose footage with visible motion and contrast — abstract data streams, flowing water, or city lights work best.

## Dependencies
- Google Fonts: Playfair Display (weight 900) or any heavy display font
- SVG `clipPath` + `foreignObject` support (all modern browsers)
- Optional: ~2MB video file (Pexels free stock)
- No JS required

## When To Use
- **Industry fit:** Tech, creative agencies, luxury brands, entertainment — bold, statement-making brands
- **Best for:** Landing pages and hero sections where the headline IS the visual centerpiece
- **Pairs well with:** preloader-curtain (dramatic entrance reveal), monospace-labels (subtle label above the giant text)

## Injection Point
Replace the hero section content entirely. The SVG block is self-contained. The Google Font `<link>` goes in `<head>`. Use the CSS-only fallback if adding a `<noscript>` alternative or for mobile.

**Source:** `.agent/skills/luxury-elements-v7/Luxury_skill_7.md` — Effect 1 (Video-Filled Text)
