# Glassmorphism Card
> Frosted-glass panels with blurred translucent backgrounds and subtle luminous borders

## Preview
- Live: https://delta-vega-luxury.preview.florianrolke.com

## What It Does
Creates frosted-glass card panels that float above dark backgrounds with a soft blur effect. The translucent surface reveals a hint of the content beneath while the luminous border adds depth. On hover, the border brightens to draw attention without breaking the ambient feel.

## Code
```html
<div class="glass-card-grid">
  <div class="glass-card">
    <div class="glass-card-icon">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
      </svg>
    </div>
    <h3 class="glass-card-title">Service Title</h3>
    <p class="glass-card-desc">Brief description of the service or feature goes here. Keep it to two lines maximum.</p>
  </div>

  <div class="glass-card">
    <div class="glass-card-icon">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/>
      </svg>
    </div>
    <h3 class="glass-card-title">Another Service</h3>
    <p class="glass-card-desc">Brief description of the service or feature goes here. Keep it to two lines maximum.</p>
  </div>

  <div class="glass-card">
    <div class="glass-card-icon">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
      </svg>
    </div>
    <h3 class="glass-card-title">Third Service</h3>
    <p class="glass-card-desc">Brief description of the service or feature goes here. Keep it to two lines maximum.</p>
  </div>
</div>

<style>
.glass-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
  padding: 2rem;
}

.glass-card {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 2.5rem 2rem;
  transition: border-color 0.4s ease, box-shadow 0.4s ease;
}

.glass-card:hover {
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.glass-card-icon {
  color: var(--accent, #C9A96E);
  margin-bottom: 1.5rem;
  opacity: 0.85;
}

.glass-card-title {
  font-family: var(--font-heading, 'Cormorant Garamond', serif);
  font-size: 1.35rem;
  font-weight: 500;
  color: #ffffff;
  margin: 0 0 0.75rem 0;
  letter-spacing: 0.02em;
}

.glass-card-desc {
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.95rem;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}
</style>
```

## Dependencies
- Dark background behind the cards (dark section or dark page)
- CSS custom properties `--accent` for icon color (falls back to gold)
- Optional: `--font-heading` and `--font-body` custom properties

## When To Use
- **Industry fit**: Finance, luxury, tech, SaaS, professional services
- **Best for**: Service cards, feature panels, pricing tiers on dark backgrounds
- **Pairs well with**: gold-gradient-line divider, film-grain overlay, ghost-outline buttons

## Injection Point
Inside a dark `<section>` element, typically the services or features section. Place the grid as a direct child of the section's container div.
