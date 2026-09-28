# Bento Grid
> Asymmetric masonry-style grid with mixed-size tiles creating visual hierarchy through spatial variation

## Preview
- Live: https://ezhomesfast3-luxury.preview.florianrolke.com

## What It Does
Creates an Apple-style bento grid layout where a hero card spans two columns while smaller tiles fill the remaining space. The asymmetric sizing naturally draws the eye to the featured content first, then guides it through secondary items. Collapses cleanly to a single column on mobile.

## Code
```html
<section class="bento-section">
  <div class="bento-container">
    <h2 class="bento-heading">Our Services</h2>
    <div class="bento-grid">
      <!-- Hero card: spans 2 columns -->
      <div class="bento-card bento-hero">
        <div class="bento-card-inner">
          <span class="bento-label">Featured</span>
          <h3>Primary Service</h3>
          <p>The flagship offering that deserves the most visual real estate. Describe the core value proposition here with enough detail to compel action.</p>
          <a href="#" class="bento-link">Explore &rarr;</a>
        </div>
      </div>

      <!-- Standard card -->
      <div class="bento-card">
        <div class="bento-card-inner">
          <span class="bento-label">01</span>
          <h3>Service Two</h3>
          <p>Secondary service with a brief description of value delivered.</p>
        </div>
      </div>

      <!-- Standard card -->
      <div class="bento-card">
        <div class="bento-card-inner">
          <span class="bento-label">02</span>
          <h3>Service Three</h3>
          <p>Another supporting service or feature description.</p>
        </div>
      </div>

      <!-- Standard card -->
      <div class="bento-card">
        <div class="bento-card-inner">
          <span class="bento-label">03</span>
          <h3>Service Four</h3>
          <p>Tertiary offering with concise benefit statement.</p>
        </div>
      </div>

      <!-- Wide card: spans 2 columns -->
      <div class="bento-card bento-wide">
        <div class="bento-card-inner">
          <span class="bento-label">Highlight</span>
          <h3>Key Differentiator</h3>
          <p>What sets you apart from competitors. This wider card draws attention to a critical selling point.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<style>
.bento-section {
  padding: 6rem 2rem;
}

.bento-container {
  max-width: 1200px;
  margin: 0 auto;
}

.bento-heading {
  font-family: var(--font-heading, 'Cormorant Garamond', serif);
  font-size: 2.5rem;
  font-weight: 400;
  color: #ffffff;
  margin-bottom: 3rem;
  letter-spacing: -0.01em;
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
  grid-auto-rows: minmax(200px, auto);
}

.bento-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  overflow: hidden;
  transition: transform 0.3s cubic-bezier(.25, .46, .45, .94),
              border-color 0.3s ease,
              box-shadow 0.3s ease;
}

.bento-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.15);
}

.bento-hero {
  grid-column: span 2;
  grid-row: span 2;
  background: linear-gradient(135deg, rgba(var(--accent-rgb, 201, 169, 110), 0.08), rgba(0, 0, 0, 0.4));
}

.bento-wide {
  grid-column: span 2;
}

.bento-card-inner {
  padding: 2rem;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.bento-hero .bento-card-inner {
  padding: 3rem;
}

.bento-label {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.7rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--accent, #C9A96E);
  margin-bottom: 1rem;
  opacity: 0.7;
}

.bento-card h3 {
  font-family: var(--font-heading, 'Cormorant Garamond', serif);
  font-size: 1.3rem;
  font-weight: 500;
  color: #ffffff;
  margin: 0 0 0.75rem 0;
}

.bento-hero h3 {
  font-size: 1.8rem;
}

.bento-card p {
  font-size: 0.9rem;
  line-height: 1.65;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.bento-link {
  display: inline-block;
  margin-top: 1.5rem;
  font-size: 0.85rem;
  color: var(--accent, #C9A96E);
  text-decoration: none;
  transition: opacity 0.3s;
}

.bento-link:hover {
  opacity: 0.75;
}

/* Responsive: collapse to single column */
@media (max-width: 768px) {
  .bento-grid {
    grid-template-columns: 1fr;
  }
  .bento-hero,
  .bento-wide {
    grid-column: span 1;
    grid-row: span 1;
  }
}

@media (max-width: 1024px) and (min-width: 769px) {
  .bento-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .bento-hero {
    grid-column: span 2;
    grid-row: span 1;
  }
}
</style>
```

## Dependencies
- CSS custom properties: `--accent`, `--accent-rgb`, `--font-heading`, `--font-mono`
- Dark page background for contrast
- Minimum 4-5 cards to fill the grid naturally

## When To Use
- **Industry fit**: Tech, SaaS, modern brands, creative agencies
- **Best for**: Services sections, feature showcases, portfolio grids where one item should dominate
- **Pairs well with**: hover-lift (add to individual cards), glassmorphism (swap card backgrounds), numbered-feature (use as labels)

## Injection Point
Replace an existing services or features section. The `<section>` is self-contained -- drop it between other page sections. Adjust grid-auto-rows for taller/shorter cards.
