# Finance & Law
> Deep navy with regal purple accents and gold trust signals -- authority meets sophistication

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
A premium dark palette designed for financial advisors, law firms, wealth managers, and accounting practices. The deep navy background conveys institutional trust, purple accents add modern sophistication, and gold touches signal premium positioning. Typography pairs thin serif headings with clean sans-serif body text.

## Code
```html
<!-- Finance & Law Palette - CSS Custom Properties -->
<style>
  :root {
    /* Core colors */
    --bg-deep: #0a0f1a;
    --bg-card: #111827;
    --bg-elevated: #1a2236;
    --accent: #7456f1;
    --accent-hover: #8b6ff5;
    --gold: #d4af37;
    --gold-muted: rgba(212, 175, 55, 0.15);
    --text: #E7EBEE;
    --text-muted: #9ca3af;
    --text-heading: #ffffff;
    --border: rgba(116, 86, 241, 0.15);
    --border-gold: rgba(212, 175, 55, 0.25);

    /* Typography */
    --font-heading: 'Cormorant Garamond', 'Georgia', serif;
    --font-body: 'Inter', 'Helvetica Neue', sans-serif;
    --heading-weight: 300;
    --heading-weight-bold: 400;
    --body-weight: 300;
    --body-weight-medium: 400;

    /* Photo overlay */
    --overlay-opacity: 0.55;
  }

  /* Base styles */
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
    letter-spacing: 0.02em;
  }

  h1 { font-size: clamp(2.5rem, 5vw, 4.5rem); line-height: 1.1; }
  h2 { font-size: clamp(1.8rem, 3.5vw, 3rem); line-height: 1.2; }
  h3 { font-size: clamp(1.2rem, 2vw, 1.5rem); font-weight: var(--heading-weight-bold); }

  /* Gold accent line */
  .gold-line {
    width: 60px;
    height: 1px;
    background: linear-gradient(90deg, var(--gold), transparent);
    margin: 1.5rem 0;
  }

  /* Card with purple border glow */
  .card-finance {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2rem;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
  }
  .card-finance:hover {
    border-color: var(--accent);
    box-shadow: 0 0 30px rgba(116, 86, 241, 0.1);
  }

  /* CTA Button */
  .btn-finance {
    background: var(--accent);
    color: #ffffff;
    padding: 14px 32px;
    border: none;
    border-radius: 8px;
    font-family: var(--font-body);
    font-weight: 500;
    font-size: 0.95rem;
    letter-spacing: 0.03em;
    cursor: pointer;
    transition: background 0.3s ease, transform 0.2s ease;
  }
  .btn-finance:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
  }
</style>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">

<!-- Example Hero Layout (left-aligned, city skyline golden hour) -->
<section style="position:relative;min-height:100vh;display:flex;align-items:center;overflow:hidden;">
  <!-- Background photo with overlay -->
  <div style="position:absolute;inset:0;z-index:0;">
    <img src="city-skyline-golden-hour.jpg" alt="" style="width:100%;height:100%;object-fit:cover;">
    <div style="position:absolute;inset:0;background:linear-gradient(135deg, rgba(10,15,26,0.85) 0%, rgba(10,15,26,0.55) 100%);"></div>
  </div>
  <!-- Content (left-aligned) -->
  <div style="position:relative;z-index:1;max-width:640px;padding:4rem 6%;">
    <div class="gold-line"></div>
    <h1>Strategic Wealth<br>Management</h1>
    <p style="color:var(--text-muted);font-size:1.15rem;margin:1.5rem 0 2rem;">
      Protecting and growing your legacy with institutional-grade strategies.
    </p>
    <button class="btn-finance">Schedule Consultation</button>
  </div>
</section>
```

## Dependencies
- Google Fonts: Cormorant Garamond (300, 400, 600) + Inter (300, 400, 500)

## When To Use
- **Industry fit**: Financial advisors, law firms, wealth managers, CPAs, insurance
- **Best for**: Sites that need to project trust, authority, and premium positioning
- **Pairs well with**: metallic-shimmer, geometric-frame, horizontal-scroll-gallery, counter-stats, marquee-ticker, parallax-depth-layers

## Injection Point
Apply the CSS custom properties to `:root` at the top of the stylesheet. The palette governs the entire page. Use `.gold-line` dividers between sections, `.card-finance` for service/feature cards, and `.btn-finance` for all CTAs.
