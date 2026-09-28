# Scroll Reveal
> Fade-in-up entrance animation triggered by IntersectionObserver as elements enter the viewport

## Preview
- Live: visible on ALL deployed preview.florianrolke.com sites (injected by animate_static_page.py)

## What It Does
Adds a fade-in-up animation to all direct children of `<section>` and `<main>` elements. Each element starts invisible and 25px below its final position, then smoothly transitions into place when it scrolls into view. Staggered delays (0.1s increments) create a cascading waterfall effect across sibling elements.

## Code
```html
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

<!-- Add class to any element you want to reveal on scroll -->
<section>
  <div class="anim-fade-in-up" style="transition-delay: 0s;">
    <h2>First element fades in</h2>
  </div>
  <div class="anim-fade-in-up" style="transition-delay: 0.1s;">
    <p>Second element fades in 0.1s later</p>
  </div>
  <div class="anim-fade-in-up" style="transition-delay: 0.2s;">
    <p>Third element fades in 0.2s later</p>
  </div>
  <div class="anim-fade-in-up" style="transition-delay: 0.3s;">
    <p>Fourth element continues the cascade</p>
  </div>
</section>

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

## Dependencies
- None (vanilla JS + CSS only)
- IntersectionObserver (supported in all modern browsers)

## When To Use
- **Industry fit:** Universal -- works on every industry and style
- **Best for:** Any page with stacked content sections (services, features, testimonials, team grids)
- **Pairs well with:** counter-stats (numbers reveal as they fade in), glassmorphism cards, bento-grid layouts, any section-based content

## Injection Point
Add `.anim-fade-in-up` class to direct children of `<section>` or `<main>` elements. Place the `<style>` block in `<head>` and the `<script>` block just before `</body>`. Stagger delays by adding `transition-delay: {n * 0.1}s` inline, cycling every 6 elements (0.0s through 0.5s).
