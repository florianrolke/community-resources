#!/usr/bin/env python3
"""
Inject premium animations into static HTML pages.

Takes any HTML file and layers cinematic effects:
  - video-hero:      Full-screen brand-tinted stock video behind hero
  - image-hero:      Ken Burns animated hero using client's own image
  - scroll-reveals:  Fade-in-up on all sections via IntersectionObserver
  - dot-rhombus:     Canvas 2D shimmering diamond dot-grid
  - particle-torus:  Three.js rotating particle torus knot
  - cinematic-full:  All of the above (populon.ai treatment)

Usage:
    python website/animate_page.py --input page.html --effect video-hero --brand-color "#09240F"
    python website/animate_page.py --input page.html --effect cinematic-full --brand-color "#1a1a2e" --output animated.html
    python website/animate_page.py --input page.html --effect image-hero --hero-image "https://example.com/hero.jpg" --brand-color "#c4842a"
"""

import os
import sys
import argparse

# Windows UTF-8 fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    print("ERROR: beautifulsoup4 required. Run: pip install beautifulsoup4")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Video & Poster Libraries (free Pexels stock)
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
# Utilities
# ---------------------------------------------------------------------------
def hex_to_color_matrix(hex_color):
    """Convert hex color to SVG feColorMatrix values for monotone brand tinting."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (f"{r:.2f} 0 0 0 {1-r:.2f} "
            f"{g:.2f} 0 0 0 {1-g:.2f} "
            f"{b:.2f} 0 0 0 {1-b:.2f} "
            f"0 0 0 1 0")


def pick_video_category(slug):
    """Guess video category from slug keywords."""
    slug_lower = slug.lower()
    categories = {
        'tech':    ['tech', 'ai', 'saas', 'software', 'digital', 'cloud', 'automation'],
        'finance': ['finance', 'capital', 'invest', 'bank', 'wealth', 'fund'],
        'nature':  ['organic', 'farm', 'garden', 'green', 'eco', 'natural'],
        'city':    ['city', 'urban', 'metro', 'downtown'],
        'code':    ['code', 'dev', 'program', 'engineer'],
        'data':    ['data', 'analytics', 'dashboard'],
    }
    for cat, keywords in categories.items():
        if any(kw in slug_lower for kw in keywords):
            return cat
    return 'abstract'  # default


def find_hero(soup):
    """Find the hero section using 4 fallback strategies."""
    # Strategy 1: <header> tag
    header = soup.find('header')
    if header:
        return header

    # Strategy 2: element with 'hero' in class
    hero = soup.find(class_=lambda c: c and 'hero' in c.lower() if isinstance(c, str) else
                     any('hero' in cls.lower() for cls in c) if isinstance(c, list) else False)
    if hero:
        return hero

    # Strategy 3: first <section>
    first_section = soup.find('section')
    if first_section:
        return first_section

    # Strategy 4: first child div of body
    body = soup.find('body')
    if body:
        for child in body.children:
            if isinstance(child, Tag) and child.name == 'div':
                return child

    return body


def ensure_head(soup):
    """Ensure <head> tag exists."""
    if not soup.find('head'):
        head_tag = soup.new_tag('head')
        html_tag = soup.find('html')
        if html_tag:
            html_tag.insert(0, head_tag)
        elif soup.find('body'):
            soup.find('body').insert_before(head_tag)


# ---------------------------------------------------------------------------
# Injection: SVG Color Filter
# ---------------------------------------------------------------------------
def inject_svg_filter(soup, brand_color):
    """Inject hidden SVG with feColorMatrix for brand tinting."""
    matrix = hex_to_color_matrix(brand_color)
    svg_html = f'''<svg style="position:absolute;width:0;height:0;" aria-hidden="true">
  <filter id="anim-brand-tint">
    <feColorMatrix type="matrix" values="{matrix}"/>
  </filter>
</svg>'''
    body = soup.find('body')
    if body:
        svg_tag = BeautifulSoup(svg_html, 'html.parser')
        body.insert(0, svg_tag)


# ---------------------------------------------------------------------------
# Injection: Video Hero
# ---------------------------------------------------------------------------
def inject_video_hero(soup, brand_color, category='abstract'):
    """Inject full-screen brand-tinted stock video behind the hero."""
    hero = find_hero(soup)
    if not hero:
        print("  WARNING: No hero found for video-hero")
        return

    # Inject SVG filter first
    inject_svg_filter(soup, brand_color)

    # Ensure hero has relative positioning
    existing_style = hero.get('style', '')
    if 'position' not in existing_style:
        hero['style'] = f'position: relative; overflow: hidden; {existing_style}'

    video_url = VIDEO_LIBRARY.get(category, VIDEO_LIBRARY['abstract'])
    poster_url = POSTER_LIBRARY.get(category, POSTER_LIBRARY['abstract'])

    # Video + triple overlay
    video_html = f'''<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <video autoplay muted loop playsinline poster="{poster_url}"
    style="width:100%;height:100%;object-fit:cover;filter:url(#anim-brand-tint) saturate(0.8) brightness(0.6);">
    <source src="{video_url}" type="video/mp4"/>
  </video>
  <div style="position:absolute;inset:0;background:rgba(0,0,0,0.55);"></div>
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.6) 100%);"></div>
  <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);pointer-events:none;"></div>
</div>'''

    video_tag = BeautifulSoup(video_html, 'html.parser')
    hero.insert(0, video_tag)

    # Make all hero children relative
    for child in hero.children:
        if isinstance(child, Tag):
            child_style = child.get('style', '')
            if 'position' not in child_style and 'absolute' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    print(f"  Injected video-hero ({category}, brand: {brand_color})")


# ---------------------------------------------------------------------------
# Injection: Image Hero (Ken Burns)
# ---------------------------------------------------------------------------
def inject_image_hero(soup, brand_color, image_url):
    """Inject Ken Burns animated hero with client's own image."""
    hero = find_hero(soup)
    if not hero:
        print("  WARNING: No hero found for image-hero")
        return

    # Inject SVG filter
    inject_svg_filter(soup, brand_color)

    existing_style = hero.get('style', '')
    if 'position' not in existing_style:
        hero['style'] = f'position: relative; overflow: hidden; {existing_style}'

    # Inject CSS keyframes
    head = soup.find('head')
    if head:
        style_tag = soup.new_tag('style')
        style_tag.string = '''
@keyframes animKenBurns {
  0%   { transform: scale(1) translate(0, 0); }
  50%  { transform: scale(1.12) translate(-2%, 1%); }
  100% { transform: scale(1.18) translate(1%, -1%); }
}
'''
        head.append(style_tag)

    # Image + overlays
    img_html = f'''<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <img src="{image_url}" alt=""
    style="width:100%;height:100%;object-fit:cover;animation:animKenBurns 25s infinite alternate ease-in-out;filter:url(#anim-brand-tint) saturate(0.8) brightness(0.6);" />
  <div style="position:absolute;inset:0;background:rgba(0,0,0,0.55);"></div>
  <div style="position:absolute;inset:0;background:radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.6) 100%);"></div>
  <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);pointer-events:none;"></div>
</div>'''

    img_tag = BeautifulSoup(img_html, 'html.parser')
    hero.insert(0, img_tag)

    # Make children relative
    for child in hero.children:
        if isinstance(child, Tag):
            child_style = child.get('style', '')
            if 'position' not in child_style and 'absolute' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    print(f"  Injected image-hero (Ken Burns, brand: {brand_color})")


