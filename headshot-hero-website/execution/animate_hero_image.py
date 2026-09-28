#!/usr/bin/env python3
"""
Skill 4: Static Image → Animated HTML

Takes a static image and generates standalone HTML with a lightweight
animation effect (Ken Burns, parallax, clip-path reveal, 3D tilt,
particles, noise grain, or fade+scale).

Output: .tmp/animations/{slug}-animated.html

Usage:
    python execution/animate_hero_image.py --image path/to/image.png --effect ken-burns
    python execution/animate_hero_image.py --image path/to/image.png --effect parallax --slug example
    python execution/animate_hero_image.py --image path/to/image.png --effect 3d-tilt --deploy
"""

import os
import sys
import re
import base64
import argparse
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

ANIMATION_DIR = ".tmp/animations"

EFFECTS = {
    "ken-burns": "Slow zoom + pan (CSS keyframes, 0KB JS)",
    "parallax": "Depth effect on scroll (GSAP ScrollTrigger)",
    "clip-path": "Geometric wipe-in reveal (CSS transitions)",
    "3d-tilt": "Mouse-reactive perspective tilt (Vanilla JS, 2KB)",
    "particles": "Floating dots/lines overlay (Canvas 2D, 8KB)",
    "noise-grain": "Film grain texture overlay (CSS SVG filter, 0KB JS)",
    "fade-scale": "Entrance fade-in with scale (GSAP)",
}


def image_to_data_uri(image_path: str) -> str:
    """Convert image to base64 data URI for embedding."""
    with open(image_path, 'rb') as f:
        data = f.read()

    ext = Path(image_path).suffix.lower()
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml'}.get(ext, 'image/png')

    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def generate_ken_burns(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Animated Hero</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; overflow: hidden; height: 100vh; }}
    .ken-burns-container {{
      width: 100vw; height: 100vh; overflow: hidden; position: relative;
    }}
    .ken-burns-container img {{
      width: 100%; height: 100%; object-fit: cover;
      animation: kenBurns 20s ease-in-out infinite alternate;
      will-change: transform;
    }}
    @keyframes kenBurns {{
      0% {{ transform: scale(1) translate(0, 0); }}
      50% {{ transform: scale(1.15) translate(-2%, -1%); }}
      100% {{ transform: scale(1.08) translate(1%, -2%); }}
    }}
    .overlay {{
      position: absolute; inset: 0;
      background: linear-gradient(to bottom, transparent 40%, rgba(0,0,0,0.6));
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <div class="ken-burns-container">
    <img src="{image_src}" alt="Hero" loading="eager">
    <div class="overlay"></div>
  </div>
</body>
</html>"""


def generate_parallax(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Parallax Hero</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; color: #fff; font-family: Inter, sans-serif; }}
    .parallax-hero {{
      height: 100vh; position: relative; overflow: hidden;
    }}
    .parallax-hero img {{
      position: absolute; inset: -15% 0; width: 100%; height: 130%;
      object-fit: cover; will-change: transform;
    }}
    .parallax-overlay {{
      position: absolute; inset: 0;
      background: linear-gradient(to bottom, rgba(0,0,0,0.2), rgba(0,0,0,0.7));
    }}
    .content-below {{ height: 200vh; padding: 100px 40px; }}
    .content-below h2 {{ font-size: 3rem; margin-bottom: 1rem; }}
    .content-below p {{ font-size: 1.2rem; opacity: 0.7; max-width: 600px; line-height: 1.8; }}
  </style>
</head>
<body>
  <div class="parallax-hero">
    <img id="parallax-img" src="{image_src}" alt="Hero">
    <div class="parallax-overlay"></div>
  </div>
  <div class="content-below">
    <h2>Scroll to see the parallax effect</h2>
    <p>The hero image moves at a different speed than the content, creating depth.</p>
  </div>
  <script>
    gsap.registerPlugin(ScrollTrigger);
    gsap.to("#parallax-img", {{
      y: "20%",
      ease: "none",
      scrollTrigger: {{
        trigger: ".parallax-hero",
        start: "top top",
        end: "bottom top",
        scrub: true
      }}
    }});
  </script>
</body>
</html>"""


def generate_clip_path(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clip-Path Reveal</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; overflow: hidden; height: 100vh; display: flex; align-items: center; justify-content: center; }}
    .reveal-container {{
      width: 90vw; height: 85vh; position: relative; overflow: hidden; border-radius: 2rem;
    }}
    .reveal-container img {{
      width: 100%; height: 100%; object-fit: cover;
      clip-path: polygon(50% 50%, 50% 50%, 50% 50%, 50% 50%);
      animation: revealClip 2s cubic-bezier(0.25, 0.46, 0.45, 0.94) 0.3s forwards;
    }}
    @keyframes revealClip {{
      0% {{ clip-path: polygon(50% 50%, 50% 50%, 50% 50%, 50% 50%); }}
      50% {{ clip-path: polygon(0 0, 100% 0, 100% 50%, 0 50%); }}
      100% {{ clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%); }}
    }}
    .overlay {{
      position: absolute; inset: 0;
      background: linear-gradient(135deg, transparent 50%, rgba(0,0,0,0.4));
      pointer-events: none; border-radius: 2rem;
    }}
  </style>
