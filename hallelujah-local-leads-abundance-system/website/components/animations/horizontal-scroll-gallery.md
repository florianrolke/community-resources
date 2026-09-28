# Horizontal Scroll Gallery
> Vertical scrolling mapped to horizontal card movement inside a sticky viewport, creating a side-scrolling portfolio strip

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
A tall wrapper (250-300vh) contains a sticky inner container (100vh, position:sticky, top:0). Inside the sticky container is a flex row of cards. JavaScript maps the vertical scroll progress within the wrapper to a horizontal translateX on the card track. As the user scrolls down normally, the cards slide left through the viewport. Cards have thin accent borders, numbered headers (01, 02, 03...), and an accent-color top-line that appears on hover. Creates the editorial lookbook feel seen on Rolex, Apple, and luxury architecture portfolios.

## Code
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">

<style>
.hscroll-wrapper {
  height: 250vh;
}
.hscroll-sticky {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  padding: 0 6vw;
}
.hscroll-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2rem;
  font-family: 'Inter', sans-serif;
  font-size: 0.65rem;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: rgba(231, 235, 238, 0.5);
}
.hscroll-track {
  display: flex;
  gap: 2.5rem;
  transition: transform 0.1s linear;
}
.hscroll-card {
  min-width: 340px;
  flex-shrink: 0;
  background: #0e1525;
  border: 1px solid rgba(116, 86, 241, 0.15);
  padding: 2.5rem 2rem;
  position: relative;
  overflow: hidden;
  transition: border-color 0.4s, transform 0.4s;
}

/* Accent top-line on hover */
.hscroll-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, #7456f1, transparent);
  opacity: 0;
  transition: opacity 0.4s;
}
.hscroll-card:hover {
  border-color: rgba(116, 86, 241, 0.3);
  transform: translateY(-4px);
}
.hscroll-card:hover::before {
  opacity: 1;
}

.hscroll-card .card-num {
  font-family: 'Cormorant Garamond', serif;
  font-size: 3rem;
  font-weight: 300;
  color: rgba(116, 86, 241, 0.15);
  line-height: 1;
  margin-bottom: 1.5rem;
}
.hscroll-card h3 {
  font-family: 'Cormorant Garamond', serif;
  font-size: 1.5rem;
  font-weight: 400;
  color: #E7EBEE;
  margin-bottom: 1rem;
}
.hscroll-card p {
  font-family: 'Inter', sans-serif;
  font-size: 0.82rem;
  font-weight: 300;
  color: #4d5d6d;
  line-height: 1.7;
}

/* Mobile: vertical stack fallback */
@media (max-width: 768px) {
  .hscroll-wrapper { height: auto; }
  .hscroll-sticky { position: relative; height: auto; padding: 4rem 1.5rem; }
  .hscroll-track { flex-direction: column; gap: 1.5rem; }
  .hscroll-card { min-width: auto; }
}
</style>

<section class="hscroll-wrapper">
  <div class="hscroll-sticky">
    <div class="hscroll-label">
      <span>Featured Services</span>
      <span>01 &mdash; 05</span>
    </div>
    <div class="hscroll-track">
      <div class="hscroll-card">
        <div class="card-num">01</div>
        <h3>Interest Rate Modeling</h3>
        <p>Multi-curve framework for SOFR migration across institutional portfolios with real-time calibration.</p>
      </div>
      <div class="hscroll-card">
        <div class="card-num">02</div>
        <h3>Derivatives Pricing</h3>
        <p>Monte Carlo engines for path-dependent exotic options with advanced variance reduction.</p>
      </div>
      <div class="hscroll-card">
        <div class="card-num">03</div>
        <h3>Risk Analytics</h3>
        <p>Historical and simulation-based VaR with regulatory stress testing and backtesting suites.</p>
      </div>
      <div class="hscroll-card">
        <div class="card-num">04</div>
        <h3>Expert Testimony</h3>
        <p>Authoritative analysis for litigation involving complex financial instruments and benchmark manipulation.</p>
      </div>
      <div class="hscroll-card">
        <div class="card-num">05</div>
        <h3>Strategic Advisory</h3>
        <p>Ongoing counsel for institutions navigating rate transitions, regulatory changes, and market disruptions.</p>
      </div>
    </div>
  </div>
</section>

<script>
(function(){
  var wrapper = document.querySelector('.hscroll-wrapper');
  var track = document.querySelector('.hscroll-track');
  var sticky = document.querySelector('.hscroll-sticky');

  if (!wrapper || !track || !sticky) return;

  /* Skip on mobile where we use vertical stack */
  if (window.innerWidth <= 768) return;

  window.addEventListener('scroll', function() {
    var rect = wrapper.getBoundingClientRect();
    var scrollProgress = -rect.top / (wrapper.offsetHeight - window.innerHeight);
    var clampedProgress = Math.max(0, Math.min(1, scrollProgress));
    var maxTranslate = track.scrollWidth - sticky.offsetWidth + 100;
    track.style.transform = 'translateX(-' + (clampedProgress * maxTranslate) + 'px)';
  }, { passive: true });
})();
</script>
```

## Dependencies
- Google Fonts: Cormorant Garamond (300, 400) + Inter (300, 400, 500)
- CSS `position: sticky` + vanilla JS scroll listener
- Passive scroll listener for zero jank

## When To Use
- **Industry fit:** Finance, architecture, luxury portfolios, agencies, editorial publications
- **Best for:** Services showcase, portfolio items, case studies, expertise areas, publications list
- **Pairs well with:** monospace-label counters (01-05 in the header), ghost-outline CTA buttons, scroll-reveal for the section title above

## Injection Point
Place in the main content area where you would normally have a card grid. The wrapper needs exactly 250vh height for comfortable scroll-to-horizontal mapping (increase to 300vh for more cards). On mobile (under 768px), the layout automatically falls back to a vertical stack with no JS execution. The `hscroll-label` header with count (01-05) goes inside the sticky container above the track.
