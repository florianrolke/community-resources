# Character Reveal
> Per-character staggered animation where each letter slides up and fades in individually on scroll

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
Headlines with the `[data-split]` attribute get their text content split into individual `<span class="split-char">` elements. Each character starts at opacity 0 and translateY(35-40px), then reveals with a staggered transition-delay (30-35ms per character) when the element enters the viewport via IntersectionObserver. Creates a typewriter-meets-curtain-reveal moment that signals premium craftsmanship. Far more sophisticated than block-level fade-in reveals.

## Code
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&display=swap" rel="stylesheet">

<style>
.split-char {
  display: inline-block;
  opacity: 0;
  transform: translateY(40px) rotateX(-15deg);
  transition: opacity 0.5s ease, transform 0.5s ease;
}
.revealed .split-char {
  opacity: 1;
  transform: translateY(0) rotateX(0deg);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .split-char {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
</style>

<!-- Add data-split to any headline -->
<h1 class="split-reveal" data-split
    style="font-family:'Cormorant Garamond',serif; font-size:4rem; font-weight:300; color:#E7EBEE;">
  Quantitative Precision
</h1>

<h2 class="split-reveal" data-split
    style="font-family:'Cormorant Garamond',serif; font-size:2.5rem; font-weight:300; color:#E7EBEE;">
  Analytical Excellence
</h2>

<script>
(function(){
  document.querySelectorAll('[data-split]').forEach(function(el) {
    var text = el.textContent;
    el.innerHTML = '';
    var chars = text.split('');

    chars.forEach(function(char, i) {
      var span = document.createElement('span');
      span.textContent = char === ' ' ? '\u00A0' : char;
      span.className = 'split-char';
      span.style.transitionDelay = (i * 30) + 'ms';
      el.appendChild(span);
    });

    var observer = new IntersectionObserver(function(entries) {
      if (entries[0].isIntersecting) {
        el.classList.add('revealed');
        observer.disconnect();
      }
    }, { threshold: 0.5 });
    observer.observe(el);
  });
})();
</script>
```

### Variations
```css
/* Rise from below (default, most elegant) */
.split-char { transform: translateY(40px) rotateX(-15deg); }

/* Slide from left */
.split-char { transform: translateX(-20px); }

/* Scale up from small */
.split-char { transform: scale(0.6); }

/* Focus-pull blur effect (combine with any above) */
.split-char { filter: blur(4px); }
.revealed .split-char { filter: blur(0); }
```

## Dependencies
- Google Fonts: Cormorant Garamond (or any serif for luxury feel)
- IntersectionObserver (universal support)

## When To Use
- **Industry fit:** Finance, law, luxury, architecture, high-end consulting
- **Best for:** Hero headlines, section titles, CTA headlines -- use on 1-3 headlines max per page
- **Pairs well with:** metallic-shimmer gradient text, gold-gradient-line dividers, scroll-reveal for body content below the headline

## Injection Point
Add `data-split` attribute to any `<h1>`, `<h2>`, or headline element. Place the `<style>` in `<head>` and the `<script>` before `</body>`. The script auto-discovers all `[data-split]` elements. Use sparingly -- overuse dilutes the premium effect. Best on 1 hero headline and 1-2 section titles.