</head>
<body>
  <div class="reveal-container">
    <img src="{image_src}" alt="Hero" loading="eager">
    <div class="overlay"></div>
  </div>
</body>
</html>"""


def generate_3d_tilt(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>3D Tilt Hero</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; height: 100vh; display: flex; align-items: center; justify-content: center; }}
    .tilt-card {{
      width: 85vw; max-width: 1200px; height: 75vh; border-radius: 2rem;
      overflow: hidden; position: relative;
      transform-style: preserve-3d; perspective: 1000px;
      transition: transform 0.15s ease-out;
      box-shadow: 0 40px 80px -20px rgba(0,0,0,0.5);
    }}
    .tilt-card img {{
      width: 100%; height: 100%; object-fit: cover;
    }}
    .shine {{
      position: absolute; inset: 0;
      background: radial-gradient(circle at 50% 50%, rgba(255,255,255,0.15), transparent 60%);
      pointer-events: none; opacity: 0;
      transition: opacity 0.3s ease;
    }}
    .tilt-card:hover .shine {{ opacity: 1; }}
  </style>
</head>
<body>
  <div class="tilt-card" id="tiltCard">
    <img src="{image_src}" alt="Hero">
    <div class="shine" id="shine"></div>
  </div>
  <script>
    const card = document.getElementById('tiltCard');
    const shine = document.getElementById('shine');
    card.addEventListener('mousemove', (e) => {{
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `rotateY(${{x * 12}}deg) rotateX(${{-y * 12}}deg)`;
      shine.style.background = `radial-gradient(circle at ${{(x+0.5)*100}}% ${{(y+0.5)*100}}%, rgba(255,255,255,0.2), transparent 60%)`;
    }});
    card.addEventListener('mouseleave', () => {{
      card.style.transform = 'rotateY(0) rotateX(0)';
    }});
  </script>
</body>
</html>"""


