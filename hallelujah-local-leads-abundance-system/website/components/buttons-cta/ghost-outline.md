# Ghost Outline Button
> Transparent button with a subtle white border that fills with a soft tint on hover

## Preview
- Live: https://delta-vega-luxury.preview.florianrolke.com

## What It Does
A secondary CTA style with a transparent background and thin white border. On hover, a soft white tint fills the background and the border brightens. Designed to sit alongside the pill-glow button as the lower-priority action (e.g., "Learn More" next to "Get Started"). The understated style prevents it from competing with the primary CTA while still being clearly clickable.

## Code
```html
<!-- Secondary CTA -->
<a href="#services" class="btn-ghost">
  Learn More
</a>

<!-- Paired with primary (common pattern) -->
<div class="cta-pair">
  <a href="#contact" class="btn-pill-glow">Get Started</a>
  <a href="#services" class="btn-ghost">Learn More</a>
</div>

<!-- Accent-colored border variant -->
<a href="#portfolio" class="btn-ghost btn-ghost--accent">
  View Portfolio
</a>

<style>
.btn-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  padding: 14px 48px;
  background: transparent;
  color: #ffffff;
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.85rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-decoration: none;
  border: 1px solid rgba(255, 255, 255, 0.3);
  cursor: pointer;
  transition: background 0.3s ease,
              border-color 0.3s ease,
              color 0.3s ease;
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.5);
}

.btn-ghost:active {
  background: rgba(255, 255, 255, 0.12);
}

/* Accent-colored border variant */
.btn-ghost--accent {
  border-color: rgba(var(--accent-rgb, 201, 169, 110), 0.4);
  color: var(--accent, #C9A96E);
}

.btn-ghost--accent:hover {
  background: rgba(var(--accent-rgb, 201, 169, 110), 0.08);
  border-color: rgba(var(--accent-rgb, 201, 169, 110), 0.6);
}

/* Dark mode (for light backgrounds) */
.btn-ghost--dark {
  color: var(--color-dark, #0a0a0a);
  border-color: rgba(0, 0, 0, 0.2);
}

.btn-ghost--dark:hover {
  background: rgba(0, 0, 0, 0.05);
  border-color: rgba(0, 0, 0, 0.4);
}

/* CTA pair layout */
.cta-pair {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

/* Small variant */
.btn-ghost--sm {
  padding: 10px 32px;
  font-size: 0.75rem;
}
</style>
```

## Dependencies
- CSS custom properties: `--accent-rgb` for accent variant, `--font-body` for typography
- Works on dark backgrounds by default; use `--dark` modifier for light backgrounds
- Pair with `pill-glow` button for primary/secondary CTA combo

## When To Use
- **Industry fit**: Universal -- secondary CTA for every redesign
- **Best for**: "Learn More", "View Portfolio", "Our Process" -- any secondary action alongside a primary CTA
- **Pairs well with**: pill-glow (always the primary/secondary pair), arrow-expand (as tertiary option)

## Injection Point
Place next to a pill-glow button using the `.cta-pair` wrapper. Common locations: hero section (dual CTA), end of feature sections, pricing cards (secondary plan action). Never use as the sole CTA -- always pair with a more prominent button or use arrow-expand for standalone secondary links.
