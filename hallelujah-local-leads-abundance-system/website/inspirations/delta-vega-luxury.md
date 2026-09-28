# Delta Vega Luxury
> Refined institutional authority, Bloomberg meets Cartier — pure typography and spacing mastery

## Live URL
- https://delta-vega-luxury.preview.florianrolke.com

## Industry Palette
- **Industry:** Finance
- **Palette:** `finance-law`

## Component Recipe

| # | Component | Section | Notes |
|---|-----------|---------|-------|
| 1 | `sticky-blur-nav` | Global | backdrop-filter, transparent → solid on scroll |
| 2 | `scroll-reveal` | All sections | fade-in-up with rd1-rd5 stagger delay classes |
| 3 | `glassmorphism` | Service cards | rgba(0,0,0,0.3-0.5) + blur(20-30px) |
| 4 | `gradient-text` | Hero headline | White → gold gradient |
| 5 | `outlined-stroke` | Display text | -webkit-text-stroke for large decorative text |
| 6 | `monospace-labels` | Throughout | Gold uppercase category labels |
| 7 | `gold-gradient-line` | Dividers | transparent → gold → transparent thin dividers |
| 8 | `sticky-card-stack` | Services | Cards stacked on scroll with z-index |
| 9 | `numbered-feature` | Service areas | Large serif numbers for each service |
| 10 | `ghost-outline` | CTAs | Transparent border CTA buttons |
| 11 | `arrow-expand` | Links | Arrow slides right on hover |
| 12 | `hover-lift` | Cards | translateY + shadow on hover |

## Page Structure (top to bottom)

1. **Navigation** — `sticky-blur-nav`
2. **Hero** — Dark green overlay + left-aligned serif heading with `gradient-text` (white → gold)
3. **Gold Line Divider** — `gold-gradient-line`
4. **Services** — `sticky-card-stack` with `glassmorphism` cards + `arrow-expand` links
5. **About** — Two-column layout with `outlined-stroke` display text + `scroll-reveal`
6. **Numbered Features** — `numbered-feature` (large serif numbers) + `monospace-labels`
7. **CTA** — `ghost-outline` buttons + `hover-lift`
8. **Footer**

## Reproduction Prompt

> Build a refined, editorial single-page site for [CLIENT]. Sticky blur nav with backdrop-filter. Hero has a dark overlay with left-aligned serif heading using gradient-text (white → gold). Separate sections with gold-gradient-line dividers (transparent → gold → transparent). Services presented as sticky-card-stack — cards that stack on scroll with increasing z-index, each using glassmorphism (rgba dark + 20-30px blur). Links use arrow-expand (arrow slides right on hover). Include a numbered-feature section with large serif numbers ("01", "02") for each service area. Gold monospace-labels for category text throughout. Outlined-stroke large display text in the about section. All sections scroll-reveal with rd1-rd5 stagger delays. CTAs are ghost-outline with hover-lift. Palette: finance-law. Mood: quiet luxury, institutional authority, editorial. NO heavy effects — rely entirely on typography, spacing, and subtle transitions.

## What Makes This One Special

- **Quiet luxury approach** — no Canvas, no Three.js, no video, no particles. Achieves premium feel through typography hierarchy, generous whitespace, and gold accents alone
- **Sticky-card-stack interaction** — the services section uses scroll-driven stacking that creates a satisfying, tactile browsing experience without feeling gimmicky
- **Most refined/editorial** of all inspirations — the combination of serif type, outlined-stroke display text, and gold-gradient-line dividers creates a look that would be at home on a Bloomberg terminal or Cartier product page