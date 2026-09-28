# Marquee Ticker
> Infinitely scrolling horizontal text ribbon with diamond separators, serif font, and low-opacity luxury aesthetic

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
A continuously scrolling horizontal text strip inspired by luxury fashion houses (Balenciaga, Gucci, Dior) and stock tickers. Content is duplicated to create a seamless loop via CSS translateX(0 to -50%). Thin accent-color borders frame the top and bottom. Text uses a serif font at 300 weight with wide letter-spacing and low opacity for subtle prestige signaling. Pauses on hover. Zero JavaScript required -- pure CSS animation.

## Code
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&display=swap" rel="stylesheet">

<style>
.marquee-ribbon {
  overflow: hidden;
  background: #102136;
  border-top: 1px solid rgba(116, 86, 241, 0.3);
  border-bottom: 1px solid rgba(116, 86, 241, 0.3);
  padding: 18px 0;
  white-space: nowrap;
}
.marquee-track {
  display: inline-flex;
  gap: 3rem;
  animation: marquee-scroll 30s linear infinite;
  font-family: 'Cormorant Garamond', serif;
  font-size: 1.1rem;
  font-weight: 300;
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: rgba(231, 235, 238, 0.6);
}
.marquee-track .separator {
  color: #7456f1;
  font-size: 0.7rem;
}
.marquee-ribbon:hover .marquee-track {
  animation-play-state: paused;
}
@keyframes marquee-scroll {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

/* Large text variant (luxury-elements-v7 style) */
.marquee-track.large {
  font-size: 4.5rem;
  font-weight: 200;
  letter-spacing: -0.01em;
  color: rgba(255, 255, 255, 0.15);
  gap: 4rem;
}
.marquee-track.large .separator {
  font-size: 0.75rem;
  align-self: center;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .marquee-track { animation: none; }
}
</style>

<!-- Standard size marquee -->
<div class="marquee-ribbon">
  <div class="marquee-track">
    <!-- First copy -->
    <span>Service One</span>
    <span class="separator">&#x2726;</span>
    <span>Service Two</span>
    <span class="separator">&#x2726;</span>
    <span>Service Three</span>
    <span class="separator">&#x2726;</span>
    <span>Service Four</span>
    <span class="separator">&#x2726;</span>
    <!-- Exact duplicate for seamless loop -->
    <span>Service One</span>
    <span class="separator">&#x2726;</span>
    <span>Service Two</span>
    <span class="separator">&#x2726;</span>
    <span>Service Three</span>
    <span class="separator">&#x2726;</span>
    <span>Service Four</span>
    <span class="separator">&#x2726;</span>
  </div>
</div>

<!-- Large text variant -->
<div class="marquee-ribbon" style="padding:24px 0;">
  <div class="marquee-track large">
    <span>LIBOR</span>
    <span class="separator">&#9670;</span>
    <span>Derivatives</span>
    <span class="separator">&#9670;</span>
    <span>Risk Analytics</span>
    <span class="separator">&#9670;</span>
    <span>Quantitative Models</span>
    <span class="separator">&#9670;</span>
    <!-- Duplicate -->
    <span>LIBOR</span>
    <span class="separator">&#9670;</span>
    <span>Derivatives</span>
    <span class="separator">&#9670;</span>
    <span>Risk Analytics</span>
    <span class="separator">&#9670;</span>
    <span>Quantitative Models</span>
    <span class="separator">&#9670;</span>
  </div>
</div>
```

### Speed & Direction Variants
```css
/* Faster (15s) for short text */
.marquee-track { animation-duration: 15s; }

/* Slower (45s) for long text */
.marquee-track { animation-duration: 45s; }

/* Reverse direction (for second band creating depth) */
.marquee-track.reverse { animation-direction: reverse; }
```

## Dependencies
- Google Fonts: Cormorant Garamond (300, 400)
- Pure CSS animation (zero JS)

## When To Use
- **Industry fit:** Finance, luxury, fashion, architecture, high-end consulting
- **Best for:** Credibility phrases, service keywords, certifications, client logos as text
- **Pairs well with:** gold-gradient-line dividers (above/below the marquee), counter-stats (place marquee between hero and stats bar)

## Injection Point
Place directly below the hero section, above the main content. The ribbon acts as a visual divider between the hero and body. Content must be duplicated exactly -- the first half and second half must be identical for the seamless loop to work (translateX(-50%) brings the duplicate into view as the first copy scrolls out).
