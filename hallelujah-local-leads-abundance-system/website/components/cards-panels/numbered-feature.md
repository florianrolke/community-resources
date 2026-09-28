# Numbered Feature Card
> Large translucent serif numbers anchor each service card, creating editorial rhythm and scannable hierarchy

## Preview
- Live: https://delta-vega-luxury.preview.florianrolke.com

## What It Does
Displays services or features with oversized decorative numbers (01, 02, 03...) in a muted accent color. The large serif numbers create a visual rhythm that guides the eye through the content sequentially. The number sits at reduced opacity so it acts as a background texture rather than competing with the actual title and description.

## Code
```html
<section class="numbered-section">
  <div class="numbered-container">
    <div class="numbered-item">
      <div class="numbered-num">01</div>
      <h3 class="numbered-title">Strategic Consulting</h3>
      <p class="numbered-desc">In-depth analysis of your current position with actionable roadmaps for sustainable growth and market positioning.</p>
    </div>

    <div class="numbered-divider"></div>

    <div class="numbered-item">
      <div class="numbered-num">02</div>
      <h3 class="numbered-title">Brand Development</h3>
      <p class="numbered-desc">Complete visual identity systems from logo to guidelines, ensuring consistency across every customer touchpoint.</p>
    </div>

    <div class="numbered-divider"></div>

    <div class="numbered-item">
      <div class="numbered-num">03</div>
      <h3 class="numbered-title">Digital Transformation</h3>
      <p class="numbered-desc">Modern web platforms and automation systems that convert visitors into clients while reducing manual workload.</p>
    </div>

    <div class="numbered-divider"></div>

    <div class="numbered-item">
      <div class="numbered-num">04</div>
      <h3 class="numbered-title">Ongoing Partnership</h3>
      <p class="numbered-desc">Retained support with monthly strategy sessions, performance tracking, and continuous optimization of all assets.</p>
    </div>
  </div>
</section>

<style>
.numbered-section {
  padding: 6rem 2rem;
}

.numbered-container {
  max-width: 900px;
  margin: 0 auto;
}

.numbered-item {
  padding: 2.5rem 0;
  position: relative;
}

.numbered-num {
  font-family: 'Cormorant Garamond', serif;
  font-size: 4rem;
  font-weight: 300;
  color: var(--accent, #C9A96E);
  opacity: 0.3;
  line-height: 1;
  margin-bottom: 0.75rem;
  letter-spacing: -0.02em;
}

.numbered-title {
  font-family: var(--font-heading, 'Inter', sans-serif);
  font-size: 1.25rem;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 0.75rem 0;
  letter-spacing: 0.01em;
}

.numbered-desc {
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.95rem;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
  max-width: 600px;
}

.numbered-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  margin: 0;
}

/* Optional: side-by-side layout for wider screens */
@media (min-width: 900px) {
  .numbered-item {
    display: grid;
    grid-template-columns: 100px 1fr;
    grid-template-rows: auto auto;
    gap: 0 2rem;
  }

  .numbered-num {
    grid-row: 1 / -1;
    align-self: start;
    font-size: 5rem;
  }

  .numbered-title {
    align-self: end;
  }

  .numbered-desc {
    grid-column: 2;
  }
}
</style>
```

## Dependencies
- Google Font: `Cormorant Garamond` (for the decorative numbers)
- CSS custom property `--accent` for number color
- Dark background for contrast

## When To Use
- **Industry fit**: Luxury, finance, legal, architecture, consulting -- any brand that values structure
- **Best for**: Process steps, service breakdowns, methodology sections, "How it works" flows
- **Pairs well with**: sticky-card-stack (animated scroll reveal), hover-lift (add lift to each item), gold-gradient-line (replace the divider)

## Injection Point
Replace a services or process section. Works best as a vertically stacked list within a centered container. The dividers between items are optional -- remove `.numbered-divider` elements for a cleaner look.
