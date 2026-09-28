# Cursor Spotlight
> Interactive radial gradient light that follows the mouse cursor across the hero section

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
Adds a large radial gradient glow (650px diameter) that tracks the user's mouse position across the hero section. Implemented via CSS custom properties (`--spot-x`, `--spot-y`) set by a JS `mousemove` listener, applied through a `::before` pseudo-element. Automatically disabled on touch devices and mobile viewports to avoid broken interactions.

## Code
```html
<!-- CSS (inject in <head>) -->
<style>
.spotlight-hero {
  position: relative;
  overflow: hidden;
  --spot-x: 50%;
  --spot-y: 50%;
}
.spotlight-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: radial-gradient(650px circle at var(--spot-x) var(--spot-y),
    rgba(116, 86, 241, 0.08),
    transparent 60%);
  transition: opacity 0.3s ease;
  opacity: 1;
}

/* Disable on touch/mobile */
@media (hover: none), (max-width: 768px) {
  .spotlight-hero::before {
    opacity: 0;
  }
}
</style>

<!-- Hero section markup -->
<section class="spotlight-hero" style="min-height:100vh;display:flex;align-items:center;justify-content:center;">
  <!-- Your hero content here (z-index: 2 to stay above spotlight) -->
  <div style="position:relative;z-index:2;text-align:center;">
    <h1>Your Headline</h1>
    <p>Subheading</p>
  </div>
</section>

<!-- JS (inject before </body>) -->
<script>
(function(){
  var hero = document.querySelector('.spotlight-hero');
  if (!hero) return;
  // Skip on touch devices
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) return;

  hero.addEventListener('mousemove', function(e){
    var rect = hero.getBoundingClientRect();
    hero.style.setProperty('--spot-x', (e.clientX - rect.left) + 'px');
    hero.style.setProperty('--spot-y', (e.clientY - rect.top) + 'px');
  }, { passive: true });
})();
</script>
```

### Customization

Replace the glow color `rgba(116, 86, 241, 0.08)` with the client's accent color at low opacity (0.06-0.12). Adjust the gradient size (650px) for larger or smaller spotlights.

## Dependencies
- No external libraries
- CSS custom properties support (all modern browsers)
- `::before` pseudo-element on the hero section

## When To Use
- **Industry fit:** Finance, tech, SaaS, luxury brands — any site wanting interactive sophistication
- **Best for:** Dark-themed heroes where the subtle glow creates a sense of responsive intelligence
- **Pairs well with:** parallax-depth-layers, film-grain, metallic-shimmer

## Injection Point
Add the `spotlight-hero` class to the hero `<section>` or `<header>`. CSS goes in `<head>`. JS goes before `</body>`. Hero content needs `position: relative; z-index: 2` to stay above the spotlight layer.

**Source:** `.agent/skills/luxury-editorial-finance/SKILL.md` — Element 4 (Cursor-Following Spotlight)
