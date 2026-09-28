# Website Redesign Engine

> Turn any prospect's website into a luxury redesign with cinematic animations — deployed to a live preview URL in minutes.

## Architecture

```
URL ──→ [capture] ──→ [analyze] ──→ [generate] ──→ [animate] ──→ [deploy]
         Firecrawl      Scoring       Claude        Effects      GitHub/Local
         HTML+Brand     10 categories  Component     Video hero   Live preview
         Screenshot     Gap analysis   library       Scroll FX    URL
```

## Quick Start

```bash
# 1. Full pipeline — URL to live preview
python website/full_pipeline.py --url "https://example.com" --slug example-corp --effect video-hero

# 2. With specific industry + animation style
python website/full_pipeline.py --url "https://example.com" --slug example-corp \
    --industry finance --effect cinematic-full --deploy github

# 3. Step by step
python website/capture_site.py --url "https://example.com" --slug example-corp
python website/analyze_site.py --html .tmp/captures/example-corp/page.html
python website/generate_redesign.py --slug example-corp --industry finance --style delta-vega
python website/animate_page.py --input .tmp/redesigns/example-corp-redesign.html \
    --effect cinematic-full --brand-color "#09240F" --output final.html
python website/deploy_site.py --slug example-corp --html final.html --method local
```

## Scripts

| Script | Purpose | API Keys Needed |
|--------|---------|----------------|
| `capture_site.py` | Firecrawl scrape → HTML + screenshot + branding | `FIRECRAWL_API_KEY` |
| `analyze_site.py` | Score design quality (10 categories), identify gaps | None |
| `generate_redesign.py` | Claude API redesign with component library | `ANTHROPIC_API_KEY` |
| `animate_page.py` | Inject cinematic animations (7 effects) | None |
| `deploy_site.py` | Deploy to GitHub Pages or local server | `GITHUB_TOKEN` (optional) |
| `full_pipeline.py` | End-to-end orchestrator | All above |

## Component Library (46 components)

The `components/` folder contains 46 copy-paste-ready HTML/CSS/JS building blocks organized into 10 categories. See `components/CATALOG.md` for the full inventory.

### Categories

| Category | Count | Examples |
|----------|-------|---------|
| Animations | 8 | scroll-reveal, counter-stats, marquee-ticker, preloader-curtain |
| Hero Sections | 5 | video-hero, image-hero-kenburns, parallax-depth-layers, cinematic-full |
| Typography | 5 | gradient-text, metallic-shimmer, outlined-stroke, video-filled-text |
| Cards & Panels | 5 | glassmorphism, hover-lift, bento-grid, numbered-feature |
| Buttons & CTAs | 4 | pill-glow, ghost-outline, magnetic-cursor, arrow-expand |
| Dividers & BG | 6 | gold-gradient-line, wave-svg, film-grain, scanlines |
| Navigation | 2 | sticky-blur-nav, custom-crosshair-cursor |
| Canvas Effects | 3 | dot-rhombus, dot-arrow, particle-torus |
| 3D Elements | 3 | glass-orb, wireframe-terrain, morphing-blob |
| Industry Palettes | 6 | finance-law, real-estate, tech-saas, construction, hospitality, medspa |

### Component Selection by Goal

| Goal | Components |
|------|-----------|
| Maximum wow factor | cinematic-full + metallic-shimmer + preloader-curtain + particle-torus |
| Clean & professional | scroll-reveal + sticky-blur-nav + hover-lift + gold-gradient-line |
| Editorial luxury | parallax-depth-layers + character-reveal + marquee-ticker + geometric-frame |
| Tech/modern | dot-rhombus + gradient-text + glassmorphism + cursor-spotlight |
| Warm/artisan | image-hero-kenburns + wave-svg + environmental-bleed + scroll-reveal |

## Inspiration Recipes (6 reference designs)

The `inspirations/` folder has 6 fully decomposed reference sites. Each lists the exact components used. See `inspirations/INDEX.md`.

| Inspiration | Industry | Mood | Key Components |
|-------------|----------|------|---------------|
| Populon AI | Tech/AI | Cyberpunk HUD | video-hero, crosshair-cursor, scanlines, film-grain, preloader, dot-rhombus |
| Dunkertons | Hospitality | Artisan warmth | image-hero-kenburns, scroll-reveal, wave-svg, environmental-bleed |
| DriveBy | Tech/SaaS | Bold indigo | video-hero, dot-rhombus, marquee-ticker, particle-torus, glassmorphism |
| Delta Vega | Finance | Refined authority | glassmorphism, gradient-text, gold-gradient-line, sticky-blur-nav |
| TeamSIOK | Construction | Bold & reliable | scroll-reveal, hover-lift, pill-glow, counter-stats, diagonal-clip |
| EZ Homes | Real Estate | Aspirational gold | bento-grid, numbered-feature, metallic-shimmer, ghost-outline |