# ---------------------------------------------------------------------------
# Injection: Scroll Reveals
# ---------------------------------------------------------------------------
def inject_scroll_reveals(soup):
    """Inject fade-in-up animations on all sections."""
    # Add CSS
    head = soup.find('head')
    if head:
        style_tag = soup.new_tag('style')
        style_tag.string = '''
.anim-fade-in-up {
  opacity: 0;
  transform: translateY(25px);
  transition: opacity 0.7s ease-out, transform 0.7s ease-out;
}
.anim-fade-in-up.anim-visible {
  opacity: 1;
  transform: translateY(0);
}
'''
        head.append(style_tag)

    # Add class to all sections + major elements
    delay_counter = 0
    delays = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

    for section in soup.find_all(['section', 'article']):
        classes = section.get('class', [])
        if isinstance(classes, str):
            classes = classes.split()
        if 'anim-fade-in-up' not in classes:
            classes.append('anim-fade-in-up')
            section['class'] = classes
            delay = delays[delay_counter % len(delays)]
            existing = section.get('style', '')
            section['style'] = f'transition-delay: {delay}s; {existing}'
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
def inject_dot_canvas(soup, shape='rhombus'):
    """Inject Canvas 2D dot-grid animation as section background."""
    canvas_id = f'anim-dots-{shape}'

    # Find target (second section or body)
    sections = soup.find_all('section')
    target = sections[1] if len(sections) > 1 else soup.find('body')
    if not target:
        print(f"  WARNING: No target section for dot-{shape}")
        return

    # Ensure relative positioning
    existing_style = target.get('style', '')
    if 'position' not in existing_style:
        target['style'] = f'position: relative; overflow: hidden; {existing_style}'

    # Canvas element
    canvas_html = f'<canvas id="{canvas_id}" style="position:absolute;inset:0;z-index:0;pointer-events:none;opacity:0.15;"></canvas>'
    canvas_tag = BeautifulSoup(canvas_html, 'html.parser')
    target.insert(0, canvas_tag)

    # Make children relative
    for child in target.children:
        if isinstance(child, Tag) and child.get('id') != canvas_id:
            child_style = child.get('style', '')
            if 'position' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    if shape == 'rhombus':
        mask_fn = "Math.abs(relX) + Math.abs(relY) < rhombusSize"
    else:
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

    existing_style = hero.get('style', '')
    if 'position' not in existing_style:
        hero['style'] = f'position: relative; overflow: hidden; {existing_style}'

    # Container
    container_html = '<div id="anim-torus-container" style="position:absolute;inset:0;z-index:0;"></div>'
    container_tag = BeautifulSoup(container_html, 'html.parser')
    hero.insert(0, container_tag)

    # Make children relative
    for child in hero.children:
        if isinstance(child, Tag) and child.get('id') != 'anim-torus-container':
            child_style = child.get('style', '')
            if 'position' not in child_style:
                child['style'] = f'position: relative; z-index: 1; {child_style}'

    # Three.js CDN
    head = soup.find('head')
    if head:
        script_cdn = soup.new_tag('script', src='https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js')
        head.append(script_cdn)

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
# Main: animate_page
# ---------------------------------------------------------------------------
def animate_page(input_path, effect, brand_color, output_path,
                 video_category=None, hero_image=None):
    """Inject animation into existing static HTML.

    Args:
        input_path: Path to input HTML file
        effect: One of: video-hero, image-hero, scroll-reveals, dot-rhombus,
                dot-arrow, particle-torus, cinematic-full
        brand_color: Hex color for brand tinting (e.g., "#09240F")
        output_path: Where to save the animated HTML
        video_category: Override auto-detection (tech, abstract, nature, city, etc.)
        hero_image: URL for image-hero effect
    """
    print(f"Animating: {input_path}")
    print(f"  Effect: {effect}")
    print(f"  Brand color: {brand_color}")

    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    ensure_head(soup)

    # Determine video category
    slug = os.path.splitext(os.path.basename(input_path))[0]
    category = video_category or pick_video_category(slug)

    # Apply effects
    if effect == 'image-hero':
        if not hero_image:
            print("  ERROR: --hero-image URL required for image-hero effect")
            sys.exit(1)
        inject_image_hero(soup, brand_color, hero_image)
    elif effect == 'video-hero':
        inject_video_hero(soup, brand_color, category)
    elif effect == 'scroll-reveals':
        inject_scroll_reveals(soup)
    elif effect == 'dot-rhombus':
        inject_dot_canvas(soup, shape='rhombus')
    elif effect == 'dot-arrow':
        inject_dot_canvas(soup, shape='arrow')
    elif effect == 'particle-torus':
        inject_threejs_torus(soup, brand_color)
    elif effect == 'cinematic-full':
        # The full populon.ai treatment
        if hero_image:
            inject_image_hero(soup, brand_color, hero_image)
        else:
            inject_video_hero(soup, brand_color, category)
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
def main():
    parser = argparse.ArgumentParser(description='Animate static HTML pages with cinematic effects')
    parser.add_argument('--input', required=True, help='Input HTML file path')
    parser.add_argument('--effect', required=True,
                        choices=['video-hero', 'image-hero', 'scroll-reveals', 'dot-rhombus',
                                 'dot-arrow', 'particle-torus', 'cinematic-full'],
                        help='Animation effect to inject')
    parser.add_argument('--brand-color', default='#FF3B30', help='Brand hex color for tinting')
    parser.add_argument('--hero-image', help='Image URL for image-hero effect (Ken Burns)')
    parser.add_argument('--output', help='Output file path (default: .tmp/animated/{slug}-{effect}.html)')
    parser.add_argument('--video-category', choices=list(VIDEO_LIBRARY.keys()),
                        help='Override auto-detected video category')

    args = parser.parse_args()

    # Default output path
    slug = os.path.splitext(os.path.basename(args.input))[0]
    output = args.output or f'.tmp/animated/{slug}-{args.effect}.html'

    animate_page(
        args.input, args.effect, args.brand_color, output,
        video_category=args.video_category,
        hero_image=args.hero_image,
    )


if __name__ == '__main__':
    main()
