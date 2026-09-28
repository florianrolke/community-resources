# Gradient Text
> Headline text filled with a shifting linear gradient between white/text color and the brand accent

## Preview
- Live: https://delta-vega-luxury.preview.florianrolke.com

## What It Does
Applies a CSS gradient fill to headline text using the `background-clip: text` technique. The gradient shifts between the page text color and the brand accent color at 135 degrees. An optional animation smoothly cycles the gradient position over 6 seconds, adding subtle motion to otherwise static text. Works on any heading but looks best on hero `<h1>` elements.

## Code
```html
<!-- CSS (inject in <head>) -->
<style>
.dp-gradient-text {
  background: linear-gradient(135deg, #fff 0%, #7456f1 50%, #fff 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: dp-gradient-shift 6s ease infinite;
}
@keyframes dp-gradient-shift {
  0%   { background-position: 0% center; }
  50%  { background-position: 100% center; }
  100% { background-position: 0% center; }
}
</style>

<!-- Usage -->
<h1 class="dp-gradient-text">Your Headline Here</h1>
```

### Static Variant (no animation)

```css
.dp-gradient-text-static {
  background: linear-gradient(135deg, #fff 0%, #7456f1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

### Customization

Replace `#fff` with the page's primary text color and `#7456f1` with the client's accent color. For light-background sites, use the primary dark text color instead of white:

```css
background: linear-gradient(135deg, #1a1a1a 0%, #0066cc 100%);
```

## Dependencies
- No JS required
- CSS `background-clip: text` support (all modern browsers)
- `-webkit-` prefix needed for Safari/Chrome

## When To Use
- **Industry fit:** Universal — works across all industries
- **Best for:** Hero headlines, section titles, CTAs where text needs visual punch without imagery
- **Pairs well with:** character-reveal (animate in, then show gradient), monospace-labels (category label above gradient heading)

## Injection Point
Add the `dp-gradient-text` class to any `<h1>`, `<h2>`, or display-sized text element. The `<style>` block goes in `<head>`. The `design_polish.py` script auto-applies this to the first `<h1>` in the first `<section>`.

**Source:** `execution/design_polish.py` — `_build_gradient_text_css()` (lines 200-218)
