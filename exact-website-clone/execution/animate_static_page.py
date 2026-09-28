#!/usr/bin/env python3
"""
Skill 5: Static → Animated Video Page

Takes any static HTML page and injects animation layers:
  - video-hero:      Full-screen brand-tinted video behind hero
  - scroll-reveals:  Fade-in-up on all sections
  - dot-rhombus:     Canvas 2D shimmering diamond dot-grid (DriveBy style)
  - dot-arrow:       Canvas 2D directional arrow dot-grid
  - particle-torus:  Three.js rotating particle torus knot
  - cinematic-full:  All of the above (populon.ai treatment)

Usage:
    python execution/animate_static_page.py \
      --input .tmp/redesigns/delta-vega-improved.html \
      --effect video-hero \
      --brand-color "#09240F" \
      --output .tmp/animated/delta-vega-cinematic.html

    python execution/animate_static_page.py \
      --input .tmp/redesigns/delta-vega-improved.html \
      --effect cinematic-full \
      --brand-color "#09240F" \
      --slug delta-vega-cinematic \
      --deploy
"""

import os
import sys
import re
import json
import argparse
import subprocess
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    print("ERROR: pip install beautifulsoup4")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Video source library (free Pexels stock)
# ---------------------------------------------------------------------------
VIDEO_LIBRARY = {
    'tech':     'https://videos.pexels.com/video-files/3129671/3129671-uhd_2560_1440_25fps.mp4',
    'abstract': 'https://videos.pexels.com/video-files/2169880/2169880-uhd_2560_1440_30fps.mp4',
    'nature':   'https://videos.pexels.com/video-files/5529539/5529539-uhd_2560_1440_25fps.mp4',
    'city':     'https://videos.pexels.com/video-files/3571264/3571264-uhd_2560_1440_30fps.mp4',
    'data':     'https://videos.pexels.com/video-files/5474057/5474057-hd_1920_1080_30fps.mp4',
    'code':     'https://videos.pexels.com/video-files/7710243/7710243-hd_1920_1080_30fps.mp4',
    'finance':  'https://videos.pexels.com/video-files/3129671/3129671-uhd_2560_1440_25fps.mp4',
}

POSTER_LIBRARY = {
    'tech':     'https://images.pexels.com/photos/373543/pexels-photo-373543.jpeg?auto=compress&cs=tinysrgb&w=1920',
    'abstract': 'https://images.pexels.com/photos/1561020/pexels-photo-1561020.jpeg?auto=compress&cs=tinysrgb&w=1920',
    'nature':   'https://images.pexels.com/photos/1407846/pexels-photo-1407846.jpeg?auto=compress&cs=tinysrgb&w=1920',
    'city':     'https://images.pexels.com/photos/574919/pexels-photo-574919.jpeg?auto=compress&cs=tinysrgb&w=1920',
    'data':     'https://images.pexels.com/photos/373543/pexels-photo-373543.jpeg?auto=compress&cs=tinysrgb&w=1920',
    'code':     'https://images.pexels.com/photos/373543/pexels-photo-373543.jpeg?auto=compress&cs=tinysrgb&w=1920',
    'finance':  'https://images.pexels.com/photos/373543/pexels-photo-373543.jpeg?auto=compress&cs=tinysrgb&w=1920',
}

