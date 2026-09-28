# Metallic Shimmer
> Animated metallic gradient text that shifts like polished metal catching light

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
Fills headline text with a multi-stop metallic gradient that continuously shifts position, creating the illusion of light moving across polished metal. Three preset palettes are provided: platinum (silver), gold, and rose gold. The gradient uses `background-size: 200% 200%` with a 6-second looping animation for smooth motion. Best on large display text against dark backgrounds.

## Code
```html
<!-- CSS (inject in <head>) -->
<style>
/* Platinum / Silver */
.metallic-platinum {
  background: linear-gradient(135deg, #667 0%, #dde 25%, #fff 50%, #ccd 75%, #889 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: metalShift 6s ease-in-out infinite;
}

/* Gold */
.metallic-gold {
  background: linear-gradient(135deg, #8B6914 0%, #DAA520 25%, #FFD700 50%, #FFEAA7 75%, #DAA520 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: metalShift 6s ease-in-out infinite;
}

/* Rose Gold */
.metallic-rose {
  background: linear-gradient(135deg, #8B6161 0%, #C9918A 25%, #E8B4B8 50%, #F5D5D8 75%, #C9918A 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: metalShift 6s ease-in-out infinite;
}

@keyframes metalShift {
  0%   { background-position: 0% 0%; }
  50%  { background-position: 100% 100%; }
  100% { background-position: 0% 0%; }
}
</style>

<!-- Usage -->
<h1 class="metallic-gold" style="font-family:'Cormorant Garamond',serif;font-weight:300;font-size:clamp(2.5rem,5vw,5.5rem);">
  QUANTITATIVE EDGE
</h1>
```

### Custom Metallic Palette

Build your own by choosing 5 gradient stops from dark to light to dark in the same hue family:

```css
.metallic-custom {
  background: linear-gradient(135deg,
    #2a1a3d 0%,    /* darkest */
    #7456f1 25%,   /* mid */
    #c084fc 50%,   /* lightest / highlight */
    #7456f1 75%,   /* mid */
    #2a1a3d 100%   /* darkest */
  );
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: metalShift 6s ease-in-out infinite;
}
```

## Dependencies
- No JS required
- CSS `background-clip: text` support (all modern browsers)
- Recommended font: Cormorant Garamond (Google Fonts) at weight 300 for maximum elegance

## When To Use
- **Industry fit:** Finance, law, luxury real estate, jewelry, high-end consulting — premium/institutional brands
- **Best for:** Hero headlines on dark backgrounds where the metallic effect reinforces luxury positioning
- **Pairs well with:** character-reveal (reveal then shimmer), parallax-depth-layers (metallic text floating over depth)

## Injection Point
Add the appropriate metallic class (`metallic-platinum`, `metallic-gold`, or `metallic-rose`) to any `<h1>` or large display heading. The `<style>` block goes in `<head>`.

**Source:** `.agent/skills/luxury-editorial-finance/SKILL.md` — Element 7 (Metallic Gradient Shimmer Text)
