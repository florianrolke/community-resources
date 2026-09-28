# Cinematic Full
> Maximum-impact composition layering video/image hero + scroll reveals + HUD overlay + dot-rhombus canvas

## Preview
- Live: https://populon-demo.client.of.florianrolke.com

## What It Does
This is not a single component but a composition recipe — the "populon.ai treatment" that combines four individual effects into one cinematic page. It layers a full-screen video (or Ken Burns image) hero, fade-in-up scroll reveals on all sections, JetBrains Mono HUD corner labels, and a shimmering diamond dot-grid canvas. The result is a high-impact, tech-forward presentation suitable for the most impressive demos.

## Code

This is a composition of individual components. Apply them in this order:

### Step 1: Video Hero OR Image Hero (choose one)

If the client has strong hero imagery, use `image-hero-kenburns.md`. Otherwise, use `video-hero.md` with an appropriate stock category.

See: `components/hero-sections/video-hero.md` or `components/hero-sections/image-hero-kenburns.md`

### Step 2: HUD Overlay

Inject inside the hero section, after the video/image background:

```html
<!-- JetBrains Mono font (inject in <head>) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400&display=swap">

<!-- HUD corner elements (append inside hero section) -->
<div style="position:absolute;top:16px;left:16px;z-index:50;font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:0.25em;color:rgba(255,255,255,0.4);">
  <div>SYSTEM ONLINE</div>
</div>
<div style="position:absolute;top:16px;right:16px;z-index:50;font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:0.25em;color:rgba(255,255,255,0.4);text-align:right;">
  <div>Status: <span style="color:#22c55e;">ACTIVE</span></div>
</div>
<div style="position:absolute;bottom:16px;right:16px;z-index:50;display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
  <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:0.25em;color:rgba(255,255,255,0.3);">[SCROLL]</span>
  <div style="width:1px;height:32px;background:linear-gradient(to bottom, rgba(255,255,255,0.4), transparent);animation:pulse 2s infinite;"></div>
</div>
```

### Step 3: Scroll Reveals

```html
<!-- CSS (inject in <head>) -->
<style>
.anim-fade-in-up {
  opacity: 0;
  transform: translateY(25px);
  transition: opacity 0.8s ease, transform 0.8s ease;
}
.anim-fade-in-up.anim-visible {
  opacity: 1;
  transform: translateY(0);
}
</style>

<!-- JS (inject before </body>) -->
<script>
(function(){
  var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting) e.target.classList.add('anim-visible');
    });
  }, {threshold: 0.1});
  document.querySelectorAll('.anim-fade-in-up').forEach(function(el){ obs.observe(el); });
})();
</script>
```

Add class `anim-fade-in-up` to each direct child of every `<section>`. Stagger with `transition-delay: 0.1s`, `0.2s`, etc.

### Step 4: Dot-Rhombus Canvas

Inject a `<canvas>` into the second section (or any section below the hero) with the shimmering diamond dot-grid animation. See `execution/animate_static_page.py` `inject_dot_canvas(soup, shape='rhombus')` for the full Canvas 2D script.

```html
<canvas id="anim-dots-rhombus" style="position:absolute;inset:0;z-index:0;pointer-events:none;opacity:0.15;"></canvas>
```

The JS creates dots in a rhombus mask (`Math.abs(relX) + Math.abs(relY) < rhombusSize`) and animates them with a sine wave for shimmering.

### Composition Checklist

| Layer | Component | File |
|-------|-----------|------|
| 1 | Video or Image hero | `video-hero.md` / `image-hero-kenburns.md` |
| 2 | HUD corner labels | Inline above |
| 3 | Scroll reveals (all sections) | Inline above |
| 4 | Dot-rhombus canvas (section 2+) | `animate_static_page.py` |

## Dependencies
- Google Fonts: JetBrains Mono (for HUD labels)
- No external JS libraries
- IntersectionObserver (scroll reveals)
- Canvas 2D API (dot-rhombus)

## When To Use
- **Industry fit:** Tech, AI, SaaS, cybersecurity — businesses wanting maximum "wow factor"
- **Best for:** First-impression demos where cinematic impact matters most (cold outreach, investor decks)
- **Pairs well with:** This IS the maximum composition — add gradient-text or metallic-shimmer on the headline for extra polish

## Injection Point
Applied across the entire page. Video/image hero goes in the first section. HUD labels append inside that hero. Scroll reveal classes go on all section children. Dot-rhombus canvas goes in the second section.

**Source:** `execution/animate_static_page.py` — `cinematic-full` effect branch (lines 604-611), `inject_hud_overlay()`
