# Med Spa & Wellness
> Soft rose and cream with thin sans-serif elegance -- clean luxury and clinical trust

## Preview
- Live: concept (adapted from delta-vega-luxury palette)

## What It Does
A refined, calming palette for med spas, dermatology clinics, cosmetic surgery, wellness centers, and luxury beauty brands. Rose gold accents convey premium femininity without being overtly pink, cream backgrounds feel clinical yet warm, and thin sans-serif typography projects modern cleanliness. Generous white space and soft shadows create an airy, spa-like feel.

## Code
```html
<!-- Med Spa & Wellness Palette - CSS Custom Properties -->
<style>
  :root {
    /* Core colors */
    --bg-deep: #1a0f14;
    --bg-card: #faf7f5;
    --bg-elevated: #ffffff;
    --bg-cream: #fdf9f6;
    --accent: #b76e79;
    --accent-hover: #c9818c;
    --rose-gold: #d4a574;
    --rose-gold-muted: rgba(212, 165, 116, 0.12);
    --text: #4a3f3a;
    --text-light: #f5efe8;
    --text-muted: #9a8e86;
    --text-heading: #2d2420;
    --border: rgba(183, 110, 121, 0.12);
    --border-rose: rgba(212, 165, 116, 0.20);

    /* Typography */
    --font-heading: 'Cormorant Garamond', 'Georgia', serif;
    --font-body: 'Inter', 'Helvetica Neue', sans-serif;
    --heading-weight: 300;
    --heading-weight-bold: 400;
    --body-weight: 300;
    --body-weight-medium: 400;

    /* Photo overlay */
    --overlay-opacity: 0.40;
  }

  /* Base styles */
  body {
    background: var(--bg-cream);
    color: var(--text);
    font-family: var(--font-body);
    font-weight: var(--body-weight);
    line-height: 1.7;
  }

  h1, h2, h3 {
    font-family: var(--font-heading);
    font-weight: var(--heading-weight);
    color: var(--text-heading);
    letter-spacing: 0.03em;
  }

  h1 { font-size: clamp(2.2rem, 4.5vw, 4rem); line-height: 1.15; }
  h2 { font-size: clamp(1.6rem, 3vw, 2.5rem); line-height: 1.25; }
  h3 { font-size: clamp(1.1rem, 1.8vw, 1.35rem); font-weight: var(--heading-weight-bold); }

  /* Rose accent line */
  .rose-line {
    width: 50px;
    height: 1px;
    background: linear-gradient(90deg, var(--accent), transparent);
    margin: 1.5rem 0;
  }

  /* Card with soft shadow */
  .card-medspa {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.03);
    transition: box-shadow 0.3s ease, transform 0.3s ease;
  }
  .card-medspa:hover {
    box-shadow: 0 12px 40px rgba(183, 110, 121, 0.08);
    transform: translateY(-2px);
  }

  /* CTA Button */
  .btn-medspa {
    background: var(--accent);
    color: #ffffff;
    padding: 14px 36px;
    border: none;
    border-radius: 9999px;
    font-family: var(--font-body);
    font-weight: 400;
    font-size: 0.85rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    cursor: pointer;
    transition: background 0.3s ease, box-shadow 0.3s ease;
  }
  .btn-medspa:hover {
    background: var(--accent-hover);
    box-shadow: 0 6px 24px rgba(183, 110, 121, 0.25);
  }

  /* Outline variant */
  .btn-medspa-outline {
    background: transparent;
    color: var(--accent);
    padding: 13px 35px;
    border: 1px solid var(--accent);
    border-radius: 9999px;
    font-family: var(--font-body);
    font-weight: 400;
    font-size: 0.85rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    cursor: pointer;
    transition: background 0.3s ease, color 0.3s ease;
  }
  .btn-medspa-outline:hover {
    background: var(--accent);
    color: #ffffff;
  }

  /* Thin label */
  .label-medspa {
    font-family: var(--font-body);
    font-weight: 400;
    font-size: 0.65rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--accent);
  }
</style>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&family=Inter:wght@300;400&display=swap" rel="stylesheet">

<!-- Example Hero (centered, light/airy) -->
<section style="position:relative;min-height:90vh;display:flex;align-items:center;justify-content:center;text-align:center;overflow:hidden;background:var(--bg-cream);">
  <div style="position:absolute;inset:0;z-index:0;">
    <img src="medspa-treatment.jpg" alt="" style="width:100%;height:100%;object-fit:cover;opacity:0.15;">
  </div>
  <div style="position:relative;z-index:1;max-width:600px;padding:4rem 6%;">
    <p class="label-medspa" style="margin-bottom:1.5rem;">Advanced Aesthetics</p>
    <h1>Radiance,<br>Redefined</h1>
    <p style="color:var(--text-muted);font-size:1.05rem;margin:1.5rem 0 2.5rem;">
      Evidence-based treatments for natural, lasting beauty.
    </p>
    <div style="display:flex;gap:1rem;justify-content:center;">
      <button class="btn-medspa">Book Consultation</button>
      <button class="btn-medspa-outline">View Treatments</button>
    </div>
  </div>
</section>
```

## Dependencies
- Google Fonts: Cormorant Garamond (300, 400) + Inter (300, 400)

## When To Use
- **Industry fit**: Med spas, dermatology, cosmetic surgery, wellness centers, luxury beauty, skincare clinics
- **Best for**: Sites that need clinical trust combined with luxury positioning and feminine elegance
- **Pairs well with**: scroll-reveal, hover-lift, pill-glow, counter-stats, gold-gradient-line

## Injection Point
Apply CSS custom properties to `:root`. This palette defaults to light mode (cream `--bg-cream` background) unlike most others. Hero sections can use the dark variant with `--bg-deep` for contrast. Use `.rose-line` dividers, `.card-medspa` for treatment/service cards, `.label-medspa` for category labels, pill buttons for all CTAs.