# Custom Crosshair Cursor
> A fixed crosshair reticle that replaces the default cursor, with directional lines and an optional trailing circle

## Preview
- Live: https://populon-demo.client.of.florianrolke.com

## What It Does
Replaces the default cursor with a custom crosshair built from a central dot and four directional line segments. A fixed-position div follows the mouse via a `mousemove` listener. The crosshair has a small red/accent-colored center dot (4px) with four extending lines (top, bottom, left, right). An optional concentric trailing circle follows with slight delay for added depth. Automatically hidden on touch devices where no cursor exists.

## Code
```html
<!-- Cursor elements (add as last children of <body>) -->
<div class="cursor-crosshair" id="cursorCrosshair" aria-hidden="true">
  <div class="cursor-dot"></div>
  <div class="cursor-line cursor-line-top"></div>
  <div class="cursor-line cursor-line-bottom"></div>
  <div class="cursor-line cursor-line-left"></div>
  <div class="cursor-line cursor-line-right"></div>
</div>
<div class="cursor-trail" id="cursorTrail" aria-hidden="true"></div>

<style>
/* Hide default cursor */
* {
  cursor: none !important;
}

/* Crosshair container */
.cursor-crosshair {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 99999;
  pointer-events: none;
  transform: translate(-50%, -50%);
  will-change: transform;
}

/* Center dot */
.cursor-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--cursor-color, #e63946);
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

/* Directional lines */
.cursor-line {
  position: absolute;
  background: var(--cursor-color, #e63946);
  opacity: 0.7;
}

.cursor-line-top {
  width: 1px;
  height: 10px;
  left: 50%;
  bottom: calc(50% + 5px);
  transform: translateX(-50%);
}

.cursor-line-bottom {
  width: 1px;
  height: 10px;
  left: 50%;
  top: calc(50% + 5px);
  transform: translateX(-50%);
}

.cursor-line-left {
  width: 10px;
  height: 1px;
  top: 50%;
  right: calc(50% + 5px);
  transform: translateY(-50%);
}

.cursor-line-right {
  width: 10px;
  height: 1px;
  top: 50%;
  left: calc(50% + 5px);
  transform: translateY(-50%);
}

/* Optional trailing circle */
.cursor-trail {
  position: fixed;
  top: 0;
  left: 0;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(var(--cursor-color-rgb, 230, 57, 70), 0.3);
  border-radius: 50%;
  z-index: 99998;
  pointer-events: none;
  transform: translate(-50%, -50%);
  transition: transform 0.15s ease-out, width 0.2s ease, height 0.2s ease, border-color 0.2s ease;
  will-change: transform;
}

/* Hover state: trail expands over interactive elements */
.cursor-trail.hover-active {
  width: 48px;
  height: 48px;
  border-color: rgba(var(--cursor-color-rgb, 230, 57, 70), 0.5);
}

/* Hide on touch/mobile */
@media (pointer: coarse) {
  .cursor-crosshair,
  .cursor-trail {
    display: none !important;
  }

  * {
    cursor: auto !important;
  }
}

/* Also hide when cursor leaves the window */
.cursor-crosshair.hidden,
.cursor-trail.hidden {
  opacity: 0;
}
</style>

<script>
(function() {
  // Skip on touch devices
  if (window.matchMedia('(pointer: coarse)').matches) return;

  var crosshair = document.getElementById('cursorCrosshair');
  var trail = document.getElementById('cursorTrail');
  if (!crosshair) return;

  var mouseX = 0, mouseY = 0;
  var trailX = 0, trailY = 0;

  // Track mouse position
  document.addEventListener('mousemove', function(e) {
    mouseX = e.clientX;
    mouseY = e.clientY;
    crosshair.style.left = mouseX + 'px';
    crosshair.style.top = mouseY + 'px';
    crosshair.classList.remove('hidden');
    if (trail) trail.classList.remove('hidden');
  });

  // Smooth trail follow (lerp)
  if (trail) {
    function animateTrail() {
      trailX += (mouseX - trailX) * 0.15;
      trailY += (mouseY - trailY) * 0.15;
      trail.style.left = trailX + 'px';
      trail.style.top = trailY + 'px';
      requestAnimationFrame(animateTrail);
    }
    animateTrail();
  }

  // Expand trail on interactive elements
  var interactiveSelectors = 'a, button, [role="button"], input, textarea, select, [data-magnetic]';
  document.querySelectorAll(interactiveSelectors).forEach(function(el) {
    el.addEventListener('mouseenter', function() {
      if (trail) trail.classList.add('hover-active');
    });
    el.addEventListener('mouseleave', function() {
      if (trail) trail.classList.remove('hover-active');
    });
  });

  // Hide when cursor leaves window
  document.addEventListener('mouseleave', function() {
    crosshair.classList.add('hidden');
    if (trail) trail.classList.add('hidden');
  });
})();
</script>
```

## Dependencies
- JavaScript for mouse tracking and animation loop
- CSS custom properties: `--cursor-color` (crosshair color, defaults to red), `--cursor-color-rgb` (same in RGB for alpha usage)
- `requestAnimationFrame` for smooth trail animation
- Touch device detection via `pointer: coarse` media query

## When To Use
- **Industry fit**: Creative agencies, gaming, film/media, tech, avant-garde brands -- high-design sites that justify unconventional interaction
- **Best for**: Portfolio sites, brand showcases, creative landing pages where the cursor IS part of the design language
- **Pairs well with**: magnetic-cursor buttons (crosshair + magnetic = fully custom interaction), film-grain (both add analog character), scanlines (CRT aesthetic)

## Injection Point
Add the HTML elements as the last children of `<body>`, just before `</body>`. Place the `<script>` block after the HTML elements. The `cursor: none` CSS must be global -- add it to the page's main stylesheet. Use sparingly: only on sites where the custom cursor enhances the brand story. Never use on utility/form-heavy pages where cursor precision matters.

To customize:
- Change `--cursor-color` for different crosshair colors (red = populon, gold = luxury, white = minimal)
- Remove `.cursor-trail` for crosshair-only (no trailing circle)
- Adjust line lengths by changing `height: 10px` and `width: 10px` on `.cursor-line` elements
