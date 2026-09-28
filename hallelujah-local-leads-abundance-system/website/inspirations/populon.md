# Populon AI
> Cyberpunk HUD terminal aesthetic — maximum visual density with scan lines, film grain, and crosshair cursor

## Live URL
- https://populon-demo.client.of.florianrolke.com

## Industry Palette
- **Industry:** Tech/AI
- **Palette:** `tech-saas`

## Component Recipe

| # | Component | Section | Notes |
|---|-----------|---------|-------|
| 1 | `preloader-curtain` | Page load | Curtain split animation with percentage counter |
| 2 | `sticky-blur-nav` | Global | Transparent → solid on scroll |
| 3 | `video-hero` | Hero | Full-bleed Pexels stock, SVG feColorMatrix brand tint, triple overlay |
| 4 | `custom-crosshair-cursor` | Global | Red dot + directional lines + trail circles |
| 5 | `monospace-labels` | Hero + throughout | JetBrains Mono HUD corner labels: "SYSTEM ONLINE", "Status: ACTIVE" |
| 6 | `scanlines` | Hero | repeating-linear-gradient 2px overlay |
| 7 | `film-grain` | Hero | SVG feTurbulence fractalNoise, opacity 0.03 |
| 8 | `scroll-reveal` | All sections | fade-in-up with stagger |
| 9 | `dot-rhombus` | Services | Canvas 2D diamond dot grid background |
| 10 | `marquee-ticker` | Between hero and services | Continuous horizontal text scroll |
| 11 | `counter-stats` | Stats section | Animated number count-up |
| 12 | `ghost-outline` | CTAs | Transparent border CTA buttons |

## Page Structure (top to bottom)

1. **Preloader** — `preloader-curtain` (curtain split + percentage counter)
2. **Navigation** — `sticky-blur-nav`
3. **Video Hero** — `video-hero` + `custom-crosshair-cursor` + `monospace-labels` + `scanlines` + `film-grain`
4. **Marquee Strip** — `marquee-ticker`
5. **Services** — `dot-rhombus` background + `scroll-reveal` cards
6. **Stats** — `counter-stats`
7. **About** — `scroll-reveal`
8. **CTA** — `ghost-outline` buttons
9. **Footer**

## Reproduction Prompt

> Build a cyberpunk-themed single-page site for [CLIENT]. Use a preloader-curtain with percentage counter on load. Sticky blur nav that transitions from transparent to solid. Full-bleed video hero with SVG feColorMatrix brand tint, scanlines overlay (repeating-linear-gradient 2px), and film-grain (SVG feTurbulence at 0.03 opacity). Add a custom crosshair cursor with red dot, directional lines, and trailing circles. Place monospace HUD labels (JetBrains Mono) in hero corners. Below hero, add a marquee-ticker strip. Services section needs a dot-rhombus Canvas 2D diamond grid background with scroll-reveal cards. Include a counter-stats section with animated numbers. Use ghost-outline transparent-border CTAs throughout. Palette: tech-saas. Mood: dark, dense, terminal-like.

## What Makes This One Special

- **Maximum visual density** — combines more components than any other inspiration (12 distinct effects layered together)
- **HUD/terminal aesthetic** — monospace labels, scanlines, film grain, and crosshair cursor create a sci-fi command center feel that no other inspiration attempts
- **Preloader as a feature** — the curtain-split loading animation sets the tone before the page even appears, making the experience feel like booting up a system