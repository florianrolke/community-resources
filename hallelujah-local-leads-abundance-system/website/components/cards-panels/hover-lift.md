# Hover Lift Card
> Cards that float upward with an expanding shadow on hover, creating a tactile depth effect

## Preview
- Live: https://teamsiok-luxury.preview.florianrolke.com

## What It Does
Applies a smooth upward translation and deepening box-shadow when the user hovers over a card. The cubic-bezier easing creates a natural, spring-like motion that feels premium. Works on any card regardless of background color or content structure.

## Code
```html
<div class="lift-card-grid">
  <div class="lift-card">
    <div class="lift-card-img">
      <img src="https://placehold.co/400x250/1a1a1a/333?text=Service" alt="Service image" loading="lazy">
    </div>
    <div class="lift-card-body">
      <h3 class="lift-card-title">Service Title</h3>
      <p class="lift-card-desc">A concise description of the service offering and its key benefits for the client.</p>
      <a href="#" class="lift-card-link">Learn more <span>&rarr;</span></a>
    </div>
  </div>

  <div class="lift-card">
    <div class="lift-card-img">
      <img src="https://placehold.co/400x250/1a1a1a/333?text=Portfolio" alt="Portfolio image" loading="lazy">
    </div>
    <div class="lift-card-body">
      <h3 class="lift-card-title">Portfolio Item</h3>
      <p class="lift-card-desc">Showcase a completed project with a brief summary of results achieved.</p>
      <a href="#" class="lift-card-link">View project <span>&rarr;</span></a>
    </div>
  </div>

  <div class="lift-card">
    <div class="lift-card-img">
      <img src="https://placehold.co/400x250/1a1a1a/333?text=Feature" alt="Feature image" loading="lazy">
    </div>
    <div class="lift-card-body">
      <h3 class="lift-card-title">Key Feature</h3>
      <p class="lift-card-desc">Highlight a product feature or capability that differentiates from competitors.</p>
      <a href="#" class="lift-card-link">Explore <span>&rarr;</span></a>
    </div>
  </div>
</div>

<style>
.lift-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
  padding: 2rem;
}

.lift-card {
  background: var(--card-bg, #111111);
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.3s cubic-bezier(.25, .46, .45, .94),
              box-shadow 0.3s cubic-bezier(.25, .46, .45, .94);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.lift-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.lift-card-img {
  overflow: hidden;
  aspect-ratio: 16/10;
}

.lift-card-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.lift-card:hover .lift-card-img img {
  transform: scale(1.03);
}

.lift-card-body {
  padding: 1.75rem;
}

.lift-card-title {
  font-family: var(--font-heading, 'Inter', sans-serif);
  font-size: 1.2rem;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 0.75rem 0;
}

.lift-card-desc {
  font-size: 0.9rem;
  line-height: 1.65;
  color: rgba(255, 255, 255, 0.55);
  margin: 0 0 1.25rem 0;
}

.lift-card-link {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--accent, #C9A96E);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: gap 0.3s ease;
}

.lift-card-link:hover {
  gap: 14px;
}

.lift-card-link span {
  transition: transform 0.3s ease;
}

.lift-card-link:hover span {
  transform: translateX(2px);
}
</style>
```

## Dependencies
- CSS custom property `--card-bg` for card background (falls back to #111)
- CSS custom property `--accent` for link color (falls back to gold)
- Images or placeholder content for the card image area (optional, remove `.lift-card-img` for text-only cards)

## When To Use
- **Industry fit**: Universal -- works across all industries and styles
- **Best for**: Service grids, portfolio showcases, feature highlights, team member cards
- **Pairs well with**: bento-grid layout, arrow-expand links, pill-glow CTA buttons

## Injection Point
Inside any section with a card grid. Replace existing static cards with this pattern. The grid container handles responsive layout automatically.
