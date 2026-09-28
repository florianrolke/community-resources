# Dot Rhombus
> Shimmering diamond-shaped dot grid that pulses with a sine-wave shimmer across a section background

## Preview
- Live: https://driveby-demo.client.of.florianrolke.com

## What It Does
Renders a Canvas 2D dot grid masked into a diamond (rhombus) shape. Each dot oscillates in size (1-4px) and opacity (0.3-1.0) using a sine wave, creating a breathing shimmer effect. The canvas sits behind section content at 15% opacity as an ambient texture.

## Code
```html
<!-- Dot Rhombus Canvas Effect -->
<!-- Place inside any <section> with position: relative; overflow: hidden; -->
<canvas id="anim-dots-rhombus" style="position:absolute;inset:0;z-index:0;pointer-events:none;opacity:0.15;"></canvas>

<script>
(function(){
  var c = document.getElementById('anim-dots-rhombus');
  if(!c) return;
  var ctx = c.getContext('2d');
  var spacing = 18;
  var dots = [];

  function resize(){
    c.width = c.parentElement.offsetWidth;
    c.height = c.parentElement.offsetHeight;
    dots = [];
    var cx = c.width/2, cy = c.height/2;
    var rhombusSize = Math.min(c.width, c.height) * 0.45;
    for(var x=0; x<c.width; x+=spacing){
      for(var y=0; y<c.height; y+=spacing){
        var relX = x - cx, relY = y - cy;
        if(Math.abs(relX) + Math.abs(relY) < rhombusSize){
          dots.push({x:x, y:y});
        }
      }
    }
  }
  resize();
  window.addEventListener('resize', resize);

  function animate(time){
    ctx.clearRect(0,0,c.width,c.height);
    for(var i=0;i<dots.length;i++){
      var d = dots[i];
      var dist = d.x + d.y;
      var wave = Math.sin(dist * 0.008 - time / 600);
      var size = 1 + (wave + 1) * 1.5;
      var opacity = 0.3 + (wave + 1) * 0.35;
      ctx.fillStyle = 'rgba(255,255,255,' + opacity + ')';
      ctx.beginPath();
      ctx.arc(d.x, d.y, size, 0, Math.PI*2);
      ctx.fill();
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();
</script>
```

## Dependencies
- None (pure Canvas 2D, zero external libraries)

## When To Use
- **Industry fit**: Tech/SaaS, finance, any dark-themed site
- **Best for**: Mid-page section backgrounds that need subtle geometric texture
- **Pairs well with**: video-hero, cinematic-full, particle-torus

## Injection Point
Inside a `<section>` element (typically the second section). The parent section must have `position: relative; overflow: hidden;`. The canvas is inserted as the first child. All sibling content should have `position: relative; z-index: 1;` so it floats above the canvas.
