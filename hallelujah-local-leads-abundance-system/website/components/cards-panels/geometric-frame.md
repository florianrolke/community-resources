# Geometric Frame
> Architectural corner brackets formed by thin accent-colored lines, framing content with editorial precision

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
Creates four corner bracket decorations around a content block using CSS pseudo-elements. Each corner has a horizontal and vertical line segment in the accent color at reduced opacity, forming an incomplete rectangle that frames the content with architectural elegance. The open sides prevent the frame from feeling like a border or box.

## Code
```html
<div class="geo-frame-wrapper">
  <div class="geo-frame">
    <div class="geo-corner geo-tl"></div>
    <div class="geo-corner geo-tr"></div>
    <div class="geo-corner geo-bl"></div>
    <div class="geo-corner geo-br"></div>

    <div class="geo-frame-content">
      <blockquote class="geo-quote">
        &ldquo;Working with this team transformed not just our brand presence but our entire approach to client acquisition. Revenue increased 340% in the first quarter.&rdquo;
      </blockquote>
      <div class="geo-attribution">
        <span class="geo-author">James Richardson</span>
        <span class="geo-role">CEO, Sterling Partners</span>
      </div>
    </div>
  </div>
</div>

<style>
.geo-frame-wrapper {
  padding: 4rem 2rem;
  max-width: 800px;
  margin: 0 auto;
}

.geo-frame {
  position: relative;
  padding: 3rem;
}

/* Corner bracket base */
.geo-corner {
  position: absolute;
  width: 35px;
  height: 35px;
}

.geo-corner::before,
.geo-corner::after {
  content: '';
  position: absolute;
  background: var(--accent, #C9A96E);
  opacity: 0.4;
}

/* Horizontal line */
.geo-corner::before {
  width: 35px;
  height: 1px;
}

/* Vertical line */
.geo-corner::after {
  width: 1px;
  height: 35px;
}

/* Top-left */
.geo-tl {
  top: 0;
  left: 0;
}
.geo-tl::before { top: 0; left: 0; }
.geo-tl::after { top: 0; left: 0; }

/* Top-right */
.geo-tr {
  top: 0;
  right: 0;
}
.geo-tr::before { top: 0; right: 0; }
.geo-tr::after { top: 0; right: 0; }

/* Bottom-left */
.geo-bl {
  bottom: 0;
  left: 0;
}
.geo-bl::before { bottom: 0; left: 0; }
.geo-bl::after { bottom: 0; left: 0; }

/* Bottom-right */
.geo-br {
  bottom: 0;
  right: 0;
}
.geo-br::before { bottom: 0; right: 0; }
.geo-br::after { bottom: 0; right: 0; }

/* Content */
.geo-frame-content {
  text-align: center;
}

.geo-quote {
  font-family: 'Cormorant Garamond', serif;
  font-size: 1.5rem;
  font-weight: 400;
  font-style: italic;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.85);
  margin: 0 0 2rem 0;
  padding: 0;
  border: none;
}

.geo-attribution {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  align-items: center;
}

.geo-author {
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.85rem;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.geo-role {
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.05em;
}

/* Responsive */
@media (max-width: 640px) {
  .geo-frame {
    padding: 2rem 1.5rem;
  }
  .geo-quote {
    font-size: 1.2rem;
  }
}
</style>
```

## Dependencies
- CSS custom property `--accent` for corner line color (falls back to gold)
- Google Font: `Cormorant Garamond` for the quote text (optional, any serif works)
- Dark background for the accent lines to be visible

## When To Use
- **Industry fit**: Finance, luxury, law, architecture, fine dining -- any brand signaling precision and heritage
- **Best for**: Testimonials, blockquotes, featured statistics, highlight boxes, pull quotes
- **Pairs well with**: monospace-labels (add label above frame), gold-gradient-line (use as section divider above/below), film-grain (ambient texture)

## Injection Point
Wrap any content block that needs visual emphasis. Most commonly used around testimonial quotes or key statistics. Place inside a section as a standalone element, not inside a card grid.
