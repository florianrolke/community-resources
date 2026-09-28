# Arrow Expand Link
> Text link with an arrow that slides outward on hover, expanding the gap for a smooth directional cue

## Preview
- Live: https://delta-vega-luxury.preview.florianrolke.com

## What It Does
A minimal text-link style CTA where an arrow icon sits to the right of the text. On hover, the gap between text and arrow expands and the arrow slides further right, creating a subtle directional animation that implies forward motion. Used as a tertiary action below primary and secondary buttons, or as inline links within cards and content blocks.

## Code
```html
<!-- Basic usage -->
<a href="#services" class="link-arrow">
  <span class="link-arrow-text">Learn more</span>
  <span class="link-arrow-icon">&rarr;</span>
</a>

<!-- In a card context -->
<div class="card-footer">
  <a href="#case-study" class="link-arrow">
    <span class="link-arrow-text">View case study</span>
    <span class="link-arrow-icon">&rarr;</span>
  </a>
</div>

<!-- Accent colored variant -->
<a href="#portfolio" class="link-arrow link-arrow--accent">
  <span class="link-arrow-text">Explore portfolio</span>
  <span class="link-arrow-icon">&rarr;</span>
</a>

<!-- Uppercase variant -->
<a href="#about" class="link-arrow link-arrow--uppercase">
  <span class="link-arrow-text">About us</span>
  <span class="link-arrow-icon">&rarr;</span>
</a>

<style>
.link-arrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.9rem;
  font-weight: 500;
  color: #ffffff;
  text-decoration: none;
  transition: gap 0.3s ease, color 0.3s ease;
}

.link-arrow:hover {
  gap: 14px;
}

.link-arrow-text {
  transition: opacity 0.3s ease;
}

.link-arrow-icon {
  display: inline-block;
  transition: transform 0.3s ease;
  font-size: 1.05em;
}

.link-arrow:hover .link-arrow-icon {
  transform: translateX(4px);
}

/* Accent color variant */
.link-arrow--accent {
  color: var(--accent, #C9A96E);
}

.link-arrow--accent:hover {
  color: var(--accent, #C9A96E);
  opacity: 0.8;
}

/* Uppercase variant */
.link-arrow--uppercase {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

/* On dark cards with lighter text */
.link-arrow--muted {
  color: rgba(255, 255, 255, 0.5);
}

.link-arrow--muted:hover {
  color: rgba(255, 255, 255, 0.8);
}
</style>
```

## Dependencies
- CSS custom property `--accent` for accent-colored variant
- No JavaScript required -- pure CSS transitions
- Uses HTML entity `&rarr;` for the arrow (no icon library needed)

## When To Use
- **Industry fit**: Universal -- works with every brand and style
- **Best for**: Card footers ("View project"), section teasers ("Learn more"), inline navigation links, breadcrumb-style secondary actions
- **Pairs well with**: hover-lift cards (place inside card body), numbered-feature (add as action link per item), ghost-outline (use arrow-expand below a ghost button group)

## Injection Point
Place inside card bodies, at the end of content sections, or as inline links within text blocks. This is a tertiary action -- use below pill-glow (primary) and ghost-outline (secondary) in the CTA hierarchy. Multiple arrow-expand links can appear on the same page without feeling repetitive.
