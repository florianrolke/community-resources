# Counter Stats
> Animated numbers that count up from zero when scrolled into view, with cubic ease-out and prefix/suffix support

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
Numbers with `data-target` attributes animate from 0 to their final value when they enter the viewport. Uses IntersectionObserver to trigger and requestAnimationFrame for smooth 60fps counting. The cubic ease-out curve (`1 - Math.pow(1-progress, 3)`) makes numbers accelerate fast then decelerate elegantly. Supports decimals, dollar prefix, and suffixes (B+, yrs, +) styled in accent color. Duration is 2000-2200ms.

## Code
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">

<style>
.stats-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 3rem;
  padding: 4rem 2rem;
  background: #102136;
  border-top: 1px solid rgba(116, 86, 241, 0.15);
  border-bottom: 1px solid rgba(116, 86, 241, 0.15);
}
.stat { text-align: center; }
.stat-number, .stat-prefix, .stat-suffix {
  font-family: 'Cormorant Garamond', serif;
  font-size: 3.5rem;
  font-weight: 300;
  color: #E7EBEE;
  line-height: 1;
}
.stat-suffix {
  font-size: 1.5rem;
  color: #7456f1;
  margin-left: 2px;
}
.stat-prefix {
  font-size: 2rem;
  color: #7456f1;
  margin-right: 2px;
}
.stat-label {
  display: block;
  margin-top: 0.75rem;
  font-family: 'Inter', sans-serif;
  font-size: 0.7rem;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  color: #4d5d6d;
}
.stat-divider {
  width: 1px;
  height: 50px;
  background: linear-gradient(to bottom, transparent, rgba(116,86,241,0.3), transparent);
}

/* Responsive */
@media (max-width: 768px) {
  .stats-bar { flex-wrap: wrap; gap: 2rem; }
  .stat-divider { display: none; }
  .stat { flex: 0 0 45%; }
  .stat-number, .stat-prefix, .stat-suffix { font-size: 2.5rem; }
}
</style>

<section class="stats-bar">
  <div class="stat">
    <span class="stat-prefix">$</span>
    <span class="stat-number" data-target="4.2">0</span>
    <span class="stat-suffix">B+</span>
    <span class="stat-label">Positions Analyzed</span>
  </div>
  <div class="stat-divider"></div>
  <div class="stat">
    <span class="stat-number" data-target="200">0</span>
    <span class="stat-suffix">+</span>
    <span class="stat-label">Expert Reports</span>
  </div>
  <div class="stat-divider"></div>
  <div class="stat">
    <span class="stat-number" data-target="25">0</span>
    <span class="stat-suffix">yrs</span>
    <span class="stat-label">Industry Experience</span>
  </div>
  <div class="stat-divider"></div>
  <div class="stat">
    <span class="stat-number" data-target="50">0</span>
    <span class="stat-suffix">+</span>
    <span class="stat-label">Litigation Cases</span>
  </div>
</section>

<script>
(function(){
  function animateCounters() {
    var counters = document.querySelectorAll('.stat-number');
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        var target = parseFloat(el.dataset.target);
        var isDecimal = target % 1 !== 0;
        var duration = 2200;
        var start = performance.now();

        function tick(now) {
          var elapsed = now - start;
          var progress = Math.min(elapsed / duration, 1);
          var eased = 1 - Math.pow(1 - progress, 3); /* cubic ease-out */
          var current = target * eased;
          el.textContent = isDecimal ? current.toFixed(1) : Math.floor(current);
          if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        observer.unobserve(el);
      });
    }, { threshold: 0.5 });

    counters.forEach(function(c) { observer.observe(c); });
  }
  document.addEventListener('DOMContentLoaded', animateCounters);
})();
</script>
```

## Dependencies
- Google Fonts: Cormorant Garamond (300, 400) + Inter (300, 400, 500)
- IntersectionObserver + requestAnimationFrame (universal support)

## When To Use
- **Industry fit:** Finance, consulting, SaaS, real estate, any data-driven business
- **Best for:** Social proof sections, credentials bars, trust indicators, "by the numbers" rows
- **Pairs well with:** gold-gradient-line dividers (above/below the stats bar), bento-grid layouts, scroll-reveal for surrounding sections

## Injection Point
Place between the hero/marquee and the main content sections. Works best as a full-width horizontal bar separating the above-fold area from the body content. Replace `data-target`, prefix, suffix, and label values with client-specific stats.
