# Pill Glow Button
> Rounded pill-shaped CTA with a luminous accent-colored shadow that intensifies on hover

## Preview
- Live: https://teamsiok-luxury.preview.florianrolke.com

## What It Does
Creates a fully rounded (pill-shaped) call-to-action button with a colored glow beneath it. The glow is achieved via box-shadow using the accent color at reduced opacity. On hover, the button lifts slightly and the glow expands, creating a sense of energy and urgency without being aggressive. This is the primary CTA style across all luxury redesigns.

## Code
```html
<!-- Primary CTA -->
<a href="#contact" class="btn-pill-glow">
  Get Started Today
</a>

<!-- With icon variant -->
<a href="#contact" class="btn-pill-glow">
  Schedule a Call
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left: 8px;">
    <path d="M5 12h14M12 5l7 7-7 7"/>
  </svg>
</a>

<style>
.btn-pill-glow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  padding: 14px 48px;
  background: var(--accent, #C9A96E);
  color: var(--accent-contrast, #000000);
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-decoration: none;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(var(--accent-rgb, 201, 169, 110), 0.3);
  transition: transform 0.3s cubic-bezier(.25, .46, .45, .94),
              box-shadow 0.3s cubic-bezier(.25, .46, .45, .94);
}

.btn-pill-glow:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 30px rgba(var(--accent-rgb, 201, 169, 110), 0.4);
}

.btn-pill-glow:active {
  transform: translateY(0);
  box-shadow: 0 2px 12px rgba(var(--accent-rgb, 201, 169, 110), 0.25);
}

/* Dark accent variant (for light backgrounds) */
.btn-pill-glow--dark {
  background: var(--color-dark, #0a0a0a);
  color: #ffffff;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

.btn-pill-glow--dark:hover {
  box-shadow: 0 6px 30px rgba(0, 0, 0, 0.3);
}

/* Small variant */
.btn-pill-glow--sm {
  padding: 10px 32px;
  font-size: 0.75rem;
}

/* Large variant */
.btn-pill-glow--lg {
  padding: 18px 56px;
  font-size: 0.9rem;
}
</style>
```

## Dependencies
- CSS custom properties: `--accent` (button color), `--accent-rgb` (for box-shadow rgba), `--accent-contrast` (text color on accent)
- If `--accent-rgb` is not defined, the fallback uses gold (201, 169, 110)
- Set `--accent-contrast` to `#000` for light accents, `#fff` for dark accents

## When To Use
- **Industry fit**: Universal -- the primary CTA for every luxury redesign
- **Best for**: Hero section CTAs, form submit buttons, pricing card buttons, any primary action
- **Pairs well with**: ghost-outline (as secondary CTA next to pill-glow), arrow-expand (for tertiary links below)

## Injection Point
Place as the primary call-to-action in hero sections, at the end of feature sections, and in pricing cards. Typically appears as `<a>` for links or `<button>` for form submissions. Use the `--sm` variant inside cards and `--lg` variant in hero sections.
