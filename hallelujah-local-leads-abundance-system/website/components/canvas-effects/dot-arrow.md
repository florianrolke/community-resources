# Dot Arrow
> Directional arrow-shaped dot grid with base-to-tip shimmer wave animation

## Preview
- Live: concept (variation of dot-rhombus, same engine)

## What It Does
Uses the same Canvas 2D shimmer engine as dot-rhombus but masks dots into an arrow shape pointing upward. The sine wave animation flows from the base to the tip, creating a directional energy effect. Dot size oscillates 1-4px and opacity 0.3-1.0 at 15% canvas opacity.

## Code
```html
<!-- Dot Arrow Canvas Effect -->
<!-- Place inside any <section> with position: relative; overflow: hidden; -->
<canvas id="anim-dots-arrow" style="position:absolute;inset:0;z-index:0;pointer-events:none;opacity:0.15;"></canvas>

<script>
(function(){
  var c = document.getElementById('anim-dots-arrow');
  if(!c) return;
  var ctx = c.getContext('2d');
  var spacing = 18;
  var dots = [];

  function resize(){
    c.width = c.parentElement.offsetWidth;
    c.height = c.parentElement.offsetHeight;
    dots = [];
    var cx = c.width/2, cy = c.height/2;
    var arrowW = c.width * 0.6, arrowH = c.height * 0.8;
    for(var x=0; x<c.width; x+=spacing){
      for(var y=0; y<c.height; y+=spacing){
        var relX = x - cx, relY = y - cy;
        if(relX > -arrowW/2 && relX < arrowW/2 && relY > relX * 0.5 && relY < -relX * 0.5 + arrowH){
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
- **Industry fit**: Tech, startups, growth-focused brands
- **Best for**: Section backgrounds where you want directional visual energy (e.g., above a CTA)
- **Pairs well with**: video-hero, gradient-text, scroll-reveal

## Injection Point
Inside a `<section>` element. The parent section must have `position: relative; overflow: hidden;`. The canvas is inserted as the first child. All sibling content needs `position: relative; z-index: 1;` to float above.
