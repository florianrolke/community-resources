#!/usr/bin/env python3
"""
Animate the 4 keyframes into one scroll-scrub video (assets/hero/ascent.mp4).

Model: OpenRouter `alibaba/happyhorse-1.1` image-to-video (POST /api/v1/videos), one 5s clip
per scene using the scene's `motion_prompt`, then ffmpeg xfade-stitched and encoded for
scrubbing (GOP-4, faststart). Cost: 4 x ~$0.639 = ~$2.56. Checkpointed/resumable.

Requires: ffmpeg on PATH.

Usage:
  python scripts/generate_video.py                # generate all clips + stitch
  python scripts/generate_video.py 1              # just clip 1 (probe)
  python scripts/generate_video.py stitch         # (re)stitch existing clips
  python scripts/generate_video.py --config path
"""
import base64, json, subprocess, sys, time
import requests
from _common import openrouter_key, load_config, hero_dir_for

MODEL = "alibaba/happyhorse-1.1"
DURATION, RESOLUTION = 5, "1080p"
# set in main() from the config location
ASSETS_HERO = None
CKPT = None
TAIL = ("Style: photorealistic live-action, seamless motion, no scene change, no cuts, "
        "no camera shake, no morphing, consistent cinematic grade.")


def ck_load():
    return json.loads(CKPT.read_text(encoding="utf-8")) if CKPT.exists() else {}


def ck_save(d):
    CKPT.write_text(json.dumps(d, indent=2), encoding="utf-8")


def data_url(name):
    return "data:image/jpeg;base64," + base64.b64encode((ASSETS_HERO / f"{name}.jpg").read_bytes()).decode()


def submit(key, prompt, img):
    return requests.post(
        "https://openrouter.ai/api/v1/videos",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": MODEL, "prompt": prompt, "duration": DURATION,
              "resolution": RESOLUTION, "aspect_ratio": "16:9",
              "frame_images": [{"type": "image_url", "image_url": {"url": img},
                                "frame_type": "first_frame"}]},
        timeout=120)


def poll(key, job, out):
    t0 = time.time()
    while time.time() - t0 < 900:
        d = requests.get(job["polling_url"], headers={"Authorization": f"Bearer {key}"}, timeout=60).json()
        st = d.get("status")
        print(f"    {st} ({int(time.time() - t0)}s)")
        if st == "completed":
            urls = d.get("unsigned_urls") or []
            dl = urls[0] if urls else f"https://openrouter.ai/api/v1/videos/{job['id']}/content?index=0"
            out.write_bytes(requests.get(dl, headers={"Authorization": f"Bearer {key}"}, timeout=300).content)
            print(f"    saved {out.name} ({out.stat().st_size // 1024} KB)")
            return True
        if st in ("failed", "cancelled", "expired"):
            print(f"    FAILED {json.dumps(d)[:300]}"); return False
        time.sleep(10)
    return False


def gen(key, i, scene):
    name, prompt = f"clip{i}", (scene.get("motion_prompt", "").strip() + " " + TAIL).strip()
    src = ASSETS_HERO / f"scene{i}.jpg"
    if not src.exists():
        sys.exit(f"ERROR: {src.name} missing. Run scripts/generate_images.py first.")
    out = ASSETS_HERO / f"{name}.mp4"
    if out.exists():
        print(f"[{name}] exists"); return
    print(f"[{name}] {DURATION}s {RESOLUTION}")
    ck = ck_load()
    if str(i) not in ck:
        r = submit(key, prompt, data_url(f"scene{i}"))
        if not r.ok:
            print(f"    submit {r.status_code}: {r.text[:200]}"); return
        j = r.json(); ck[str(i)] = {"id": j.get("id"), "polling_url": j.get("polling_url")}
        ck_save(ck); print(f"    job {j.get('id')}")
    poll(key, ck[str(i)], out)


def stitch():
    clips = [ASSETS_HERO / f"clip{i}.mp4" for i in (1, 2, 3, 4)]
    missing = [c.name for c in clips if not c.exists()]
    if missing:
        sys.exit(f"missing clips: {missing}")
    fc = ("[0:v]scale=1280:720,fps=24,setsar=1[v0];[1:v]scale=1280:720,fps=24,setsar=1[v1];"
          "[2:v]scale=1280:720,fps=24,setsar=1[v2];[3:v]scale=1280:720,fps=24,setsar=1[v3];"
          "[v0][v1]xfade=transition=fade:duration=0.45:offset=4.59[x1];"
          "[x1][v2]xfade=transition=fade:duration=0.45:offset=9.18[x2];"
          "[x2][v3]xfade=transition=fade:duration=0.45:offset=13.77[vout]")
    out = ASSETS_HERO / "ascent.mp4"
    cmd = ["ffmpeg", "-y", *sum([["-i", str(c)] for c in clips], []),
           "-filter_complex", fc, "-map", "[vout]", "-an", "-c:v", "libx264", "-preset", "slow",
           "-crf", "23", "-g", "4", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(out)]
    print("stitching -> ascent.mp4 ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr[-800:])
    print(f"OK ascent.mp4 ({out.stat().st_size // 1024} KB)  ->  now: python scripts/build.py")


def main():
    global ASSETS_HERO, CKPT
    cfg_path = None
    if "--config" in sys.argv:
        cfg_path = sys.argv[sys.argv.index("--config") + 1]
    ASSETS_HERO = hero_dir_for(cfg_path)
    CKPT = ASSETS_HERO / ".happyhorse_jobs.json"
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != cfg_path]
    if args == ["stitch"]:
        stitch(); return
    key = openrouter_key()
    cfg = load_config(cfg_path)
    scenes = cfg["hero"]["scenes"]
    targets = [int(a) for a in args] if args else [1, 2, 3, 4]
    ASSETS_HERO.mkdir(parents=True, exist_ok=True)
    for i in targets:
        gen(key, i, scenes[i - 1]); time.sleep(1)
    if targets == [1, 2, 3, 4]:
        stitch()


if __name__ == "__main__":
    main()
