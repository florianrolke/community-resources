# Glass Orb
> Floating translucent glass sphere with environment reflections and gentle bobbing animation

## Preview
- Live: concept component (not yet deployed standalone)

## What It Does
Renders a photorealistic glass sphere using Three.js MeshPhysicalMaterial with high transmission (0.9) for see-through glass. The orb floats with a sine-wave Y-axis animation and slowly rotates. Environment reflections are generated via PMREMGenerator. A CSS-only fallback is included for lightweight pages.

## Code
```html
<!-- Glass Orb - Three.js Version -->
<!-- Add to <head>: -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>

<div id="glass-orb-container" style="width:300px;height:300px;position:relative;margin:0 auto;"></div>

<script>
(function(){
  var container = document.getElementById('glass-orb-container');
  if(!container || typeof THREE === 'undefined') return;

  var w = container.offsetWidth, h = container.offsetHeight;
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 100);
  camera.position.z = 5;

  var renderer = new THREE.WebGLRenderer({alpha: true, antialias: true});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  container.appendChild(renderer.domElement);

  // Environment map for reflections
  var pmremGenerator = new THREE.PMREMGenerator(renderer);
  var envScene = new THREE.Scene();
  envScene.background = new THREE.Color(0x111122);
  var light1 = new THREE.PointLight(0x7456f1, 2, 50);
  light1.position.set(5, 5, 5);
  envScene.add(light1);
  var light2 = new THREE.PointLight(0x06b6d4, 1.5, 50);
  light2.position.set(-5, -3, 3);
  envScene.add(light2);
  var envMap = pmremGenerator.fromScene(envScene).texture;

  // Glass sphere
  var geometry = new THREE.SphereGeometry(1.2, 64, 64);
  var material = new THREE.MeshPhysicalMaterial({
    transmission: 0.9,
    roughness: 0.1,
    metalness: 0,
    thickness: 1.5,
    envMap: envMap,
    envMapIntensity: 1.0,
    clearcoat: 1.0,
    clearcoatRoughness: 0.1,
    transparent: true,
    opacity: 0.95
  });
  var sphere = new THREE.Mesh(geometry, material);
  scene.add(sphere);

  // Ambient + directional light
  scene.add(new THREE.AmbientLight(0xffffff, 0.3));
  var dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(3, 5, 4);
  scene.add(dirLight);

  var startTime = Date.now();
  function animate(){
    requestAnimationFrame(animate);
    var elapsed = (Date.now() - startTime) / 1000;
    sphere.position.y = Math.sin(elapsed * 0.8) * 0.3;
    sphere.rotation.y += 0.003;
    sphere.rotation.x += 0.001;
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

<!-- CSS-Only Fallback (no Three.js needed) -->
<!--
<div style="width:200px;height:200px;margin:0 auto;border-radius:50%;
  background: radial-gradient(circle at 35% 35%, rgba(255,255,255,0.4), rgba(116,86,241,0.15) 40%, rgba(6,182,212,0.1) 70%, transparent);
  box-shadow: 0 0 60px rgba(116,86,241,0.3), inset 0 0 40px rgba(255,255,255,0.1);
  animation: orbFloat 4s ease-in-out infinite;">
</div>
<style>
@keyframes orbFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-15px); }
}
</style>
-->
```

## Dependencies
- Three.js r128 CDN (~120KB gzipped): `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`
- CSS-only fallback: zero dependencies

## When To Use
- **Industry fit**: Tech/SaaS, fintech, AI companies, innovation brands
- **Best for**: Hero section accent element, floating beside headline text
- **Pairs well with**: gradient-text, particle-torus, glassmorphism cards

## Injection Point
Place the container `div` inside the hero section, typically beside or behind the main headline. For a split-layout hero, put it in the right column. The CSS fallback can be dropped anywhere as a decorative accent.
