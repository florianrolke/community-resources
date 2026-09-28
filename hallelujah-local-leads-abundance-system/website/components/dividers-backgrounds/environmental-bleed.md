# Environmental Bleed
> A background photograph at near-invisible opacity with edge-fading mask, adding ambient context to sections

## Preview
- Live: Used across deployed luxury sites for contextual atmosphere

## What It Does
Places a background image at extremely low opacity (0.04-0.07) behind a section's content. A CSS mask fades the image to transparent at the top and bottom edges, preventing hard boundaries. The image bleeds through just enough to set a mood -- an office interior for an about section, a cityscape for a contact section -- without competing with foreground content. Non-interactive and layered beneath all content.

## Code
```html
<section class="env-bleed-section">
  <!-- Background bleed image -->
  <div class="env-bleed-bg" aria-hidden="true">
    <img src="https://placehold.co/1920x1080/111/222?text=Background" alt="" loading="lazy">
  </div>

  <!-- Actual section content -->
  <div class="env-bleed-content">
    <h2>About Our Firm</h2>
    <p>Your section content goes here. The background image provides subtle atmospheric context without interfering with readability.</p>
    <a href="#contact" class="btn-pill-glow">Get in Touch</a>
  </div>
</section>

<style>
.env-bleed-section {
  position: relative;
  padding: 8rem 2rem;
  overflow: hidden;
}

.env-bleed-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.05;
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 15%,
    black 85%,
    transparent 100%
  );
  mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 15%,
    black 85%,
    transparent 100%
  );
}

.env-bleed-bg img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.env-bleed-content {
  position: relative;
  z-index: 1;
  max-width: 900px;
  margin: 0 auto;
}

.env-bleed-content h2 {
  font-family: var(--font-heading, 'Cormorant Garamond', serif);
  font-size: 2.5rem;
  color: #ffffff;
  margin-bottom: 1.5rem;
}

.env-bleed-content p {
  font-size: 1rem;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 2rem;
  max-width: 600px;
}

/* Higher opacity variant (more visible background) */
.env-bleed-bg--visible {
  opacity: 0.08;
}

/* Side-fade variant (fades left and right too) */
.env-bleed-bg--all-edges {
  -webkit-mask-image: radial-gradient(
    ellipse 70% 80% at center,
    black 40%,
    transparent 100%
  );
  mask-image: radial-gradient(
    ellipse 70% 80% at center,
    black 40%,
    transparent 100%
  );
}

/* Using CSS background-image instead of <img> */
.env-bleed-css {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.05;
  background-image: url('path/to/image.jpg');
  background-size: cover;
  background-position: center;
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 15%,
    black 85%,
    transparent 100%
  );
  mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 15%,
    black 85%,
    transparent 100%
  );
}
</style>
```

## Dependencies
- CSS `mask-image` with `-webkit-` prefix for Safari support
- A relevant background image (industry-appropriate photo)
- No JavaScript required

## When To Use
- **Industry fit**: Real estate, hospitality, architecture, food & beverage, luxury -- any industry with strong visual identity
- **Best for**: About sections (office/team photo bleed), contact sections (location/cityscape), service sections (industry imagery)
- **Pairs well with**: film-grain (grain + bleed = magazine editorial), glassmorphism (glass cards over bleed background), gold-gradient-line (divider above/below bleed sections)

## Injection Point
Add the `.env-bleed-bg` div as the first child inside a `<section>`. Set the section to `position: relative` and ensure all content has `position: relative; z-index: 1`. Choose an image contextually relevant to the section's content. Keep opacity between 0.04 and 0.07 -- higher values compete with foreground text.
