# Diagonal Clip
> CSS clip-path that angles the bottom (or both edges) of a section, creating dynamic diagonal transitions

## Preview
- Live: Used across multiple luxury redesigns for section transitions

## What It Does
Applies a CSS `clip-path: polygon()` to a section element, slicing the bottom edge at an angle. This creates a diagonal transition between sections that adds visual energy and breaks the monotony of horizontal section boundaries. A dual-angle variant clips both top and bottom for sections sandwiched between others.

## Code
```html
<!-- Bottom angle only -->
<section class="section-diagonal">
  <div class="section-diagonal-content">
    <h2>Our Approach</h2>
    <p>Content goes here. The bottom edge of this section is angled.</p>
  </div>
</section>

<!-- Both top and bottom angled -->
<section class="section-diagonal section-diagonal--both">
  <div class="section-diagonal-content">
    <h2>Featured Work</h2>
    <p>Both edges are angled, creating a parallelogram-shaped section.</p>
  </div>
</section>

<!-- Reverse angle direction -->
<section class="section-diagonal section-diagonal--reverse">
  <div class="section-diagonal-content">
    <h2>Testimonials</h2>
    <p>The angle goes the opposite direction for visual variety.</p>
  </div>
</section>

<style>
/* Bottom edge angled: straight top, angled bottom */
.section-diagonal {
  position: relative;
  padding: 6rem 2rem 8rem;
  clip-path: polygon(0 0, 100% 0, 100% 88%, 0 100%);
  background: var(--section-bg, #0a0a0a);
}

/* Both top and bottom angled */
.section-diagonal--both {
  padding: 8rem 2rem;
  clip-path: polygon(0 5%, 100% 0, 100% 95%, 0 100%);
}

/* Reverse angle direction */
.section-diagonal--reverse {
  clip-path: polygon(0 0, 100% 0, 100% 100%, 0 88%);
}

/* Top angle only (for section below a diagonal) */
.section-diagonal--top {
  clip-path: polygon(0 5%, 100% 0, 100% 100%, 0 100%);
  padding: 8rem 2rem 6rem;
}

/* Subtle angle (less dramatic) */
.section-diagonal--subtle {
  clip-path: polygon(0 0, 100% 0, 100% 95%, 0 100%);
}

/* Content container */
.section-diagonal-content {
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.section-diagonal-content h2 {
  font-family: var(--font-heading, 'Cormorant Garamond', serif);
  font-size: 2.5rem;
  color: #ffffff;
  margin-bottom: 1.5rem;
}

.section-diagonal-content p {
  font-size: 1rem;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  max-width: 600px;
}

/* Overlap compensation: negative margin pulls next section up */
.section-diagonal + section {
  margin-top: -4rem;
  position: relative;
  z-index: 1;
}

/* When stacking two diagonals */
.section-diagonal + .section-diagonal--top {
  margin-top: -6rem;
}
</style>
```

## Dependencies
- CSS `clip-path` (supported in all modern browsers, IE11 excluded)
- Extra bottom padding to compensate for the clipped area
- May need negative margin on the following section to close the visual gap

## When To Use
- **Industry fit**: Construction, real estate, sports, automotive -- bold, dynamic brands
- **Best for**: Hero-to-content transitions, alternating background sections, creating visual momentum
- **Pairs well with**: environmental-bleed (background image inside the clipped section), scanlines (overlay texture on the section)

## Injection Point
Apply directly to `<section>` elements. Add the class to the section tag and increase bottom padding to account for the clipped area. Use `margin-top: -4rem` (or adjust) on the next section to prevent a visible gap. Alternate between `--reverse` variants on consecutive sections for a zigzag flow.
