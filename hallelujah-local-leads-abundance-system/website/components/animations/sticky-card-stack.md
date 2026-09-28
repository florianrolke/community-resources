# Sticky Card Stack
> Multiple cards with position:sticky at staggered top offsets that stack on top of each other as the user scrolls

## Preview
- Live: https://delta-vega-luxury-k8.preview.florianrolke.com

## What It Does
A series of full-width or nearly full-width cards, each with `position: sticky` and incrementally increasing `top` values (12vh, 15vh, 18vh, 21vh). As the user scrolls past each card, it sticks to its position and the next card slides up from below to overlap it, creating a physical "card deck" stacking effect. Progressive z-index values and subtly lightening background colors create depth perception. Zero JavaScript required -- pure CSS sticky positioning.

## Code
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">

<style>
.stack-section {
  padding: 0 5vw;
  /* Enough height to scroll through all cards */
}
.stack-card {
  position: sticky;
  min-height: 70vh;
  padding: 4rem 3rem;
  border: 1px solid rgba(116, 86, 241, 0.12);
  border-radius: 2px;
  margin-bottom: 3rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  transition: box-shadow 0.4s ease;
}
.stack-card:hover {
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.3);
}

/* Staggered sticky positions + z-index + progressive backgrounds */
.stack-card:nth-child(1) {
  top: 12vh;
  z-index: 1;
  background: #0e1525;
}
.stack-card:nth-child(2) {
  top: 15vh;
  z-index: 2;
  background: #111a2d;
}
.stack-card:nth-child(3) {
  top: 18vh;
  z-index: 3;
  background: #141e35;
}
.stack-card:nth-child(4) {
  top: 21vh;
  z-index: 4;
  background: #17223d;
}
.stack-card:nth-child(5) {
  top: 24vh;
  z-index: 5;
  background: #1a2645;
}

.stack-card .card-number {
  font-family: 'Cormorant Garamond', serif;
  font-size: 4rem;
  font-weight: 300;
  color: rgba(116, 86, 241, 0.12);
  line-height: 1;
  margin-bottom: 1.5rem;
}
.stack-card h3 {
  font-family: 'Cormorant Garamond', serif;
  font-size: 2rem;
  font-weight: 400;
  color: #E7EBEE;
  margin-bottom: 1rem;
}
.stack-card p {
  font-family: 'Inter', sans-serif;
  font-size: 0.9rem;
  font-weight: 300;
  color: #4d5d6d;
  max-width: 560px;
  line-height: 1.7;
}

/* Mobile: reduce sticky offsets */
@media (max-width: 768px) {
  .stack-card { min-height: 50vh; padding: 2.5rem 1.5rem; }
  .stack-card:nth-child(1) { top: 8vh; }
  .stack-card:nth-child(2) { top: 10vh; }
  .stack-card:nth-child(3) { top: 12vh; }
  .stack-card:nth-child(4) { top: 14vh; }
  .stack-card:nth-child(5) { top: 16vh; }
}
</style>

<section class="stack-section">
  <div class="stack-card">
    <span class="card-number">01</span>
    <h3>Strategic Analysis</h3>
    <p>Deep quantitative research and modeling to uncover hidden patterns in complex financial data.</p>
  </div>
  <div class="stack-card">
    <span class="card-number">02</span>
    <h3>Risk Assessment</h3>
    <p>Comprehensive evaluation of portfolio exposure with stress testing across multiple scenarios.</p>
  </div>
  <div class="stack-card">
    <span class="card-number">03</span>
    <h3>Expert Testimony</h3>
    <p>Authoritative courtroom presence backed by decades of institutional research and publication.</p>
  </div>
  <div class="stack-card">
    <span class="card-number">04</span>
    <h3>Advisory Services</h3>
    <p>Ongoing strategic counsel for institutions navigating regulatory transitions and market shifts.</p>
  </div>
</section>
```

## Dependencies
- Google Fonts: Cormorant Garamond + Inter
- CSS `position: sticky` (universal modern browser support)
- Zero JavaScript

## When To Use
- **Industry fit:** Finance, consulting, law, SaaS, architecture -- any business with 3-6 service pillars
- **Best for:** Services sections, process steps, feature breakdowns, case study highlights
- **Pairs well with:** scroll-reveal (animate card content as each card sticks), numbered-feature layouts, gold-gradient-line between cards

## Injection Point
Place in the main content area where you would normally have a services grid or feature list. Each card needs enough surrounding scroll distance to create the stacking effect -- the section should have no explicit height constraint. Cards should contain concise content (heading + 1-2 lines) since they overlap. Best with 3-5 cards; more than 5 creates too much overlap at the bottom of the stack.
