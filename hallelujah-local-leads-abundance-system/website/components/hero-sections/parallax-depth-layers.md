# Parallax Depth Layers
> Three stacked layers that scroll at different speeds creating dimensional depth in the hero

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
Creates a 3D depth illusion by splitting the hero into three absolutely-positioned layers, each scrolling at a different rate. The background layer (decorative shapes/circles) moves slowest, the mid layer (SVG curves or accent lines) moves at medium speed, and the foreground (text content) moves at full scroll speed. A vanilla JS scroll listener applies `translateY` offsets based on each layer's `data-speed` attribute.

## Code
```html
<!-- Hero section with parallax layers -->
<section class="parallax-hero" style="position:relative;overflow:hidden;min-height:100vh;">

  <!-- Layer 1: Background — decorative shapes (slowest) -->
  <div class="parallax-layer" data-speed="0.3"
       style="position:absolute;inset:0;z-index:0;will-change:transform;">
    <div style="position:absolute;top:10%;right:15%;width:300px;height:300px;border-radius:50%;border:1px solid rgba(116,86,241,0.08);"></div>
    <div style="position:absolute;bottom:20%;left:10%;width:200px;height:200px;border-radius:50%;border:1px solid rgba(116,86,241,0.05);"></div>
    <div style="position:absolute;top:40%;left:50%;width:400px;height:400px;border-radius:50%;background:radial-gradient(circle, rgba(116,86,241,0.03), transparent 70%);"></div>
  </div>

  <!-- Layer 2: Mid — SVG decorative curves (medium speed) -->
  <div class="parallax-layer" data-speed="0.6"
       style="position:absolute;inset:0;z-index:1;will-change:transform;">
    <svg style="position:absolute;bottom:0;left:0;width:100%;opacity:0.06;" viewBox="0 0 1440 200" fill="none">
      <path d="M0 100 Q360 20 720 100 T1440 100" stroke="rgba(116,86,241,0.3)" stroke-width="1" fill="none"/>
      <path d="M0 140 Q360 60 720 140 T1440 140" stroke="rgba(116,86,241,0.15)" stroke-width="1" fill="none"/>
    </svg>
  </div>

  <!-- Layer 3: Foreground — text content (full speed) -->
  <div class="parallax-layer" data-speed="1.0"
       style="position:relative;z-index:2;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:2rem;">
    <div style="text-align:center;">
      <h1 style="font-size:clamp(2.5rem,5vw,5.5rem);color:#E7EBEE;">Your Headline</h1>
      <p style="color:rgba(231,235,238,0.6);margin-top:1rem;">Subheading text</p>
    </div>
  </div>

</section>

<!-- Parallax scroll script (inject before </body>) -->
<script>
(function(){
  var layers = document.querySelectorAll('.parallax-layer[data-speed]');
  if (!layers.length) return;
  window.addEventListener('scroll', function(){
    var scrollY = window.pageYOffset;
    layers.forEach(function(layer){
      var speed = parseFloat(layer.dataset.speed) || 1;
      layer.style.transform = 'translateY(' + (scrollY * (1 - speed) * 0.5) + 'px)';
    });
  }, { passive: true });
})();
</script>
```

## Dependencies
- No external libraries
- Vanilla JS scroll listener with `{ passive: true }` for performance
- Hero section needs `position: relative; overflow: hidden; min-height: 100vh`

## When To Use
- **Industry fit:** Finance, consulting, luxury brands, architecture — any site wanting subtle dimensional sophistication
- **Best for:** Dark-themed hero sections with minimal imagery where depth creates visual interest
- **Pairs well with:** metallic-shimmer, cursor-spotlight, film-grain

## Injection Point
Replaces the hero section's inner structure. The three `.parallax-layer` divs go inside the hero `<section>`. The scroll script goes before `</body>`.

**Source:** `.agent/skills/luxury-editorial-finance/SKILL.md` — Element 9 (Parallax Depth Layers)
