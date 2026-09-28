#!/usr/bin/env python3
"""
Generate AI Video from Hero Image

Takes a static hero image (from client's website) and generates a short
animated video using AI image-to-video models. The video preserves the
original image content while adding natural motion.

Backends:
  - replicate: Kling v2.1 via Replicate (fast, good quality, ~$0.10-0.50/video)
  - veo: Google Veo 3.1 via Gemini API (best quality, $0.15/sec, 8sec = $1.20)

Usage:
    # Test with Replicate (Kling v2.1)
    python execution/generate_hero_video.py \\
      --image "https://nexgenroofing.com.au/wp-content/uploads/2022/11/1-1.jpg" \\
      --prompt "Timelapse of roof construction, workers installing metal panels" \\
      --slug nexgen-roofing \\
      --backend replicate

    # Production with Veo 3.1 (8 seconds)
    python execution/generate_hero_video.py \\
      --image "https://nexgenroofing.com.au/wp-content/uploads/2022/11/1-1.jpg" \\
      --prompt "Timelapse of roof construction, workers installing metal panels" \\
      --slug nexgen-roofing \\
      --backend veo \\
      --duration 8
"""

import os
import sys
import time
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

VIDEO_DIR = ".tmp/videos"


def download_image(url, output_path):
    """Download image from URL to local path."""
    print(f"  Downloading image: {url[:80]}...")
    resp = requests.get(url, timeout=30, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    resp.raise_for_status()
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(resp.content)
    size_kb = len(resp.content) / 1024
    print(f"  Saved: {output_path} ({size_kb:.0f}KB)")
    return output_path


def validate_and_crop_image(image_path, max_ratio=2.4):
    """Validate image aspect ratio for Kling (must be between 1:2.5 and 2.5:1).

    If outside range, center-crop to fit. Returns path to validated image.
    """
    img = Image.open(image_path)
    w, h = img.size
    ratio = w / h
    print(f"  Image size: {w}x{h} (ratio: {ratio:.2f})")

    if 1 / max_ratio <= ratio <= max_ratio:
        print(f"  Aspect ratio OK ({ratio:.2f} within [{1/max_ratio:.2f}, {max_ratio:.2f}])")
        return image_path

    # Need to crop — center-crop to max allowed ratio
    if ratio > max_ratio:
        # Too wide — crop width
        new_w = int(h * max_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
        print(f"  Cropped to {new_w}x{h} (was {w}x{h}, ratio {ratio:.2f} -> {max_ratio:.2f})")
    else:
        # Too tall — crop height
        new_h = int(w * max_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
        print(f"  Cropped to {w}x{new_h} (was {w}x{h}, ratio {ratio:.2f} -> {1/max_ratio:.2f})")

    # Save cropped version
    cropped_path = image_path.replace('.jpg', '-cropped.jpg').replace('.png', '-cropped.png')
    if cropped_path == image_path:
        cropped_path = image_path + '-cropped.jpg'
    img.save(cropped_path, quality=95)
    print(f"  Cropped image saved: {cropped_path}")
    return cropped_path


def generate_via_replicate(image_url, prompt, slug, duration=5, aspect_ratio='16:9'):
    """Generate video via Replicate Kling v2.1 image-to-video.

    Downloads image locally first to avoid 406/403 errors from source servers,
    validates aspect ratio, and uploads as file to Replicate.

    Args:
        image_url: URL of the starting image (will be downloaded locally)
        prompt: Motion description prompt
        slug: Slug name for file naming
        duration: 5 or 10 seconds
        aspect_ratio: '16:9', '9:16', or '1:1'

    Returns:
        str: URL of generated video
    """
    try:
        import replicate
    except ImportError:
        print("ERROR: pip install replicate")
        sys.exit(1)

    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        print("ERROR: REPLICATE_API_TOKEN not set in .env")
        sys.exit(1)

    client = replicate.Client(api_token=api_token)

    print(f"  Backend: Replicate (Kling v2.1)")
    print(f"  Duration: {duration}s")
    print(f"  Aspect ratio: {aspect_ratio}")
    print(f"  Prompt: {prompt[:100]}...")

    # Step 1: Download image locally (avoids 406/403 from source servers)
    os.makedirs(VIDEO_DIR, exist_ok=True)
    ext = '.jpg'
    if '.png' in image_url.lower():
        ext = '.png'
    local_image = os.path.join(VIDEO_DIR, f"{slug}-input{ext}")
    if image_url.startswith('http'):
        download_image(image_url, local_image)
    else:
        local_image = image_url

    # Step 2: Validate and crop aspect ratio if needed (Kling requires 1:2.5 to 2.5:1)
    local_image = validate_and_crop_image(local_image)

    start_time = time.time()

    # Step 3: Upload as file to Replicate
    print(f"  Uploading image to Replicate...")
    with open(local_image, 'rb') as f:
        output = client.run(
            "kwaivgi/kling-v2.1",
            input={
                "prompt": prompt,
                "start_image": f,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "cfg_scale": 0.5,
                "negative_prompt": "blurry, distorted faces, morphing, glitch, artifacts, low quality",
            }
        )

    elapsed = time.time() - start_time
    print(f"  Generated in {elapsed:.0f}s")

    # Output is typically a URL or FileOutput
    if hasattr(output, 'url'):
        video_url = output.url
    elif isinstance(output, str):
        video_url = output
    elif isinstance(output, list) and output:
        video_url = str(output[0])
    else:
        video_url = str(output)

    print(f"  Video URL: {video_url[:100]}...")
    return video_url


def generate_via_veo(image_path, prompt, duration=8, aspect_ratio='16:9', resolution='720p'):
    """Generate video via Google Veo 3.1 image-to-video.

    Args:
        image_path: Local path to image file
        prompt: Motion description prompt
        duration: 4, 6, or 8 seconds
        aspect_ratio: '16:9' or '9:16'
        resolution: '720p' or '1080p'

    Returns:
        str: Local path to saved MP4 video
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("ERROR: pip install google-genai")
        sys.exit(1)

    api_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_GEMINI_API_KEY not set in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print(f"  Backend: Google Veo 3.1")
    print(f"  Duration: {duration}s")
    print(f"  Resolution: {resolution}")
    print(f"  Cost estimate: ${0.15 * duration:.2f} (Fast) / ${0.40 * duration:.2f} (Standard)")
    print(f"  Prompt: {prompt[:100]}...")

    start_time = time.time()

    # Load image
    image = types.Image.from_file(image_path)

    # Generate video
    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        image=image,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            duration_seconds=str(duration),
        ),
    )

    # Poll for completion
    poll_count = 0
    while not operation.done:
        poll_count += 1
        elapsed = time.time() - start_time
        print(f"  Waiting... ({elapsed:.0f}s, poll #{poll_count})")
        time.sleep(10)
        operation = client.operations.get(operation)

    elapsed = time.time() - start_time
    print(f"  Generated in {elapsed:.0f}s")

    # Save video
    video = operation.response.generated_videos[0]
    os.makedirs(VIDEO_DIR, exist_ok=True)
    output_path = os.path.join(VIDEO_DIR, f"veo-output-{int(time.time())}.mp4")
    client.files.download(file=video.video)
    video.video.save(output_path)

    print(f"  Saved: {output_path}")
    return output_path


def generate_hero_video(
    image_url,
    prompt,
    slug,
    backend='replicate',
    duration=5,
    aspect_ratio='16:9',
    resolution='720p',
):
    """Generate a hero video from an image URL.

    Returns:
        dict with video_url, video_path, metadata
    """
    os.makedirs(VIDEO_DIR, exist_ok=True)

    result = {
        'slug': slug,
        'image_url': image_url,
        'prompt': prompt,
        'backend': backend,
        'video_url': None,
        'video_path': None,
    }

    print(f"\n{'='*60}")
    print(f"  HERO VIDEO GENERATION")
    print(f"  Slug: {slug}")
    print(f"  Backend: {backend}")
    print(f"{'='*60}\n")

    if backend == 'replicate':
        video_url = generate_via_replicate(image_url, prompt, slug, duration, aspect_ratio)
        result['video_url'] = video_url

        # Download the video locally
        video_path = os.path.join(VIDEO_DIR, f"{slug}-hero.mp4")
        print(f"  Downloading video...")
        resp = requests.get(video_url, timeout=120)
        resp.raise_for_status()
        with open(video_path, 'wb') as f:
            f.write(resp.content)
        size_mb = len(resp.content) / (1024 * 1024)
        print(f"  Saved: {video_path} ({size_mb:.1f}MB)")
        result['video_path'] = video_path

    elif backend == 'veo':
        # Veo needs a local image file
        local_image = os.path.join(VIDEO_DIR, f"{slug}-input.jpg")
        if image_url.startswith('http'):
            download_image(image_url, local_image)
        else:
            local_image = image_url

        video_path = generate_via_veo(local_image, prompt, duration, aspect_ratio, resolution)
        result['video_path'] = video_path

    # Save metadata
    meta_path = os.path.join(VIDEO_DIR, f"{slug}-video-meta.json")
    result['timestamp'] = datetime.now().isoformat()
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  VIDEO GENERATION COMPLETE")
    if result.get('video_url'):
        print(f"  URL: {result['video_url'][:80]}...")
    if result.get('video_path'):
        print(f"  Local: {result['video_path']}")
    print(f"{'='*60}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate AI video from hero image (Replicate Kling or Google Veo 3.1)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with Replicate (Kling v2.1, ~$0.10-0.50)
  python execution/generate_hero_video.py \\
    --image "https://example.com/hero.jpg" \\
    --prompt "Subtle motion, people celebrating" \\
    --slug example --backend replicate --duration 5

  # Production with Veo 3.1 (8 seconds, ~$1.20)
  python execution/generate_hero_video.py \\
    --image "https://example.com/hero.jpg" \\
    --prompt "Cinematic motion" \\
    --slug example --backend veo --duration 8
        """
    )

    parser.add_argument('--image', required=True, help='Hero image URL (must be publicly accessible)')
    parser.add_argument('--prompt', required=True, help='Motion description prompt')
    parser.add_argument('--slug', required=True, help='Slug for output naming')
    parser.add_argument('--backend', default='replicate', choices=['replicate', 'veo'],
                        help='Backend: replicate (Kling v2.1) or veo (Veo 3.1)')
    parser.add_argument('--duration', type=int, default=5, help='Video duration in seconds (5 or 10 for Kling, 4/6/8 for Veo)')
    parser.add_argument('--aspect-ratio', default='16:9', choices=['16:9', '9:16', '1:1'],
                        help='Aspect ratio (default: 16:9)')
    parser.add_argument('--resolution', default='720p', choices=['720p', '1080p'],
                        help='Resolution (default: 720p)')

    args = parser.parse_args()

    result = generate_hero_video(
        image_url=args.image,
        prompt=args.prompt,
        slug=args.slug,
        backend=args.backend,
        duration=args.duration,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
    )

    if result.get('video_path') or result.get('video_url'):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
