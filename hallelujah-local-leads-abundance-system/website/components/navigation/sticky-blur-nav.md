# Sticky Blur Navigation
> Fixed-position navbar with backdrop blur that transitions from transparent to solid on scroll

## Preview
- Live: ALL deployed sites (https://delta-vega-luxury.preview.florianrolke.com, https://teamsiok-luxury.preview.florianrolke.com, https://populon-demo.client.of.florianrolke.com, etc.)

## What It Does
A fixed navigation bar that starts transparent over the hero section, then transitions to a blurred semi-opaque background once the user scrolls past 60px. The blur effect creates a frosted glass appearance that maintains visibility of the content beneath while keeping the nav readable. A subtle bottom border appears on scroll to define the nav boundary. This is the standard navigation pattern used on every deployed luxury site.

## Code
```html
<nav class="nav-blur" id="mainNav">
  <div class="nav-blur-inner">
    <!-- Logo -->
    <a href="#" class="nav-blur-logo">
      <span class="nav-blur-logo-text">BRAND</span>
    </a>

    <!-- Desktop links -->
    <ul class="nav-blur-links">
      <li><a href="#services">Services</a></li>
      <li><a href="#about">About</a></li>
      <li><a href="#portfolio">Portfolio</a></li>
      <li><a href="#contact">Contact</a></li>
    </ul>

    <!-- CTA button -->
    <a href="#contact" class="nav-blur-cta">Get Started</a>

    <!-- Mobile menu toggle -->
    <button class="nav-blur-toggle" id="navToggle" aria-label="Toggle menu">
      <span></span>
      <span></span>
      <span></span>
    </button>
  </div>

  <!-- Mobile menu -->
  <div class="nav-blur-mobile" id="navMobile">
    <ul>
      <li><a href="#services">Services</a></li>
      <li><a href="#about">About</a></li>
      <li><a href="#portfolio">Portfolio</a></li>
      <li><a href="#contact">Contact</a></li>
    </ul>
  </div>
</nav>

<style>
.nav-blur {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  background: transparent;
  border-bottom: 1px solid transparent;
  transition: background 0.3s ease,
              border-color 0.3s ease;
}

/* Scrolled state (added via JS) */
.nav-blur.scrolled {
  background: rgba(10, 10, 10, 0.85);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.nav-blur-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Logo */
.nav-blur-logo {
  text-decoration: none;
}

.nav-blur-logo-text {
  font-family: var(--font-heading, 'Inter', sans-serif);
  font-size: 1.1rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

/* Desktop links */
.nav-blur-links {
  display: flex;
  list-style: none;
  gap: 2.5rem;
  margin: 0;
  padding: 0;
}

.nav-blur-links a {
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.8rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  transition: color 0.3s ease;
}

.nav-blur-links a:hover {
  color: #ffffff;
}

/* CTA in nav */
.nav-blur-cta {
  display: inline-flex;
  align-items: center;
  padding: 8px 24px;
  border-radius: 9999px;
  background: var(--accent, #C9A96E);
  color: var(--accent-contrast, #000000);
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-decoration: none;
  transition: opacity 0.3s ease;
}

.nav-blur-cta:hover {
  opacity: 0.85;
}

/* Mobile toggle */
.nav-blur-toggle {
  display: none;
  flex-direction: column;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
}

.nav-blur-toggle span {
  display: block;
  width: 22px;
  height: 1.5px;
  background: #ffffff;
  transition: transform 0.3s ease, opacity 0.3s ease;
}

/* Mobile menu */
.nav-blur-mobile {
  display: none;
  padding: 1rem 2rem 2rem;
}

.nav-blur-mobile ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-blur-mobile a {
  display: block;
  padding: 0.75rem 0;
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.nav-blur-mobile a:hover {
  color: #ffffff;
}

/* Mobile toggle active state */
.nav-blur-toggle.active span:nth-child(1) {
  transform: translateY(6.5px) rotate(45deg);
}

.nav-blur-toggle.active span:nth-child(2) {
  opacity: 0;
}

.nav-blur-toggle.active span:nth-child(3) {
  transform: translateY(-6.5px) rotate(-45deg);
}

/* Responsive */
@media (max-width: 768px) {
  .nav-blur-links,
  .nav-blur-cta {
    display: none;
  }

  .nav-blur-toggle {
    display: flex;
  }

  .nav-blur-mobile.open {
    display: block;
  }
}
</style>

<script>
(function() {
  var nav = document.getElementById('mainNav');
  var toggle = document.getElementById('navToggle');
  var mobile = document.getElementById('navMobile');

  // Scroll detection
  window.addEventListener('scroll', function() {
    if (window.scrollY > 60) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
  }, { passive: true });

  // Mobile toggle
  if (toggle && mobile) {
    toggle.addEventListener('click', function() {
      toggle.classList.toggle('active');
      mobile.classList.toggle('open');
    });

    // Close on link click
    mobile.querySelectorAll('a').forEach(function(link) {
      link.addEventListener('click', function() {
        toggle.classList.remove('active');
        mobile.classList.remove('open');
      });
    });
  }
})();
</script>
```

## Dependencies
- CSS `backdrop-filter` support (all modern browsers; falls back to solid background in older browsers)
- JavaScript for scroll detection and mobile menu toggle
- CSS custom properties: `--accent`, `--accent-contrast`, `--font-heading`, `--font-body`

## When To Use
- **Industry fit**: Universal -- the standard navigation for every luxury redesign
- **Best for**: Any single-page or multi-page site with a hero section, where the nav should be transparent over the hero and solidify on scroll
- **Pairs well with**: Every other component -- this is the foundational navigation pattern

## Injection Point
Place as the first child of `<body>`, before any section content. Add `padding-top: 80px` (or nav height) to the first section to prevent content from hiding behind the fixed nav. Place the `<script>` block before `</body>`.
