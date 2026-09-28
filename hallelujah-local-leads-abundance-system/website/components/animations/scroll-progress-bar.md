# Scroll Progress Bar
> Thin gradient line at the top of the page that fills left-to-right as the user scrolls down

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
A fixed 2px bar pinned to the top of the viewport. As the user scrolls, JavaScript calculates the scroll percentage and sets the bar width accordingly. Uses requestAnimationFrame for jank-free rendering and a passive scroll listener for zero performance impact. Creates a subtle reading-progress indicator seen on premium editorial and long-form sites.

## Code
```html
<!-- Place immediately after <body> -->
<div style="position:fixed;top:0;left:0;width:100%;height:2px;z-index:9999;pointer-events:none;">
  <div id="scrollProgress" style="height:100%;width:0;background:linear-gradient(90deg,#7456f1,#c084fc);transform-origin:left;"></div>
</div>

<script>
(function(){
  var bar = document.getElementById('scrollProgress');
  var ticking = false;

  window.addEventListener('scroll', function(){
    if (!ticking) {
      requestAnimationFrame(function(){
        var scrollTop = window.scrollY;
        var docHeight = document.documentElement.scrollHeight - window.innerHeight;
        var progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
        bar.style.width = progress + '%';
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });
})();
</script>
```

### Color Variants
```css
/* Purple-violet (default, finance/tech) */
background: linear-gradient(90deg, #7456f1, #c084fc);

/* Gold (luxury/real estate) */
background: linear-gradient(90deg, #8B6914, #DAA520, #FFD700);

/* Teal (health/wellness) */
background: linear-gradient(90deg, #0d9488, #2dd4bf);

/* Red-orange (bold/agency) */
background: linear-gradient(90deg, #dc2626, #f97316);
```

## Dependencies
- None (vanilla JS + inline CSS)
- requestAnimationFrame (universal browser support)

## When To Use
- **Industry fit:** Long-form pages, case studies, multi-section landing pages, editorial content
- **Best for:** Pages with 4+ scroll-lengths of content where users benefit from orientation
- **Pairs well with:** sticky-blur-nav (both live at the top of the viewport), scroll-reveal sections

## Injection Point
Place the HTML immediately after the opening `<body>` tag. The bar sits at `z-index: 9999` so it layers above all content including sticky navs. If using a sticky nav, set the bar's `top` to the nav height (e.g., `top: 64px`) or keep at `top: 0` for the bar to overlay the nav edge.
