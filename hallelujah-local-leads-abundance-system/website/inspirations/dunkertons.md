# Dunkertons Cider
> Artisan warmth, countryside craft — photography-forward with elegant simplicity

## Live URL
- https://dunkertons-demo.client.of.florianrolke.com

## Industry Palette
- **Industry:** Hospitality/Food
- **Palette:** `hospitality`

## Component Recipe

| # | Component | Section | Notes |
|---|-----------|---------|-------|
| 1 | `sticky-blur-nav` | Global | Transparent → solid on scroll |
| 2 | `image-hero-kenburns` | Hero | Client's own product photo, 25s Ken Burns loop |
| 3 | `scroll-reveal` | All sections | Sections fade in on scroll |
| 4 | `monospace-labels` | Throughout | Category labels above headings |
| 5 | `wave-svg` | Section dividers | Organic wave shapes between content blocks |
| 6 | `environmental-bleed` | Background | Faded orchard photo at 0.04 opacity as watermark |
| 7 | `hover-lift` | Products | Product/feature cards with translateY + shadow |
| 8 | `gold-gradient-line` | Dividers | Thin copper accent dividers between sections |
| 9 | `pill-glow` | CTAs | Warm CTA buttons with glow effect |

## Page Structure (top to bottom)

1. **Navigation** — `sticky-blur-nav`
2. **Ken Burns Hero** — `image-hero-kenburns` (product photo, 25s loop)
3. **Wave Divider** — `wave-svg`
4. **Products** — `hover-lift` cards with `scroll-reveal`
5. **Environmental Bleed Background** — `environmental-bleed` (faded orchard photo)
6. **Story Section** — `monospace-labels` + `scroll-reveal` + `gold-gradient-line` accents
7. **Wave Divider** — `wave-svg`
8. **CTA** — `pill-glow` buttons
9. **Footer**

## Reproduction Prompt

> Build a warm, photography-forward single-page site for [CLIENT]. Sticky blur nav. Hero section uses image-hero-kenburns with the client's own product/venue photo on a 25-second Ken Burns loop. Separate sections with wave-svg organic dividers. Products/services displayed as hover-lift cards that rise on hover. Add an environmental-bleed background layer — a faded photo of their environment at 0.04 opacity as a watermark. Use monospace-labels for category text above headings. Thin gold-gradient-line copper accent dividers. CTAs are pill-glow with warm tones. All sections use scroll-reveal fade-in. Palette: hospitality. Mood: artisan, warm, craft. No heavy JS effects — let the photography and spacing do the work.

## What Makes This One Special

- **Photography-forward** — the Ken Burns hero and environmental bleed let the client's actual imagery tell the story, making it feel authentic rather than templated
- **Elegant simplicity** — only 9 components with no heavy JS effects (no Canvas, no Three.js, no particles), proving that warmth and spacing alone can create a premium feel
- **Organic dividers** — wave-svg sections create a soft, flowing visual rhythm that matches the countryside/artisan brand perfectly