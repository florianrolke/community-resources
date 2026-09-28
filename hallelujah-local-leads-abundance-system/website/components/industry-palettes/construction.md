# Construction
> Bold contrast with amber accents on dark backgrounds -- strength, reliability, no-nonsense

## Preview
- Live: https://nexgen-roofing.preview.florianrolke.com

## What It Does
A high-contrast palette for construction companies, roofing, HVAC, plumbing, and trades. Bold sans-serif headings at heavy weights (700-800) project strength and reliability. Amber/orange accents create urgency and visibility. Photo overlays at 60-70% keep worksite imagery present but ensure text punches through clearly.

## Code
```html
<!-- Construction Palette - CSS Custom Properties -->
<style>
  :root {
    /* Core colors */
    --bg-deep: #1a1a1a;
    --bg-card: #242424;
    --bg-elevated: #2e2e2e;
    --accent: #f59e0b;
    --accent-hover: #fbbf24;
    --accent-dark: #d97706;
    --text: #ffffff;
    --text-muted: #a3a3a3;
    --text-heading: #ffffff;
    --border: rgba(245, 158, 11, 0.2);

    /* Typography */
    --font-heading: 'Overpass', 'Arial Black', sans-serif;
    --font-body: 'Inter', 'Helvetica Neue', sans-serif;
    --heading-weight: 700;
    --heading-weight-bold: 800;
    --body-weight: 400;

    /* Photo overlay */
    --overlay-opacity: 0.65;
  }

  body {
    background: var(--bg-deep);
    color: var(--text);
    font-family: var(--font-body);
    font-weight: var(--body-weight);
    line-height: 1.6;
  }

  h1, h2, h3 {
    font-family: var(--font-heading);
    font-weight: var(--heading-weight);
    color: var(--text-heading);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  h1 { font-size: clamp(2.5rem, 6vw, 5rem); line-height: 1.05; font-weight: var(--heading-weight-bold); }
  h2 { font-size: clamp(1.8rem, 4vw, 3rem); line-height: 1.15; }
  h3 { font-size: clamp(1.1rem, 2vw, 1.4rem); }

  /* Accent bar */
  .accent-bar {
    width: 80px;
    height: 4px;
    background: var(--accent);
    margin: 1rem 0;
  }

  /* Stat counter */
  .stat-block {
    text-align: center;
    padding: 1.5rem;
  }
  .stat-block .number {
    font-family: var(--font-heading);
    font-size: 3.5rem;
    font-weight: 800;
    color: var(--accent);
    line-height: 1;
  }
  .stat-block .label {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: var(--text-muted);
    margin-top: 0.5rem;
  }

  /* Service card */
  .card-construction {
    background: var(--bg-card);
    border-left: 4px solid var(--accent);
    padding: 2rem;
    border-radius: 0 8px 8px 0;
    transition: transform 0.2s ease;
  }
  .card-construction:hover {
    transform: translateX(4px);
  }

  /* CTA Button */
  .btn-construction {
    background: var(--accent);
    color: #1a1a1a;
    padding: 16px 36px;
    border: none;
    border-radius: 6px;
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: background 0.3s ease, transform 0.2s ease;
  }
  .btn-construction:hover {
    background: var(--accent-hover);
    transform: translateY(-2px);
  }
</style>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Overpass:wght@700;800;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">

<!-- Example Hero (worksite photo, bold text, high contrast) -->
<section style="position:relative;min-height:100vh;display:flex;align-items:center;overflow:hidden;">
  <!-- Worksite photo background -->
  <div style="position:absolute;inset:0;z-index:0;">
    <img src="construction-site.jpg" alt="" style="width:100%;height:100%;object-fit:cover;">
    <div style="position:absolute;inset:0;background:linear-gradient(180deg, rgba(26,26,26,0.75) 0%, rgba(26,26,26,0.65) 50%, rgba(26,26,26,0.85) 100%);"></div>
  </div>
  <!-- Bold left-aligned content -->
  <div style="position:relative;z-index:1;max-width:700px;padding:4rem 6%;">
    <div class="accent-bar"></div>
    <h1>Built To<br>Last</h1>
    <p style="color:var(--text-muted);font-size:1.15rem;margin:1.5rem 0 2rem;max-width:480px;">
      25+ years of reliable roofing, siding, and gutter solutions for homeowners who demand quality.
    </p>
    <button class="btn-construction">Get Free Estimate</button>
  </div>
</section>

<!-- Stats bar example -->
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;padding:3rem 6%;background:var(--bg-card);">
  <div class="stat-block">
    <div class="number">25+</div>
    <div class="label">Years Experience</div>
  </div>
  <div class="stat-block">
    <div class="number">3,200</div>
    <div class="label">Projects Completed</div>
  </div>
  <div class="stat-block">
    <div class="number">4.9</div>
    <div class="label">Star Rating</div>
  </div>
  <div class="stat-block">
    <div class="number">100%</div>
    <div class="label">Licensed & Insured</div>
  </div>
</div>
```

## Dependencies
- Google Fonts: Overpass (700, 800, 900) + Inter (400, 500, 600)

## When To Use
- **Industry fit**: Roofing, general contracting, HVAC, plumbing, electrical, landscaping
- **Best for**: Service-based trades that need to project reliability and urgency
- **Pairs well with**: video-hero, counter-stats, pill-glow, scroll-reveal, numbered-feature

## Injection Point
Apply CSS custom properties to `:root`. Use uppercase headings with the accent bar divider. The left-border card style (`.card-construction`) works well for service listings. Stats bar should sit directly below the hero as social proof.
