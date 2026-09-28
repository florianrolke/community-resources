# Monospace Labels
> Tiny uppercase monospace category labels above headings for editorial structure

## Preview
- Live: visible on ALL luxury deployed sites (delta-vega-luxury, delta-vega-luxury-k8, populon-demo, driveby-demo)

## What It Does
Small, uppercase, wide-tracked monospace labels placed above section headings to create editorial hierarchy. Uses JetBrains Mono at 8-11px with 0.2-0.4em letter-spacing in the accent or gold color. These labels categorize sections ("ABOUT US", "WHAT WE DO", "SERVICES") and give the page a structured, editorial-publication feel. A staple of luxury/premium web design.

## Code
```html
<!-- Google Font (inject in <head>) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400&display=swap">

<!-- CSS (inject in <head>) -->
<style>
.mono-label {
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
  font-size: 0.625rem;         /* ~10px */
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.3em;
  color: rgba(212, 175, 55, 0.6);  /* gold at 60% — replace with accent */
  margin-bottom: 1rem;
  display: block;
}

/* Variant: with left accent line */
.mono-label-lined {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.35em;
  color: rgba(116, 86, 241, 0.7);  /* accent purple */
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.mono-label-lined::before {
  content: '';
  display: block;
  width: 24px;
  height: 1px;
  background: currentColor;
  opacity: 0.5;
}

/* Variant: numbered (01. ABOUT) */
.mono-label-numbered {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.25em;
  color: rgba(212, 175, 55, 0.5);
}
.mono-label-numbered .num {
  color: rgba(212, 175, 55, 0.8);
  margin-right: 0.5em;
}
</style>

<!-- Usage: Basic -->
<span class="mono-label">About Us</span>
<h2>Who We Are</h2>

<!-- Usage: With accent line -->
<span class="mono-label-lined">Services</span>
<h2>What We Do</h2>

<!-- Usage: Numbered -->
<span class="mono-label-numbered"><span class="num">01.</span> About</span>
<h2>Our Story</h2>
```

### Customization

- **Color:** Replace the `rgba(...)` color with client accent at 50-70% opacity
- **Size:** 8px for minimal, 10px for standard, 11px for slightly more prominent
- **Spacing:** 0.2em for tight, 0.3em for standard, 0.4em for wide spread
- **Font alternatives:** SF Mono, Fira Code, IBM Plex Mono, Source Code Pro

## Dependencies
- Google Fonts: JetBrains Mono (weight 400)
- No JS required

## When To Use
- **Industry fit:** Universal — works across all industries, essential for luxury/editorial aesthetics
- **Best for:** Section category labels above every `<h2>` heading throughout the page
- **Pairs well with:** gradient-text (gradient heading below mono label), scroll-reveal (fade in label then heading)

## Injection Point
Place a `<span class="mono-label">` immediately before each section's `<h2>` heading. The Google Font `<link>` and `<style>` block go in `<head>`.

**Source:** All deployed luxury sites, `.agent/skills/luxury-editorial-finance/SKILL.md` (Typography section)
