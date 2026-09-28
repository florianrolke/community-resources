# Preloader Curtain
> Split-screen curtain reveal with percentage counter, status text, and brand name fade-up sequence

## Preview
- Live: https://populon-demo.client.of.florianrolke.com

## What It Does
A full-screen preloader overlay with left and right curtain panels that slide outward when loading completes. While loading, a percentage counter increments from 0% to 100% with random step sizes (5-20% per tick), creating organic acceleration. Status text fades below the counter. Once 100% is reached, the content fades out, then the two curtains slide apart with a cubic-bezier(0.77, 0, 0.175, 1) easing -- the same curve used by award-winning agency sites. The page content is revealed behind the parting curtains.

## Code
```html
<style>
.preloader-container {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.preloader-curtain {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 50%;
  background: #0b0f1a;
  transition: transform 0.8s cubic-bezier(0.77, 0, 0.175, 1);
}
.preloader-curtain.left { left: 0; }
.preloader-curtain.right { right: 0; }
.preloader-curtain.done.left { transform: translateX(-100%); }
.preloader-curtain.done.right { transform: translateX(100%); }

.preloader-content {
  position: relative;
  z-index: 1;
  text-align: center;
  transition: opacity 0.3s;
}
.preloader-content.done { opacity: 0; }

.preloader-percentage {
  display: block;
  font-family: 'Inter', monospace;
  font-size: 3rem;
  font-weight: 700;
  color: #7456f1;
  letter-spacing: 0.1em;
}
.preloader-status {
  display: block;
  font-family: 'Inter', sans-serif;
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.3em;
  text-transform: uppercase;
  margin-top: 0.5rem;
}
.preloader-brand {
  display: block;
  font-family: 'Cormorant Garamond', serif;
  font-size: 1.2rem;
  font-weight: 300;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 0.5em;
  text-transform: uppercase;
  margin-top: 2rem;
  opacity: 0;
  transform: translateY(10px);
  animation: preloaderFadeUp 0.8s ease 0.5s forwards;
}
.preloader-tagline {
  display: block;
  font-family: 'Inter', sans-serif;
  font-size: 0.55rem;
  color: rgba(255, 255, 255, 0.2);
  letter-spacing: 0.4em;
  text-transform: uppercase;
  margin-top: 0.5rem;
  opacity: 0;
  transform: translateY(10px);
  animation: preloaderFadeUp 0.8s ease 0.8s forwards;
}

@keyframes preloaderFadeUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

<!-- Place immediately after <body> -->
<div class="preloader-container" id="preloader">
  <div class="preloader-curtain left" id="curtainL"></div>
  <div class="preloader-curtain right" id="curtainR"></div>
  <div class="preloader-content" id="preloaderContent">
    <span class="preloader-percentage" id="preloaderPct">0%</span>
    <span class="preloader-status">LOADING ASSETS...</span>
    <span class="preloader-brand">Your Brand</span>
    <span class="preloader-tagline">Your Tagline Here</span>
  </div>
</div>

<script>
(function(){
  var pct = 0;
  var pctEl = document.getElementById('preloaderPct');

  var interval = setInterval(function(){
    pct += Math.floor(Math.random() * 15) + 5;
    if (pct > 100) pct = 100;
    pctEl.textContent = pct + '%';

    if (pct >= 100) {
      clearInterval(interval);
      setTimeout(function(){
        document.getElementById('preloaderContent').classList.add('done');
        setTimeout(function(){
          document.getElementById('curtainL').classList.add('done');
          document.getElementById('curtainR').classList.add('done');
          setTimeout(function(){
            var preloader = document.getElementById('preloader');
            preloader.style.pointerEvents = 'none';
            preloader.style.display = 'none';
          }, 900);
        }, 300);
      }, 400);
    }
  }, 200);
})();
</script>
```

### Color Variants
```css
/* Dark navy (default) */
.preloader-curtain { background: #0b0f1a; }
.preloader-percentage { color: #7456f1; }

/* Pure black (cinematic) */
.preloader-curtain { background: #000; }
.preloader-percentage { color: #FF3B30; }

/* Warm dark (luxury) */
.preloader-curtain { background: #1a0f0a; }
.preloader-percentage { color: #d4af37; }
```

### Status Text Variants
```html
<!-- Tech/agency -->
<span class="preloader-status">INITIALIZING SYSTEMS...</span>

<!-- Luxury/editorial -->
<span class="preloader-status">PREPARING YOUR EXPERIENCE</span>

<!-- Finance -->
<span class="preloader-status">LOADING ANALYTICS...</span>
```

## Dependencies
- Google Fonts: Inter (for counter/status) + Cormorant Garamond (for brand name)
- Vanilla JS only (no libraries)

## When To Use
- **Industry fit:** Tech, finance, luxury, agencies, cinematic portfolio sites
- **Best for:** First impressions on hero-heavy pages, sites with large assets (video heroes, 3D elements) that need loading time
- **Pairs well with:** cinematic-full hero (the curtain reveals into the hero), video-hero backgrounds, particle effects that need initialization time

## Injection Point
Place immediately after the opening `<body>` tag, before all other content. The preloader sits at `z-index: 10000` covering everything. The percentage counter runs for approximately 1-2 seconds (random increments at 200ms intervals), then the content fades, curtains part, and the preloader is removed from display. Total sequence duration: approximately 2.5-3 seconds from page load.
