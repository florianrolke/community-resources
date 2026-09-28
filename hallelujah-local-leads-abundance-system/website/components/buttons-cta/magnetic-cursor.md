# Magnetic Cursor Button
> Button that magnetically attracts toward the cursor when nearby, with inner text parallax for depth

## Preview
- Live: concept (not widely deployed)

## What It Does
Uses JavaScript to track the mouse position relative to the button. When the cursor enters an 80px proximity radius, the button smoothly translates toward the cursor. The inner text element moves at 40% of the button movement, creating a subtle parallax depth effect. On mouse leave, the button springs back to its original position via a custom cubic-bezier ease. Disabled on touch devices where there is no hover cursor.

## Code
```html
<a href="#contact" class="btn-magnetic" data-magnetic>
  <span class="btn-magnetic-text">Start Your Project</span>
</a>

<style>
.btn-magnetic {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  border-radius: 9999px;
  padding: 16px 52px;
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
  transition: transform 0.5s cubic-bezier(0.23, 1, 0.32, 1),
              box-shadow 0.3s ease;
  box-shadow: 0 4px 20px rgba(var(--accent-rgb, 201, 169, 110), 0.3);
  will-change: transform;
}

.btn-magnetic-text {
  display: inline-block;
  transition: transform 0.5s cubic-bezier(0.23, 1, 0.32, 1);
  will-change: transform;
}

.btn-magnetic:hover {
  box-shadow: 0 8px 32px rgba(var(--accent-rgb, 201, 169, 110), 0.4);
}

/* Disable on touch devices */
@media (pointer: coarse) {
  .btn-magnetic {
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }
}
</style>

<script>
(function() {
  const RADIUS = 80;         // Attraction radius in pixels
  const STRENGTH = 0.3;      // Button movement multiplier
  const TEXT_STRENGTH = 0.12; // Inner text movement (40% of button = parallax)

  document.querySelectorAll('[data-magnetic]').forEach(function(btn) {
    var textEl = btn.querySelector('.btn-magnetic-text');

    // Skip on touch devices
    if (window.matchMedia('(pointer: coarse)').matches) return;

    btn.addEventListener('mousemove', function(e) {
      var rect = btn.getBoundingClientRect();
      var cx = rect.left + rect.width / 2;
      var cy = rect.top + rect.height / 2;
      var dx = e.clientX - cx;
      var dy = e.clientY - cy;
      var dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < RADIUS) {
        btn.style.transform = 'translate(' + (dx * STRENGTH) + 'px, ' + (dy * STRENGTH) + 'px)';
        if (textEl) {
          textEl.style.transform = 'translate(' + (dx * TEXT_STRENGTH) + 'px, ' + (dy * TEXT_STRENGTH) + 'px)';
        }
      }
    });

    btn.addEventListener('mouseleave', function() {
      btn.style.transform = 'translate(0, 0)';
      if (textEl) {
        textEl.style.transform = 'translate(0, 0)';
      }
    });
  });
})();
</script>
```

## Dependencies
- JavaScript enabled (progressive enhancement -- button works without JS, just loses magnetic effect)
- No external libraries required
- `data-magnetic` attribute on each button that should have the effect
- Touch device detection via `pointer: coarse` media query

## When To Use
- **Industry fit**: Creative agencies, luxury brands, tech/SaaS, portfolio sites -- brands that want to feel interactive
- **Best for**: Hero section primary CTA, single prominent call-to-action, landing page conversion button
- **Pairs well with**: custom-crosshair-cursor (both create interactive feel), pill-glow (same visual style, magnetic adds interactivity)

## Injection Point
Replace the hero section's primary CTA `<a>` or `<button>` element. Add `data-magnetic` attribute and wrap the text in `.btn-magnetic-text`. Place the `<script>` block before `</body>`. Use sparingly -- one or two magnetic buttons per page maximum, otherwise the effect feels gimmicky.
