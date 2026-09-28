# Wireframe Terrain
> Low-poly animated wireframe landscape with flowing displacement and brand-colored grid lines

## Preview
- Live: concept component (not yet deployed standalone)

## What It Does
Creates a Three.js wireframe plane that simulates rolling terrain using sine/cosine displacement. The mesh animates over time, producing a flowing landscape effect. Brand-colored wireframe lines on a dark background evoke data visualization and technical precision. Fully responsive.

## Code
```html
<!-- Wireframe Terrain - Three.js Animated Landscape -->
<!-- Add to <head>: -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>

<div id="terrain-container" style="position:absolute;inset:0;z-index:0;overflow:hidden;"></div>

<script>
(function(){
  var container = document.getElementById('terrain-container');
  if(!container || typeof THREE === 'undefined') return;

  var w = container.offsetWidth, h = container.offsetHeight;
  var scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0a0a0a, 0.035);

  var camera = new THREE.PerspectiveCamera(60, w/h, 0.1, 200);
  camera.position.set(0, 8, 15);
  camera.lookAt(0, 0, 0);

  var renderer = new THREE.WebGLRenderer({alpha: true, antialias: true});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  // Terrain plane
  var segments = 80;
  var geometry = new THREE.PlaneGeometry(40, 40, segments, segments);
  geometry.rotateX(-Math.PI / 2.2);

  // Replace f59e0b with your brand accent hex (no #)
  var material = new THREE.MeshBasicMaterial({
    color: 0xf59e0b,
    wireframe: true,
    transparent: true,
    opacity: 0.4
  });

  var mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);

  var positionAttr = geometry.attributes.position;
  var originalY = new Float32Array(positionAttr.count);
  for(var i = 0; i < positionAttr.count; i++){
    originalY[i] = positionAttr.getY(i);
  }

  function animate(){
    requestAnimationFrame(animate);
    var time = Date.now() * 0.0005;

    for(var i = 0; i < positionAttr.count; i++){
      var x = positionAttr.getX(i);
      var z = positionAttr.getZ(i);
      var displacement = Math.sin(x * 0.3 + time) * Math.cos(z * 0.3 + time * 0.7) * 1.8;
      displacement += Math.sin(x * 0.15 + time * 0.5) * 0.8;
      positionAttr.setY(i, originalY[i] + displacement);
    }
    positionAttr.needsUpdate = true;

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
- **Industry fit**: Tech, data analytics, construction, engineering, architecture
- **Best for**: Hero or section backgrounds on dark-themed sites needing a "technical" feel
- **Pairs well with**: counter-stats, gradient-text, scroll-progress-bar

## Injection Point
Inside a hero or feature `<section>` as the first child, with the section having `position: relative; overflow: hidden;`. The terrain container sits at `z-index: 0`. All content above it needs `position: relative; z-index: 1;`. The Three.js CDN script goes in `<head>`.
