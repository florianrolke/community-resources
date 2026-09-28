# Real Estate
> Warm earth tones with gold accents -- property photos breathe through light overlays

## Preview
- Live: https://ezhomesfast3-luxury.preview.florianrolke.com

## What It Does
A warm, property-focused palette for real estate agents, brokerages, and property investors. The low-opacity overlay (40-55%) lets hero property photos dominate since the listing is the product. Warm gold and cream tones create approachability while maintaining luxury positioning. Layout favors large imagery with compact text.

## Code
```html
<!-- Real Estate Palette - CSS Custom Properties -->
<style>
  :root {
    /* Core colors */
    --bg-deep: #0f1410;
    --bg-card: #1a1f1c;
    --bg-elevated: #242a26;
    --accent: #c4842a;
    --accent-hover: #d49a3e;
    --gold: #d4af37;
    --gold-muted: rgba(212, 175, 55, 0.12);
    --text: #f5f0e8;
    --text-muted: #b8b0a0;
    --text-heading: #ffffff;
    --border: rgba(196, 132, 42, 0.15);

    /* Typography */
    --font-heading: 'Playfair Display', 'Georgia', serif;
    --font-body: 'Source Sans Pro', 'Helvetica Neue', sans-serif;
    --heading-weight: 400;
    --heading-weight-bold: 700;
    --body-weight: 300;
    --body-weight-medium: 400;

    /* Photo overlay - keep low so properties show */
    --overlay-opacity: 0.45;
  }

  body {
    background: var(--bg-deep);
    color: var(--text);
    font-family: var(--font-body);
    font-weight: var(--body-weight);
    line-height: 1.7;
  }

  h1, h2, h3 {
    font-family: var(--font-heading);
    font-weight: var(--heading-weight);
    color: var(--text-heading);
  }

  h1 { font-size: clamp(2.5rem, 5vw, 4.5rem); line-height: 1.1; }
  h2 { font-size: clamp(1.8rem, 3.5vw, 3rem); line-height: 1.2; }
  h3 { font-size: clamp(1.2rem, 2vw, 1.5rem); font-weight: var(--heading-weight-bold); }

  /* Property stat counter */
  .stat-value {
    font-family: var(--font-heading);
    font-size: 3rem;
    font-weight: 700;
    color: var(--accent);
  }
  .stat-label {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: var(--text-muted);
  }

  /* Property card */
  .card-property {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }
  .card-property:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
  }
  .card-property img {
    width: 100%;
    height: 220px;
    object-fit: cover;
  }
  .card-property-content {
    padding: 1.5rem;
  }

  /* CTA Button */
  .btn-realestate {
    background: var(--accent);
    color: #ffffff;
    padding: 14px 32px;
    border: none;
    border-radius: 8px;
    font-family: var(--font-body);
    font-weight: 500;
    font-size: 0.95rem;
    cursor: pointer;
    transition: background 0.3s ease;
  }
  .btn-realestate:hover {
    background: var(--accent-hover);
  }
</style>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Source+Sans+Pro:wght@300;400;600&display=swap" rel="stylesheet">

<!-- Example Hero (35% text / 65% image) -->
<section style="position:relative;min-height:100vh;display:flex;align-items:center;overflow:hidden;">
  <!-- Large property photo -->
  <div style="position:absolute;inset:0;z-index:0;">
    <img src="luxury-property.jpg" alt="" style="width:100%;height:100%;object-fit:cover;">
    <div style="position:absolute;inset:0;background:linear-gradient(90deg, rgba(15,20,16,0.85) 0%, rgba(15,20,16,0.45) 50%, rgba(15,20,16,0.2) 100%);"></div>
  </div>
  <!-- Compact text, left side -->
  <div style="position:relative;z-index:1;max-width:520px;padding:4rem 6%;">
    <p style="color:var(--accent);text-transform:uppercase;letter-spacing:0.2em;font-size:0.8rem;margin-bottom:1rem;">Premium Properties</p>
    <h1>Find Your<br>Dream Home</h1>
    <p style="color:var(--text-muted);font-size:1.1rem;margin:1.5rem 0;">
      Curated listings in the most sought-after neighborhoods.
    </p>
    <button class="btn-realestate">View Listings</button>
  </div>
</section>
```

## Dependencies
- Google Fonts: Playfair Display (400, 700) + Source Sans Pro (300, 400, 600)

## When To Use
- **Industry fit**: Real estate agents, brokerages, property management, home builders
- **Best for**: Sites where property photography is the primary selling tool
- **Pairs well with**: image-hero-kenburns, environmental-bleed, pill-glow, counter-stats, bento-grid

## Injection Point
Apply CSS custom properties to `:root`. The key differentiator is the low overlay opacity (40-55%) -- real estate sites must let property photos breathe. Use the gradient overlay (opaque left, transparent right) so text remains readable while the photo dominates the right side.
