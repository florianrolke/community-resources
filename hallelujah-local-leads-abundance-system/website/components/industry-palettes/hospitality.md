# Hospitality & Food
> Warm earth tones with artisan script accents -- experience, craft, and warmth

## Preview
- Live: https://dunkertons-demo.client.of.florianrolke.com

## What It Does
A warm, inviting palette for restaurants, hotels, wineries, craft breweries, and artisan food brands. Rich burgundy and copper tones signal craftsmanship, warm ivory backgrounds feel welcoming rather than corporate, and script-style headings add artisan character. Photography-forward with generous white space.

## Code
```html
<!-- Hospitality & Food Palette - CSS Custom Properties -->
<style>
  :root {
    /* Core colors */
    --bg-deep: #1a1410;
    --bg-card: #23201a;
    --bg-elevated: #2c2820;
    --bg-warm: #faf5ef;
    --accent: #8b3a3a;
    --accent-hover: #a04545;
    --copper: #b87333;
    --copper-muted: rgba(184, 115, 51, 0.15);
    --text: #3d3028;
    --text-light: #f5efe8;
    --text-muted: #8a7e72;
    --text-heading: #2c2018;
    --border: rgba(139, 58, 58, 0.15);
    --border-copper: rgba(184, 115, 51, 0.25);

    /* Typography */
    --font-heading: 'Playfair Display', 'Georgia', serif;
    --font-body: 'Source Sans 3', 'Helvetica Neue', sans-serif;
    --font-accent: 'Cormorant Garamond', 'Georgia', serif;
    --heading-weight: 400;
    --heading-weight-bold: 700;
    --body-weight: 300;
    --body-weight-medium: 400;

    /* Photo overlay */
    --overlay-opacity: 0.45;
  }

  /* Base styles */
  body {
    background: var(--bg-warm);
    color: var(--text);
    font-family: var(--font-body);
    font-weight: var(--body-weight);
    line-height: 1.75;
  }

  h1, h2, h3 {
    font-family: var(--font-heading);
    font-weight: var(--heading-weight);
    color: var(--text-heading);
    letter-spacing: -0.01em;
  }

  h1 { font-size: clamp(2.5rem, 5.5vw, 5rem); line-height: 1.1; }
  h2 { font-size: clamp(1.8rem, 3.5vw, 3rem); line-height: 1.2; }
  h3 { font-size: clamp(1.2rem, 2vw, 1.5rem); font-weight: var(--heading-weight-bold); }

  /* Copper accent line */
  .copper-line {
    width: 60px;
    height: 1px;
    background: linear-gradient(90deg, var(--copper), transparent);
    margin: 1.5rem 0;
  }

  /* Card with warm hover */
  .card-hospitality {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.06);
    border-radius: 8px;
    padding: 2rem;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
  }
  .card-hospitality:hover {
    border-color: var(--copper);
    box-shadow: 0 12px 40px rgba(184, 115, 51, 0.08);
  }

  /* CTA Button */
  .btn-hospitality {
    background: var(--accent);
    color: #ffffff;
    padding: 14px 36px;
    border: none;
    border-radius: 4px;
    font-family: var(--font-body);
    font-weight: 500;
    font-size: 0.85rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    cursor: pointer;
    transition: background 0.3s ease, transform 0.2s ease;
  }
  .btn-hospitality:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
  }

  /* Italic accent for serif flair */
  .serif-accent {
    font-family: var(--font-accent);
    font-style: italic;
    color: var(--accent);
    font-size: 1.1em;
  }
</style>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Source+Sans+3:wght@300;400;500&family=Cormorant+Garamond:ital,wght@1,400&display=swap" rel="stylesheet">

<!-- Example Hero (centered, image-forward) -->
<section style="position:relative;min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;overflow:hidden;">
  <div style="position:absolute;inset:0;z-index:0;">
    <img src="artisan-food-hero.jpg" alt="" style="width:100%;height:100%;object-fit:cover;">
    <div style="position:absolute;inset:0;background:linear-gradient(to bottom, rgba(26,20,16,0.65) 0%, rgba(26,20,16,0.45) 100%);"></div>
  </div>
  <div style="position:relative;z-index:1;max-width:700px;padding:4rem 6%;">
    <p style="font-family:var(--font-accent);font-style:italic;color:var(--copper);font-size:1.1rem;margin-bottom:1rem;">Est. 1988</p>
    <h1 style="color:var(--text-light);">Craft & Character</h1>
    <p style="color:rgba(245,239,232,0.7);font-size:1.15rem;margin:1.5rem 0 2rem;">
      Farm-to-table excellence in the heart of the countryside.
    </p>
    <button class="btn-hospitality">Reserve a Table</button>
  </div>
</section>
```

## Dependencies
- Google Fonts: Playfair Display (400, 700) + Source Sans 3 (300, 400, 500) + Cormorant Garamond (italic 400)

## When To Use
- **Industry fit**: Restaurants, hotels, wineries, craft breweries, bakeries, catering, farm-to-table
- **Best for**: Sites that need warmth, artisan character, and photography-forward layouts
- **Pairs well with**: image-hero-kenburns, scroll-reveal, wave-svg, environmental-bleed, marquee-ticker

## Injection Point
Apply CSS custom properties to `:root`. This palette supports both dark sections (hero with `--bg-deep` overlay) and light sections (warm ivory `--bg-warm` background). Use `.copper-line` dividers, `.card-hospitality` for menu/feature cards, `.serif-accent` for elegant italic callouts.