# ---------------------------------------------------------------------------
# SVG brand color matrix
# ---------------------------------------------------------------------------
def hex_to_color_matrix(hex_color):
    """Convert hex color to SVG feColorMatrix values for monotone tinting."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (f"{r:.2f} 0 0 0 {1-r:.2f} "
            f"{g:.2f} 0 0 0 {1-g:.2f} "
            f"{b:.2f} 0 0 0 {1-b:.2f} "
            f"0 0 0 1 0")


def pick_video_category(slug):
    """Guess video category from slug name."""
    slug_lower = slug.lower() if slug else ''
    if any(w in slug_lower for w in ['tech', 'ai', 'auto', 'data', 'software', 'driveby']):
        return 'tech'
    if any(w in slug_lower for w in ['finance', 'vega', 'bank', 'invest', 'risk']):
        return 'finance'
    if any(w in slug_lower for w in ['food', 'cider', 'organic', 'farm', 'restaurant']):
        return 'nature'
    if any(w in slug_lower for w in ['city', 'urban', 'real estate']):
        return 'city'
    return 'abstract'


# ---------------------------------------------------------------------------
# Find hero section in HTML
# ---------------------------------------------------------------------------
def find_hero(soup):
    """Find the first hero-like section in the HTML."""
    # Strategy 1: <header> tag
    header = soup.find('header')
    if header:
        return header

    # Strategy 2: section/div with hero in class
    for tag in soup.find_all(['section', 'div']):
        classes = ' '.join(tag.get('class', []))
        if 'hero' in classes.lower():
            return tag

    # Strategy 3: first <section> in main or body
    main = soup.find('main') or soup.find('body')
    if main:
        first_section = main.find('section')
        if first_section:
            return first_section

    # Strategy 4: first direct child div of body
    body = soup.find('body')
    if body:
        for child in body.children:
            if isinstance(child, Tag) and child.name in ('div', 'section', 'header'):
                return child

    return None


# ---------------------------------------------------------------------------
# Injection: SVG Color Filter
# ---------------------------------------------------------------------------
def inject_svg_filter(soup, brand_color):
    """Inject hidden SVG with brand-tinted feColorMatrix."""
    matrix = hex_to_color_matrix(brand_color)
    svg_html = f'''<svg style="position:absolute;width:0;height:0;overflow:hidden;" aria-hidden="true">
  <defs>
    <filter id="brandTint" color-interpolation-filters="sRGB">
      <feColorMatrix type="saturate" values="0"/>
      <feColorMatrix type="matrix" values="{matrix}"/>
    </filter>
  </defs>
</svg>'''
    body = soup.find('body')
    if body:
        svg_tag = BeautifulSoup(svg_html, 'html.parser')
        body.insert(0, svg_tag)


# ---------------------------------------------------------------------------
# Injection: Video Hero
# ---------------------------------------------------------------------------
def inject_video_hero(soup, brand_color, category='abstract'):
    """Inject full-screen video background behind hero section."""
    video_url = VIDEO_LIBRARY.get(category, VIDEO_LIBRARY['abstract'])
    poster_url = POSTER_LIBRARY.get(category, POSTER_LIBRARY['abstract'])

    # Inject SVG filter
    inject_svg_filter(soup, brand_color)

    hero = find_hero(soup)
    if not hero:
        print("  WARNING: No hero section found, injecting at body start")
        hero = soup.find('body')

    # Ensure hero has relative positioning
    existing_style = hero.get('style', '')
    if 'position' not in existing_style:
        hero['style'] = f'position: relative; overflow: hidden; {existing_style}'

    # Create video background container
    video_html = f'''<div class="anim-video-bg" style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <video autoplay muted loop playsinline preload="auto"
         poster="{poster_url}"
         style="width:100%;height:100%;object-fit:cover;filter:url(#brandTint);">
    <source src="{video_url}" type="video/mp4">
  </video>
  <div style="position:absolute;inset:0;background:rgba(0,0,0,0.55);"></div>
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.7) 100%);"></div>
  <div style="position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px);"></div>
</div>'''

    video_tag = BeautifulSoup(video_html, 'html.parser')
    hero.insert(0, video_tag)

    # Make all direct children of hero position relative to stay above video
    for child in hero.children:
        if isinstance(child, Tag) and 'anim-video-bg' not in ' '.join(child.get('class', [])):
            child_style = child.get('style', '')
            if 'position' not in child_style and 'z-index' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    # Inject CSS for minimum hero height
    head = soup.find('head')
    if head:
        style_tag = soup.new_tag('style')
        style_tag.string = '''
.anim-video-bg video { transition: opacity 0.3s; }
'''
        head.append(style_tag)

    print(f"  Injected video-hero ({category} category, tinted to {brand_color})")


# ---------------------------------------------------------------------------
# Injection: Image Hero (Ken Burns on actual site image)
# ---------------------------------------------------------------------------
def inject_image_hero(soup, brand_color, image_url):
    """Inject Ken Burns animated hero using an actual image URL (not stock video).

    This replaces the stock video approach with the client's own hero image,
    animated via CSS keyframes for a cinematic Ken Burns zoom/pan effect.
    """
    # Inject SVG filter for brand tinting
    inject_svg_filter(soup, brand_color)

    hero = find_hero(soup)
    if not hero:
        print("  WARNING: No hero section found, injecting at body start")
        hero = soup.find('body')

    # Ensure hero has relative positioning
    existing_style = hero.get('style', '')
    if 'position' not in existing_style:
        hero['style'] = f'position: relative; overflow: hidden; min-height: 70vh; {existing_style}'
    elif 'min-height' not in existing_style:
        hero['style'] = f'min-height: 70vh; {existing_style}'

    # Create Ken Burns animated image background
    image_html = f'''<div class="anim-image-hero" style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <img src="{image_url}" alt="" style="width:100%;height:100%;object-fit:cover;filter:url(#brandTint);animation:animKenBurns 25s ease-in-out infinite alternate;will-change:transform;">
  <div style="position:absolute;inset:0;background:rgba(0,0,0,0.45);"></div>
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.65) 100%);"></div>
  <div style="position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.02) 2px, rgba(0,0,0,0.02) 4px);"></div>
</div>'''

    image_tag = BeautifulSoup(image_html, 'html.parser')
    hero.insert(0, image_tag)

    # Make all direct children of hero position relative to stay above image
    for child in hero.children:
        if isinstance(child, Tag) and 'anim-image-hero' not in ' '.join(child.get('class', [])):
            child_style = child.get('style', '')
            if 'position' not in child_style and 'z-index' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    # Inject Ken Burns keyframes CSS
    head = soup.find('head')
    if head:
        style_tag = soup.new_tag('style')
        style_tag.string = '''
@keyframes animKenBurns {
  0% { transform: scale(1) translate(0, 0); }
  25% { transform: scale(1.12) translate(-1.5%, -1%); }
  50% { transform: scale(1.18) translate(-2.5%, 0.5%); }
  75% { transform: scale(1.1) translate(0.5%, -1.5%); }
  100% { transform: scale(1.06) translate(1%, -0.5%); }
}
.anim-image-hero img { transition: opacity 0.5s; }
'''
        head.append(style_tag)

    print(f"  Injected image-hero (Ken Burns animation on {image_url[:80]}...)")


# ---------------------------------------------------------------------------
# Injection: Scroll Reveals
# ---------------------------------------------------------------------------
def inject_scroll_reveals(soup):
    """Add fade-in-up scroll reveals to all sections."""
    # Inject CSS
    head = soup.find('head')
    if head:
        style_tag = soup.new_tag('style')
        style_tag.string = '''
.anim-fade-in-up {
  opacity: 0;
  transform: translateY(25px);
  transition: opacity 0.8s ease, transform 0.8s ease;
}
.anim-fade-in-up.anim-visible {
  opacity: 1;
  transform: translateY(0);
}
'''
        head.append(style_tag)

    # Find all sections and add reveal class to their direct children
    delay_counter = 0
    for section in soup.find_all(['section', 'main']):
        for child in section.children:
            if isinstance(child, Tag) and child.name not in ('script', 'style', 'link'):
                existing_classes = child.get('class', [])
                if 'anim-fade-in-up' not in existing_classes:
                    child['class'] = existing_classes + ['anim-fade-in-up']
                    delay = round(0.1 * (delay_counter % 6), 1)
                    child['style'] = child.get('style', '') + f' transition-delay: {delay}s;'
                    delay_counter += 1

    # Inject IntersectionObserver JS
    body = soup.find('body')
    if body:
        script_tag = soup.new_tag('script')
        script_tag.string = '''
(function(){
  var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting) e.target.classList.add('anim-visible');
    });
  }, {threshold: 0.1});
  document.querySelectorAll('.anim-fade-in-up').forEach(function(el){ obs.observe(el); });
})();
'''
        body.append(script_tag)

    print(f"  Injected scroll-reveals ({delay_counter} elements)")


# ---------------------------------------------------------------------------
# Injection: Dot Canvas (Rhombus / Arrow)
# ---------------------------------------------------------------------------
def inject_dot_canvas(soup, shape='rhombus', target_section=None):
    """Inject Canvas 2D dot-grid animation as section background."""
    canvas_id = f'anim-dots-{shape}'

    # Find target section (default: second section or body)
    if not target_section:
        sections = soup.find_all('section')
        target_section = sections[1] if len(sections) > 1 else soup.find('body')

    if not target_section:
        print(f"  WARNING: No target section for dot-{shape}")
        return

    # Ensure relative positioning
    existing_style = target_section.get('style', '')
    if 'position' not in existing_style:
        target_section['style'] = f'position: relative; overflow: hidden; {existing_style}'

    # Canvas element
    canvas_html = f'<canvas id="{canvas_id}" style="position:absolute;inset:0;z-index:0;pointer-events:none;opacity:0.15;"></canvas>'
    canvas_tag = BeautifulSoup(canvas_html, 'html.parser')
    target_section.insert(0, canvas_tag)

    # Make children relative
    for child in target_section.children:
        if isinstance(child, Tag) and child.get('id') != canvas_id:
            child_style = child.get('style', '')
            if 'position' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    if shape == 'rhombus':
        mask_fn = "Math.abs(relX) + Math.abs(relY) < rhombusSize"
    else:  # arrow
        mask_fn = "relX > -arrowW/2 && relX < arrowW/2 && relY > relX * 0.5 && relY < -relX * 0.5 + arrowH"

    # Inject animation script
    body = soup.find('body')
    if body:
        script_tag = soup.new_tag('script')
        script_tag.string = f'''
(function(){{
  var c = document.getElementById('{canvas_id}');
  if(!c) return;
  var ctx = c.getContext('2d');
  var spacing = 18;
  var dots = [];

  function resize(){{
    c.width = c.parentElement.offsetWidth;
    c.height = c.parentElement.offsetHeight;
    dots = [];
    var cx = c.width/2, cy = c.height/2;
    var rhombusSize = Math.min(c.width, c.height) * 0.45;
    var arrowW = c.width * 0.6, arrowH = c.height * 0.8;
    for(var x=0; x<c.width; x+=spacing){{
      for(var y=0; y<c.height; y+=spacing){{
        var relX = x - cx, relY = y - cy;
        if({mask_fn}){{
          dots.push({{x:x, y:y}});
        }}
      }}
    }}
  }}
  resize();
  window.addEventListener('resize', resize);

  function animate(time){{
    ctx.clearRect(0,0,c.width,c.height);
    for(var i=0;i<dots.length;i++){{
      var d = dots[i];
      var dist = d.x + d.y;
      var wave = Math.sin(dist * 0.008 - time / 600);
      var size = 1 + (wave + 1) * 1.5;
      var opacity = 0.3 + (wave + 1) * 0.35;
      ctx.fillStyle = 'rgba(255,255,255,' + opacity + ')';
      ctx.beginPath();
      ctx.arc(d.x, d.y, size, 0, Math.PI*2);
      ctx.fill();
    }}
    requestAnimationFrame(animate);
  }}
  requestAnimationFrame(animate);
}})();
'''
        body.append(script_tag)

    print(f"  Injected dot-{shape} Canvas animation")


# ---------------------------------------------------------------------------
# Injection: Three.js Particle Torus
# ---------------------------------------------------------------------------
def inject_threejs_torus(soup, brand_color):
    """Inject Three.js particle torus knot as hero background."""
    hero = find_hero(soup)
    if not hero:
        print("  WARNING: No hero found for particle-torus")
        return

    # Ensure relative positioning
    existing_style = hero.get('style', '')
    if 'position' not in existing_style:
        hero['style'] = f'position: relative; overflow: hidden; {existing_style}'

    # Canvas container
    container_html = '<div id="anim-torus-container" style="position:absolute;inset:0;z-index:0;"></div>'
    container_tag = BeautifulSoup(container_html, 'html.parser')
    hero.insert(0, container_tag)

    # Make children relative
    for child in hero.children:
        if isinstance(child, Tag) and child.get('id') != 'anim-torus-container':
            child_style = child.get('style', '')
            if 'position' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    # Inject Three.js CDN
    head = soup.find('head')
    if head:
        script_cdn = soup.new_tag('script', src='https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js')
        head.append(script_cdn)

    # Convert brand color to hex int
    hex_int = brand_color.lstrip('#')

    body = soup.find('body')
    if body:
        script_tag = soup.new_tag('script')
        script_tag.string = f'''
(function(){{
  var container = document.getElementById('anim-torus-container');
  if(!container || typeof THREE === 'undefined') return;

  var scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x000000, 0.06);

  var w = container.offsetWidth, h = container.offsetHeight;
  var camera = new THREE.PerspectiveCamera(60, w/h, 0.1, 100);
  camera.position.z = 12;

  var renderer = new THREE.WebGLRenderer({{alpha: true, antialias: true}});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  // Generate torus knot particles
  var positions = [];
  var count = 8000;
  var p = 3, q = 4, radius = 5, tube = 1.5;
  for(var i=0; i<count; i++){{
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
  }}

  var geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

  var material = new THREE.PointsMaterial({{
    color: 0x{hex_int},
    size: 0.04,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  }});

  var points = new THREE.Points(geometry, material);
  scene.add(points);

  function animate(){{
    requestAnimationFrame(animate);
    points.rotation.x += 0.0015;
    points.rotation.y += 0.002;
    renderer.render(scene, camera);
  }}
  animate();

  window.addEventListener('resize', function(){{
    w = container.offsetWidth;
    h = container.offsetHeight;
    camera.aspect = w/h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }});
}})();
'''
        body.append(script_tag)

    print(f"  Injected Three.js particle torus (color: {brand_color})")


# ---------------------------------------------------------------------------
# Injection: HUD Overlay (populon.ai style)
# ---------------------------------------------------------------------------
def inject_hud_overlay(soup):
    """Inject HUD corner elements on hero section."""
    hero = find_hero(soup)
    if not hero:
        return

    hud_html = '''<div style="position:absolute;top:16px;left:16px;z-index:50;font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:0.25em;color:rgba(255,255,255,0.4);">
  <div>SYSTEM ONLINE</div>
</div>
<div style="position:absolute;top:16px;right:16px;z-index:50;font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:0.25em;color:rgba(255,255,255,0.4);text-align:right;">
  <div>Status: <span style="color:#22c55e;">ACTIVE</span></div>
</div>
<div style="position:absolute;bottom:16px;right:16px;z-index:50;display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
  <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:0.25em;color:rgba(255,255,255,0.3);">[SCROLL]</span>
  <div style="width:1px;height:32px;background:linear-gradient(to bottom, rgba(255,255,255,0.4), transparent);animation:pulse 2s infinite;"></div>
</div>'''

    hud_tag = BeautifulSoup(hud_html, 'html.parser')
    hero.append(hud_tag)

    # Inject JetBrains Mono font
    head = soup.find('head')
    if head:
        link_tag = soup.new_tag('link', rel='preconnect', href='https://fonts.googleapis.com')
        head.append(link_tag)
        font_tag = soup.new_tag('link', rel='stylesheet',
                                href='https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400&display=swap')
        head.append(font_tag)

    print("  Injected HUD overlay elements")


# ---------------------------------------------------------------------------
# Main: animate_static_page
# ---------------------------------------------------------------------------
def animate_static_page(input_path, effect, brand_color, output_path, video_category='abstract', hero_image=None):
    """Inject animation into existing static HTML.

    Args:
        hero_image: URL of actual hero image (for image-hero effect).
                    If provided with video-hero, uses image-hero instead.
    """
    print(f"Animating: {input_path}")
    print(f"  Effect: {effect}")
    print(f"  Brand color: {brand_color}")

    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    # Ensure <head> exists
    if not soup.find('head'):
        head_tag = soup.new_tag('head')
        html_tag = soup.find('html')
        if html_tag:
            html_tag.insert(0, head_tag)
        elif soup.find('body'):
            soup.find('body').insert_before(head_tag)

    # Apply effects
    if effect == 'image-hero':
        if not hero_image:
            print("  ERROR: --hero-image URL required for image-hero effect")
            sys.exit(1)
        inject_image_hero(soup, brand_color, hero_image)
    elif effect == 'video-hero':
        inject_video_hero(soup, brand_color, video_category)
    elif effect == 'scroll-reveals':
        inject_scroll_reveals(soup)
    elif effect == 'dot-rhombus':
        inject_dot_canvas(soup, shape='rhombus')
    elif effect == 'dot-arrow':
        inject_dot_canvas(soup, shape='arrow')
    elif effect == 'particle-torus':
        inject_threejs_torus(soup, brand_color)
    elif effect == 'cinematic-full':
        if hero_image:
            inject_image_hero(soup, brand_color, hero_image)
        else:
            inject_video_hero(soup, brand_color, video_category)
        inject_scroll_reveals(soup)
        inject_hud_overlay(soup)
        inject_dot_canvas(soup, shape='rhombus')
    else:
        print(f"  ERROR: Unknown effect '{effect}'")
        sys.exit(1)

    # Save
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    size = os.path.getsize(output_path)
    print(f"  Saved: {output_path} ({size:,} bytes)")
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Animate static HTML pages')
    parser.add_argument('--input', required=True, help='Input HTML file path')
    parser.add_argument('--effect', required=True,
                        choices=['video-hero', 'image-hero', 'scroll-reveals', 'dot-rhombus',
                                 'dot-arrow', 'particle-torus', 'cinematic-full'],
                        help='Animation effect to inject')
    parser.add_argument('--brand-color', default='#FF3B30', help='Brand hex color for tinting')
    parser.add_argument('--overlay-color', default=None, help='Override tint color (defaults to brand-color)')
    parser.add_argument('--hero-image', default=None,
                        help='URL of actual hero image (for image-hero effect, Ken Burns animation)')
    parser.add_argument('--output', help='Output file path (default: .tmp/animated/{slug}-{effect}.html)')
    parser.add_argument('--slug', help='Slug name (for deploy)')
    parser.add_argument('--video-category', default=None,
                        help='Video category: tech, abstract, nature, city, data, code, finance')
    parser.add_argument('--deploy', action='store_true', help='Deploy after generating')
    parser.add_argument('--deploy-type', default='redesign', choices=['redesign', 'landing'])

    args = parser.parse_args()

    # Auto-slug from input filename
    slug = args.slug or Path(args.input).stem
    category = args.video_category or pick_video_category(slug)

    # Default output path
    output = args.output or f'.tmp/animated/{slug}-{args.effect}.html'

    # Use overlay-color if specified, otherwise brand-color
    tint_color = args.overlay_color or args.brand_color

    result = animate_static_page(args.input, args.effect, tint_color, output, category,
                                  hero_image=args.hero_image)

    # Deploy if requested
    if args.deploy and args.slug:
        deploy_slug = f"{args.slug}"
        deploy_type = args.deploy_type
        print(f"\nDeploying as {deploy_slug}...")
        cmd = [sys.executable, 'execution/deploy_redesign.py',
               '--slug', deploy_slug,
               '--html-file', result,
               '--deploy-type', deploy_type]
        subprocess.run(cmd, cwd=os.path.dirname(os.path.dirname(__file__)) or '.')
