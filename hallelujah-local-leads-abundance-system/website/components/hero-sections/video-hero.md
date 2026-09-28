# Video Hero
> Full-screen brand-tinted stock video background with triple cinematic overlay

## Preview
- Live: https://driveby-demo.client.of.florianrolke.com

## What It Does
Injects an absolutely-positioned video element behind the hero section, with an SVG `feColorMatrix` filter that desaturates then re-tints the footage to match the client's brand color. Three overlay layers add depth: a flat dark wash, a radial vignette, and a faint scanline texture. Content floats above at `z-index: 1`.

## Code
```html
<!-- 1. Hidden SVG filter (inject at top of <body>) -->
<svg style="position:absolute;width:0;height:0;overflow:hidden;" aria-hidden="true">
  <defs>
    <filter id="brandTint" color-interpolation-filters="sRGB">
      <feColorMatrix type="saturate" values="0"/>
      <feColorMatrix type="matrix" values="0.04 0 0 0 0.96 0.14 0 0 0 0.86 0.06 0 0 0 0.94 0 0 0 1 0"/>
    </filter>
  </defs>
</svg>

<!-- 2. Video background (first child of hero section) -->
<div class="anim-video-bg" style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <video autoplay muted loop playsinline preload="auto"
         poster="https://images.pexels.com/photos/1561020/pexels-photo-1561020.jpeg?auto=compress&cs=tinysrgb&w=1920"
         style="width:100%;height:100%;object-fit:cover;filter:url(#brandTint);">
    <source src="https://videos.pexels.com/video-files/2169880/2169880-uhd_2560_1440_30fps.mp4" type="video/mp4">
  </video>
  <!-- Overlay 1: flat dark wash -->
  <div style="position:absolute;inset:0;background:rgba(0,0,0,0.55);"></div>
  <!-- Overlay 2: radial vignette -->
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.7) 100%);"></div>
  <!-- Overlay 3: scanline texture -->
  <div style="position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px);"></div>
</div>

<!-- 3. Hero content (must have position:relative; z-index:1) -->
<div style="position:relative; z-index:1;">
  <h1>Your Headline Here</h1>
  <p>Subheading text</p>
</div>
```

### SVG Brand Tint Matrix Formula

The `feColorMatrix` values are computed from the brand hex color using this pattern:

```
R channel: r/255  0  0  0  (1 - r/255)
G channel: g/255  0  0  0  (1 - g/255)
B channel: b/255  0  0  0  (1 - b/255)
A channel: 0      0  0  1  0
```

For example, `#09240F` produces:
```
0.04 0 0 0 0.96
0.14 0 0 0 0.86
0.06 0 0 0 0.94
0 0 0 1 0
```

### Video Library (Pexels, free to use)

| Category | URL |
|----------|-----|
| tech | `https://videos.pexels.com/video-files/3129671/3129671-uhd_2560_1440_25fps.mp4` |
| abstract | `https://videos.pexels.com/video-files/2169880/2169880-uhd_2560_1440_30fps.mp4` |
| nature | `https://videos.pexels.com/video-files/5529539/5529539-uhd_2560_1440_25fps.mp4` |
| city | `https://videos.pexels.com/video-files/3571264/3571264-uhd_2560_1440_30fps.mp4` |
| data | `https://videos.pexels.com/video-files/5474057/5474057-hd_1920_1080_30fps.mp4` |
| code | `https://videos.pexels.com/video-files/7710243/7710243-hd_1920_1080_30fps.mp4` |
| finance | `https://videos.pexels.com/video-files/3129671/3129671-uhd_2560_1440_25fps.mp4` |

## Dependencies
- No JS libraries required
- Hero section must have `position: relative; overflow: hidden`
- All hero content children need `position: relative; z-index: 1`

## When To Use
- **Industry fit:** Tech, SaaS, finance, agencies, consulting — any business wanting cinematic presence
- **Best for:** Dark-themed sites where the video adds energy without competing with text
- **Pairs well with:** scroll-reveal, HUD overlay, dot-rhombus canvas

## Injection Point
First child of the hero `<section>`, `<header>`, or first major `<div>` in `<body>`. The SVG filter goes at the top of `<body>`. The hero container needs `position: relative; overflow: hidden` set on it.

**Source:** `execution/animate_static_page.py` — `inject_video_hero()` + `inject_svg_filter()` + `hex_to_color_matrix()`
