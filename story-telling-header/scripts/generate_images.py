#!/usr/bin/env python3
"""
Generate the 4 hero keyframe images from story.config.json.

Model: OpenRouter `google/gemini-3-pro-image` (Nano Banana Pro), 16:9.
Reads each scene's `image_prompt`; writes assets/hero/scene1.jpg .. scene4.jpg (<=1920px, q85).
Cost: ~$0.08/image => ~$0.32 for four. Skips images that already exist.

Usage:
  python scripts/generate_images.py                 # all four
  python scripts/generate_images.py --config path   # custom config
  python scripts/generate_images.py --force         # regenerate even if present
"""
import base64, sys, time
import requests
from _common import openrouter_key, load_config, hero_dir_for

MODEL = "google/gemini-3-pro-image"
GRADE = ("Consistent cinematic color grade across a continuous camera-ascent film sequence, "
         "photorealistic, ultra detailed, no text, no watermark, no logos. 16:9.")


def _pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        sys.exit("ERROR: Pillow is required. pip install -r requirements.txt")


def generate(key, name, prompt, ASSETS_HERO, attempt=1):
    Image = _pillow()
    print(f"  [{name}] attempt {attempt} ...", flush=True)
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [{"role": "user", "content": f"{prompt} {GRADE}"}],
                  "modalities": ["image", "text"],
                  "image_config": {"aspect_ratio": "16:9"}},
            timeout=300)
        if not r.ok:
            print(f"    HTTP {r.status_code}: {r.text[:200]}"); return False
        msg = r.json().get("choices", [{}])[0].get("message", {})
        imgs = msg.get("images") or []
        if not imgs:
            print(f"    no image returned: {str(msg)[:160]}"); return False
        url = imgs[0].get("image_url", {}).get("url", "")
        raw = base64.b64decode(url.split(",", 1)[1])
        tmp = ASSETS_HERO / f"{name}.raw"
        tmp.write_bytes(raw)
        im = Image.open(tmp).convert("RGB")
        if im.size[0] > 1920:
            im = im.resize((1920, int(im.size[1] * 1920 / im.size[0])), Image.LANCZOS)
        out = ASSETS_HERO / f"{name}.jpg"
        im.save(out, "JPEG", quality=85, optimize=True)
        tmp.unlink()
        print(f"    OK -> {out.name} ({im.size[0]}x{im.size[1]}, {out.stat().st_size // 1024} KB)")
        return True
    except Exception as e:
        print(f"    error: {e}"); return False


def main():
    key = openrouter_key()
    cfg_path = None
    force = "--force" in sys.argv
    if "--config" in sys.argv:
        cfg_path = sys.argv[sys.argv.index("--config") + 1]
    cfg = load_config(cfg_path)
    ASSETS_HERO = hero_dir_for(cfg_path)
    ASSETS_HERO.mkdir(parents=True, exist_ok=True)
    scenes = cfg["hero"]["scenes"]
    print(f"Model: {MODEL}\nOutput: {ASSETS_HERO}\n")
    failed = []
    for i, s in enumerate(scenes, 1):
        name = f"scene{i}"
        out = ASSETS_HERO / f"{name}.jpg"
        if out.exists() and not force:
            print(f"  [{name}] exists, skipping (use --force to redo)"); continue
        prompt = s.get("image_prompt", "").strip()
        if not prompt:
            print(f"  [{name}] no image_prompt, skipping"); continue
        ok = generate(key, name, prompt, ASSETS_HERO)
        if not ok:
            time.sleep(3); ok = generate(key, name, prompt, ASSETS_HERO, 2)
        if not ok:
            failed.append(name)
        time.sleep(1)
    print("\nDONE. Failed:", failed if failed else "none")
    print("Review the images in assets/hero/, then: python scripts/generate_video.py")


if __name__ == "__main__":
    main()
