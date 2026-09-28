# Scanlines Overlay
> Horizontal repeating lines at micro-opacity creating a subtle CRT monitor texture over backgrounds

## Preview
- Live: Used in animate_static_page.py video-hero overlay across deployed sites

## What It Does
Creates a repeating pattern of horizontal lines using a CSS gradient -- alternating between transparent and near-black at 2px intervals. When placed over video backgrounds, hero images, or dark sections, it creates a subtle CRT/retro monitor effect that adds analog depth. At 0.03 opacity the lines are felt rather than seen, adding texture without interfering with readability.

## Code
```html
<!-- As an overlay on a hero/video section -->
<section class="hero-with-scanlines">
  <video autoplay loop muted playsinline class="hero-video">
    <source src="hero.mp4" type="video/mp4">
  </video>
  <div class="scanlines-overlay" aria-hidden="true"></div>
  <div class="hero-content">
    <h1>Your Headline</h1>
  </div>
</section>

<style>
.hero-with-scanlines {
  position: relative;
  overflow: hidden;
  min-height: 100vh;
}

.hero-video {
  position: absolute;
  top: 50%;
  left: 50%;
  min-width: 100%;
  min-height: 100%;
  transform: translate(-50%, -50%);
  object-fit: cover;
}

.scanlines-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 2;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
}

.hero-content {
  position: relative;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
}

.hero-content h1 {
  font-family: var(--font-heading, 'Cormorant Garamond', serif);
  font-size: clamp(2.5rem, 6vw, 5rem);
  color: #ffffff;
  text-align: center;
}

/* Full-page scanlines variant (like film-grain but lines) */
.scanlines-fullpage {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 9998;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
}

/* Heavier variant (more visible, for retro themes) */
.scanlines-overlay--heavy {
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.06) 2px,
    rgba(0, 0, 0, 0.06) 4px
  );
}

/* Wider lines variant */
.scanlines-overlay--wide {
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(0, 0, 0, 0.025) 3px,
    rgba(0, 0, 0, 0.025) 6px
  );
}
</style>
```

## Dependencies
- No JavaScript required
- No external images -- pure CSS gradient
- Works on any background (most effective on images and video)

## When To Use
- **Industry fit**: Tech, gaming, media production, music, nightlife -- brands with a digital/retro edge
- **Best for**: Video hero backgrounds, full-bleed image sections, dark UI panels
- **Pairs well with**: film-grain (stack both for cinematic CRT feel -- scanlines at z-index 9998, grain at 9999), video-hero animations, environmental-bleed

## Injection Point
Add the `.scanlines-overlay` div as a sibling inside any section with a background image or video. Set the parent to `position: relative` and ensure the overlay has a z-index between the background and the content. For full-page effect, add `.scanlines-fullpage` as the last child of `<body>`.
