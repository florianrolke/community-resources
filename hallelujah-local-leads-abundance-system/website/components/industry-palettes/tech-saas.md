# Tech / SaaS
> Deep space navy with electric cyan accents -- futuristic, data-driven, abstract hero visuals

## Preview
- Live: https://driveby-demo.client.of.florianrolke.com

## What It Does
A forward-looking palette for technology companies, SaaS platforms, and AI startups. High overlay opacity (60-80%) allows abstract gradients and 3D elements to take center stage instead of photography. Centered hero layouts with bold sans-serif headings convey clarity and innovation. The cyan accent pops against dark backgrounds.

## Code
```html
<!-- Tech / SaaS Palette - CSS Custom Properties -->
<style>
  :root {
    /* Core colors */
    --bg-deep: #0a0f1a;
    --bg-card: #111827;
    --bg-elevated: #1e293b;
    --accent: #06b6d4;
    --accent-hover: #22d3ee;
    --accent-glow: rgba(6, 182, 212, 0.15);
    --gold: #c0c0c0;
    --text: #E7EBEE;
    --text-muted: #94a3b8;
    --text-heading: #ffffff;
    --border: rgba(6, 182, 212, 0.12);

    /* Typography */
    --font-heading: 'Inter', 'Overpass', 'Helvetica Neue', sans-serif;
    --font-body: 'Inter', 'Helvetica Neue', sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    --heading-weight: 600;
    --heading-weight-bold: 700;
    --body-weight: 400;

    /* Photo overlay - high, abstract backgrounds */
    --overlay-opacity: 0.70;
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

  h1 { font-size: clamp(2.5rem, 5vw, 4rem); line-height: 1.1; letter-spacing: -0.02em; }
  h2 { font-size: clamp(1.8rem, 3.5vw, 2.8rem); line-height: 1.2; }
  h3 { font-size: clamp(1.1rem, 1.8vw, 1.4rem); font-weight: var(--heading-weight-bold); }

  /* Gradient text accent */
  .gradient-text {
    background: linear-gradient(135deg, var(--accent), #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  /* Glassmorphism card */
  .card-glass {
    background: rgba(17, 24, 39, 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2rem;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
  }
  .card-glass:hover {
    border-color: var(--accent);
    box-shadow: 0 0 40px var(--accent-glow);
  }

  /* Code badge */
  .badge-code {
    display: inline-block;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 4px 10px;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--accent);
  }

  /* CTA Button */
  .btn-tech {
    background: var(--accent);
    color: #0a0f1a;
    padding: 14px 32px;
    border: none;
    border-radius: 8px;
    font-family: var(--font-body);
    font-weight: 600;
    font-size: 0.95rem;
    cursor: pointer;
    transition: background 0.3s ease, box-shadow 0.3s ease;
  }
  .btn-tech:hover {
    background: var(--accent-hover);
    box-shadow: 0 0 24px var(--accent-glow);
  }

  /* Ghost button variant */
  .btn-tech-ghost {
    background: transparent;
    color: var(--accent);
    padding: 14px 32px;
    border: 1px solid var(--accent);
    border-radius: 8px;
    font-family: var(--font-body);
    font-weight: 500;
    font-size: 0.95rem;
    cursor: pointer;
    transition: background 0.3s ease;
  }
  .btn-tech-ghost:hover {
    background: var(--accent-glow);
  }
</style>

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<!-- Example Hero (centered, abstract gradient background) -->
<section style="position:relative;min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;overflow:hidden;">
  <!-- Abstract gradient background -->
  <div style="position:absolute;inset:0;z-index:0;background:radial-gradient(ellipse at 30% 20%, rgba(6,182,212,0.12) 0%, transparent 60%),radial-gradient(ellipse at 70% 80%, rgba(167,139,250,0.08) 0%, transparent 50%),var(--bg-deep);"></div>
  <!-- Centered content -->
  <div style="position:relative;z-index:1;max-width:700px;padding:4rem 6%;">
    <span class="badge-code">v2.0 Released</span>
    <h1 style="margin-top:1.5rem;">Build <span class="gradient-text">Faster</span> With AI-Powered Tools</h1>
    <p style="color:var(--text-muted);font-size:1.15rem;margin:1.5rem 0 2rem;">
      Ship production-ready code in minutes, not months. Trusted by 2,000+ teams.
    </p>
    <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;">
      <button class="btn-tech">Get Started Free</button>
      <button class="btn-tech-ghost">View Demo</button>
    </div>
  </div>
</section>
```

## Dependencies
- Google Fonts: Inter (400, 500, 600, 700)

## When To Use
- **Industry fit**: SaaS, AI/ML, dev tools, fintech, data platforms, cybersecurity
- **Best for**: Product-led sites with abstract visuals, not photo-heavy
- **Pairs well with**: particle-torus, gradient-text, dot-rhombus, glassmorphism cards, scroll-progress-bar

## Injection Point
Apply CSS custom properties to `:root`. Use the radial gradient background pattern for hero sections instead of photography. The centered layout with `.gradient-text` heading and dual CTAs (solid + ghost) is the standard tech hero pattern.