**Usage:** `--style delta-vega` in generate_redesign.py loads that recipe's component list.

## Animation Effects

The `animate_page.py` script injects these effects into any HTML:

| Effect | What It Does | Dependencies |
|--------|-------------|-------------|
| `video-hero` | Full-screen brand-tinted stock video behind hero | None |
| `image-hero` | Ken Burns animated hero with client's own image | None |
| `scroll-reveals` | Fade-in-up on all sections (IntersectionObserver) | None |
| `dot-rhombus` | Canvas 2D shimmering diamond dot-grid | None |
| `particle-torus` | Three.js rotating particle torus knot | Three.js CDN |
| `cinematic-full` | All of the above (maximum wow factor) | Three.js CDN |

### Brand Tinting

Video heroes are brand-tinted using SVG feColorMatrix. The hex color is converted to a monotone filter matrix that shifts the stock video to match the brand palette. Formula:

```
R channel: r_normalized  0  0  0  (1 - r_normalized)
G channel: g_normalized  0  0  0  (1 - g_normalized)
B channel: b_normalized  0  0  0  (1 - b_normalized)
Alpha:     0  0  0  1  0
```

### Video Library

7 free Pexels stock videos categorized by industry:
- **tech** — circuit board / data streams
- **abstract** — flowing particles
- **nature** — forest / organic
- **city** — aerial urban
- **data** — visualization
- **code** — terminal / IDE
- **finance** — same as tech (markets)

Auto-selected based on slug keywords or `--video-category` override.

## Industry Palettes

Each palette defines CSS custom properties for the entire design:

```css
:root {
    --accent: #c4842a;        /* Primary accent */
    --accent-rgb: 196,132,42; /* For rgba() usage */
    --text: #f5f0eb;          /* Body text */
    --bg-deep: #0f1410;       /* Background */
    --font-heading: 'Playfair Display', serif;
    --font-body: 'Source Sans Pro', sans-serif;
}
```

| Palette | Accent | Heading Font | Mood |
|---------|--------|-------------|------|
| finance-law | Gold #c4842a | Playfair Display | Quiet authority |
| real-estate | Warm gold #c4842a | Playfair Display | Aspirational |
| tech-saas | Electric indigo #6366f1 | Inter | Modern, clean |
| construction | Safety orange #f97316 | Oswald | Bold, reliable |
| hospitality | Warm amber #d4a853 | Cormorant Garamond | Artisan warmth |
| medspa | Rose gold #c9a87c | Cormorant Garamond | Refined luxury |

## Design Analysis Scoring

`analyze_site.py` scores across 10 categories (0-10 each):

| Category | How It's Scored |
|----------|----------------|
| Visual Hierarchy | Heading count + variety, penalize missing H1 |
| Layout | Section count × 2.5, capped at 10 |
| CTA | Button count × 3, capped at 10 |
| Typography | Font count sweet spot (2 fonts = 8/10), penalize inverted sizes |
| Color | Unique non-B/W colors |
| Social Proof | 8 if testimonials found, else 2 |
| Content Quality | Word count thresholds (200+ = 7, 50+ = 5) |
| Modern Features | Animations, viewport meta, forms |
| Imagery | Image count thresholds (5+ = 7, 2+ = 5) |
| Overall | Average of all above |

## API Budget

| Step | API | Cost per Site |
|------|-----|--------------|
| Capture | Firecrawl | 1 credit (~$0.01) |
| Analyze | None | Free |
| Generate | Claude Sonnet | ~$0.02-0.05 (8K tokens out) |
| Animate | None | Free (all client-side JS) |
| Deploy | GitHub | Free |
| **Total** | | **~$0.03-0.06 per site** |

## Gotchas

1. **Firecrawl v2**: Use `"formats": ["html", "screenshot"]` — do NOT pass `"screenshot": {"fullPage": false}`
2. **Claude HTML generation**: Always force standalone HTML + Tailwind CDN in the prompt, or Claude defaults to React/JSX
3. **Three.js CDN**: particle-torus requires Three.js r128 — loaded from cdnjs, no npm needed
4. **Ken Burns**: 25s infinite alternate animation — test on mobile (can cause jank on low-end devices)
5. **SVG feColorMatrix**: The brand tint filter must be injected BEFORE the video element that references it
6. **Page builder detection**: Sites built with Elementor/Divi/Brizy have deeply nested DOM — find_hero() uses 4 fallback strategies
7. **Windows encoding**: All scripts use `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`
8. **Component zero-dependency**: 38/46 components use pure CSS/JS — no build tools, no npm install

## Production Stats

- **12+ live deployed redesigns** across finance, construction, real estate, hospitality
- **46 components** battle-tested on Cloudflare Workers
- **6 industry palettes** validated with real clients
- **$0.03-0.06 cost per complete redesign** (capture → deploy)
