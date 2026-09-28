# Outlined Stroke
> Transparent text with a thin accent-colored outline stroke for large display typography

## Preview
- Live: https://delta-vega-luxury.preview.florianrolke.com

## What It Does
Creates hollow/outlined text using CSS `-webkit-text-stroke` with a transparent fill. The stroke is thin (1px) and uses the accent color at low opacity, producing an elegant architectural effect. Works exclusively on large display text — hero titles, section dividers, decorative headings. Not suitable for body text or small sizes where the stroke would be illegible.

## Code
```html
<!-- CSS (inject in <head>) -->
<style>
.stroke-text {
  -webkit-text-stroke: 1px rgba(212, 175, 55, 0.1);
  -webkit-text-fill-color: transparent;
  font-size: clamp(3rem, 8vw, 8rem);
  font-weight: 300;
  letter-spacing: 0.05em;
  line-height: 1.1;
}

/* Hover variant: fill appears on interaction */
.stroke-text-hover {
  -webkit-text-stroke: 1px rgba(212, 175, 55, 0.15);
  -webkit-text-fill-color: transparent;
  transition: -webkit-text-fill-color 0.6s ease, -webkit-text-stroke 0.6s ease;
}
.stroke-text-hover:hover {
  -webkit-text-fill-color: rgba(212, 175, 55, 0.8);
  -webkit-text-stroke: 1px rgba(212, 175, 55, 0.3);
}

/* Decorative section divider variant */
.stroke-divider {
  -webkit-text-stroke: 1px rgba(255, 255, 255, 0.06);
  -webkit-text-fill-color: transparent;
  font-size: clamp(4rem, 12vw, 12rem);
  font-weight: 200;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.4;
  user-select: none;
  pointer-events: none;
}
</style>

<!-- Usage: Hero title -->
<h1 class="stroke-text" style="font-family:'Cormorant Garamond',serif;">
  DELTA VEGA
</h1>

<!-- Usage: Decorative background text -->
<div class="stroke-divider" style="font-family:'Cormorant Garamond',serif;text-align:center;overflow:hidden;">
  SERVICES
</div>
```

### Customization

Replace `rgba(212, 175, 55, ...)` with the client's accent color. Adjust opacity:
- `0.06-0.10` for subtle ghost text (decorative dividers)
- `0.12-0.20` for readable outlined headings
- `0.25-0.40` for bolder stroke presence

## Dependencies
- No JS required
- `-webkit-text-stroke` support (Chrome, Safari, Edge, Firefox 49+)
- Works best with serif fonts at light weights (200-400)

## When To Use
- **Industry fit:** Finance, architecture, luxury brands, editorial — industries valuing understated elegance
- **Best for:** Large display headings (3rem+) and decorative section dividers on dark backgrounds
- **Pairs well with:** gradient-text (use one OR the other on the same element, not both)

## Injection Point
Add class directly to `<h1>`, `<h2>`, or decorative `<div>` elements. CSS goes in `<head>`. Only use on text sized 3rem or larger.

**Source:** Deployed delta-vega-luxury sites, `.agent/skills/luxury-editorial-finance/`
