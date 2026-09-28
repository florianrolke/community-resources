# Particle Torus
> 8000-particle Three.js torus knot rotating in 3D space with additive blending and fog depth

## Preview
- Live: https://driveby-demo.client.of.florianrolke.com (particle section)

## What It Does
Renders 8000 particles distributed across a torus knot surface (p=3, q=4, radius=5, tube=1.5) using Three.js. Particles are brand-colored with additive blending for a glowing effect. FogExp2 adds depth fade, and the knot rotates slowly on both axes. Fully responsive with resize handling.

## Code
```html
<!-- Particle Torus - Three.js Hero Background -->
<!-- Add to <head>: -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>

<!-- Place inside your hero <section> with position: relative; overflow: hidden; -->
<div id="anim-torus-container" style="position:absolute;inset:0;z-index:0;"></div>

<script>
(function(){
  var container = document.getElementById('anim-torus-container');
  if(!container || typeof THREE === 'undefined') return;

  var scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x000000, 0.06);

  var w = container.offsetWidth, h = container.offsetHeight;
  var camera = new THREE.PerspectiveCamera(60, w/h, 0.1, 100);
  camera.position.z = 12;

  var renderer = new THREE.WebGLRenderer({alpha: true, antialias: true});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  // Generate torus knot particles
  var positions = [];
  var count = 8000;
  var p = 3, q = 4, radius = 5, tube = 1.5;
  for(var i=0; i<count; i++){
    var u = Math.random() * Math.PI * 2;
    var v = Math.random() * Math.PI * 2;
    var r2 = tube * (0.5 + 0.5 * Math.cos(v));
    var x = (radius + r2 * Math.cos(q * u)) * Math.cos(p * u);
    var y = (radius + r2 * Math.cos(q * u)) * Math.sin(p * u);
    var z = r2 * Math.sin(q * u);
    var noise = 0.15;
    positions.push(
      x + (Math.random()-0.5)*noise,
      y + (Math.random()-0.5)*noise,
      z + (Math.random()-0.5)*noise
    );
  }

  var geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

  // Replace 06b6d4 with your brand hex color (no #)
  var material = new THREE.PointsMaterial({
    color: 0x06b6d4,
    size: 0.04,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  var points = new THREE.Points(geometry, material);
  scene.add(points);

  function animate(){
    requestAnimationFrame(animate);
    points.rotation.x += 0.0015;
    points.rotation.y += 0.002;
    renderer.render(scene, camera);
  }
  animate();

  window.addEventListener('resize', function(){
    w = container.offsetWidth;
    h = container.offsetHeight;
    camera.aspect = w/h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
})();
</script>
```

## Dependencies
- Three.js r128 CDN (~120KB gzipped): `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`

## When To Use
- **Industry fit**: Tech/SaaS, data analytics, fintech, any futuristic brand
- **Best for**: Hero section backgrounds on dark-themed sites
- **Pairs well with**: video-hero, glassmorphism cards, gradient-text

## Injection Point
Inside the hero `<section>` as the first child. The hero must have `position: relative; overflow: hidden;`. The torus container div sits at `z-index: 0`, and all hero content (headings, CTAs) should have `position: relative; z-index: 1;`. The Three.js CDN script goes in `<head>`.