def generate_particles(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Particle Overlay</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; overflow: hidden; height: 100vh; }}
    .hero {{ position: relative; width: 100vw; height: 100vh; }}
    .hero img {{ width: 100%; height: 100%; object-fit: cover; }}
    canvas {{
      position: absolute; inset: 0; pointer-events: none;
      mix-blend-mode: screen;
    }}
    .gradient-overlay {{
      position: absolute; inset: 0;
      background: linear-gradient(to bottom, transparent 50%, rgba(0,0,0,0.6));
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <div class="hero">
    <img src="{image_src}" alt="Hero">
    <canvas id="particles"></canvas>
    <div class="gradient-overlay"></div>
  </div>
  <script>
    const canvas = document.getElementById('particles');
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const particles = Array.from({{length: 60}}, () => ({{
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2 + 0.5,
      dx: (Math.random() - 0.5) * 0.4,
      dy: (Math.random() - 0.5) * 0.4,
      o: Math.random() * 0.5 + 0.2,
    }}));
    function draw() {{
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {{
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${{p.o}})`;
        ctx.fill();
        p.x += p.dx; p.y += p.dy;
        if (p.x < 0 || p.x > canvas.width) p.dx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.dy *= -1;
      }});
      requestAnimationFrame(draw);
    }}
    draw();
    window.addEventListener('resize', () => {{
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }});
  </script>
</body>
</html>"""


def generate_noise_grain(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Noise Grain Overlay</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; overflow: hidden; height: 100vh; }}
    .hero {{ position: relative; width: 100vw; height: 100vh; }}
    .hero img {{ width: 100%; height: 100%; object-fit: cover; }}
    .noise-overlay {{
      position: absolute; inset: 0; pointer-events: none;
      background: url('data:image/svg+xml;utf8,<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/></filter><rect width="100%25" height="100%25" filter="url(%23n)"/></svg>');
      opacity: 0.08;
      mix-blend-mode: overlay;
    }}
    .vignette {{
      position: absolute; inset: 0; pointer-events: none;
      background: radial-gradient(circle at center, transparent 40%, rgba(0,0,0,0.5));
    }}
  </style>
</head>
<body>
  <div class="hero">
    <img src="{image_src}" alt="Hero">
    <div class="noise-overlay"></div>
    <div class="vignette"></div>
  </div>
</body>
</html>"""


def generate_fade_scale(image_src: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fade + Scale Entrance</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0a; overflow: hidden; height: 100vh;
           display: flex; align-items: center; justify-content: center; }}
    .hero-frame {{
      width: 90vw; max-width: 1400px; height: 85vh; border-radius: 2rem;
      overflow: hidden; position: relative;
      opacity: 0; transform: scale(0.92);
    }}
    .hero-frame img {{ width: 100%; height: 100%; object-fit: cover; }}
    .gradient {{
      position: absolute; inset: 0;
      background: linear-gradient(to top, rgba(0,0,0,0.5), transparent 60%);
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <div class="hero-frame" id="heroFrame">
    <img src="{image_src}" alt="Hero">
    <div class="gradient"></div>
  </div>
  <script>
    gsap.to("#heroFrame", {{
      opacity: 1, scale: 1,
      duration: 1.4,
      ease: "power2.out",
      delay: 0.2
    }});
  </script>
</body>
</html>"""


GENERATORS = {
    "ken-burns": generate_ken_burns,
    "parallax": generate_parallax,
    "clip-path": generate_clip_path,
    "3d-tilt": generate_3d_tilt,
    "particles": generate_particles,
    "noise-grain": generate_noise_grain,
    "fade-scale": generate_fade_scale,
}


def animate_hero_image(
    image_path: str,
    effect: str = "ken-burns",
    slug: str = None,
    output: str = None,
    embed_image: bool = True,
    deploy: bool = False,
) -> dict:
    """
    Generate animated HTML from a static image.

    Args:
        image_path: Path to the source image
        effect: Animation effect name
        slug: Optional slug for naming
        output: Optional output path override
        embed_image: If True, base64-encode image into HTML
        deploy: If True, deploy to live server

    Returns:
        dict with: html_path, effect, error
    """
    result = {"html_path": None, "effect": effect, "error": None}

    if not os.path.exists(image_path):
        result["error"] = f"Image not found: {image_path}"
        print(f"ERROR: {result['error']}")
        return result

    if effect not in GENERATORS:
        result["error"] = f"Unknown effect: {effect}. Available: {', '.join(GENERATORS.keys())}"
        print(f"ERROR: {result['error']}")
        return result

    print(f"Animating {image_path} with effect: {effect}")

    # Get image source
    if embed_image:
        image_src = image_to_data_uri(image_path)
        print(f"  Embedded image as data URI ({len(image_src)} chars)")
    else:
        image_src = image_path

    # Generate HTML
    html_content = GENERATORS[effect](image_src)

    # Determine output path
    if not slug:
        slug = Path(image_path).stem
    os.makedirs(ANIMATION_DIR, exist_ok=True)
    output_path = output or os.path.join(ANIMATION_DIR, f"{slug}-{effect}.html")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    result["html_path"] = output_path
    print(f"  Saved: {output_path}")

    # Deploy if requested
    if deploy:
        print(f"\n  Deploying {slug}-animated to live server...")
        import subprocess
        deploy_cmd = [
            sys.executable, "execution/deploy_redesign.py",
            "--slug", f"{slug}-animated",
            "--html-file", output_path,
        ]
        proc = subprocess.run(deploy_cmd, capture_output=True, text=True, timeout=300,
                              encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            print(f"  Deployed to: {slug}-animated.preview.florianrolke.com")
        else:
            print(f"  Deploy failed: {proc.stderr[:500]}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate animated HTML from a static image",
        epilog=f"Available effects: {', '.join(EFFECTS.keys())}"
    )
    parser.add_argument("--image", required=True, help="Path to source image")
    parser.add_argument("--effect", default="ken-burns", choices=list(EFFECTS.keys()),
                        help="Animation effect (default: ken-burns)")
    parser.add_argument("--slug", help="Slug for output naming")
    parser.add_argument("--output", "-o", help="Output path override")
    parser.add_argument("--no-embed", action="store_true", help="Use file path instead of base64")
    parser.add_argument("--deploy", action="store_true", help="Deploy to live server")

    args = parser.parse_args()
    result = animate_hero_image(
        image_path=args.image,
        effect=args.effect,
        slug=args.slug,
        output=args.output,
        embed_image=not args.no_embed,
        deploy=args.deploy,
    )

    if result["error"]:
        sys.exit(1)
