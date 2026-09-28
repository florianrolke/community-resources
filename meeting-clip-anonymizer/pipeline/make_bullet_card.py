"""Animated branded BULLET CARD for the client-hidden ("card") moments: animated bullets on the LEFT,
a gold vertical divider in the MIDDLE, your logo on the RIGHT. Matches the v6 dark-green/gold brand.
Used in place of the plain logo card so hidden-face moments still carry the advice. Renders an mp4 sized
to the segment; the NEWEST bullet slides+fades in (the rest are already shown) = building-list animation."""
import os, subprocess, tempfile, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

LOGO = os.environ.get("CLIP_LOGO", r"C:\Users\flori\Downloads\ChatGPT Image Jun 13, 2026, 08_19_27 PM.png")  # transparent emblem (use as-is)
W, H, FPS = 1280, 720, 30
FOREST, FOREST2 = (9, 36, 15), (6, 14, 11)
GOLD, PALEGOLD, WHITE = (201, 169, 110), (240, 214, 138), (235, 235, 230)

_BG_CACHE = None
def _bg():
    # vectorized + cached (was a pure-Python per-pixel loop -> CPU hog). Compute once, reuse every card.
    global _BG_CACHE
    if _BG_CACHE is not None:
        return _BG_CACHE.copy()
    ys = (np.arange(H) / H)[:, None, None]
    base = np.array(FOREST)[None, None, :] * (1 - ys) + np.array(FOREST2)[None, None, :] * ys  # H,1,3
    base = np.broadcast_to(base, (H, W, 3)).astype(np.float64)
    dx = ((np.arange(W) - W * 0.32) / W)[None, :]
    dy = ((np.arange(H) - H * 0.30) / H)[:, None]
    glow = (np.clip(0.07 - (dx * dx + dy * dy), 0, None) * 1.5)[:, :, None]
    out = np.clip(base + glow * (np.array(GOLD)[None, None, :] - base), 0, 255).astype(np.uint8)
    _BG_CACHE = Image.fromarray(out, "RGB").convert("RGBA")
    return _BG_CACHE.copy()

def _font(names, sz):
    for n in names:
        try: return ImageFont.truetype(n, sz)
        except Exception: pass
    return ImageFont.load_default()

def _logo(h):
    em = Image.open(LOGO).convert("RGBA")
    b = em.getbbox()
    if b: em = em.crop(b)
    return em.resize((int(em.width * h / em.height), h), Image.LANCZOS)

DIVX = 772  # divider x position

def _static(bullets, eyebrow, n_static):
    """Base layer: bg + gold divider + logo right + eyebrow + the first n_static bullets (rest animate)."""
    img = _bg()
    # gold vertical divider with soft glow
    d = ImageDraw.Draw(img)
    for w, a in ((9, 40), (5, 90), (2, 230)):
        d.line([(DIVX, 150), (DIVX, H - 150)], fill=(GOLD[0], GOLD[1], GOLD[2], a), width=w)
    d.ellipse([DIVX - 5, 146, DIVX + 5, 156], fill=(PALEGOLD[0], PALEGOLD[1], PALEGOLD[2], 255))
    d.ellipse([DIVX - 5, H - 156, DIVX + 5, H - 146], fill=(PALEGOLD[0], PALEGOLD[1], PALEGOLD[2], 255))
    # logo right (centered in right region)
    lg = _logo(230)
    img.alpha_composite(lg, (DIVX + ((W - DIVX) - lg.width) // 2, (H - lg.height) // 2 - 10))
    dd = ImageDraw.Draw(img)
    eyf = _font(["arialbd.ttf", "Arial.ttf", "DejaVuSans-Bold.ttf"], 24)
    bf = _font(["arialbd.ttf", "Arial.ttf", "DejaVuSans-Bold.ttf"], 38)
    # eyebrow top-left
    LX = 96
    dd.text((LX, 120), eyebrow.upper(), font=eyf, fill=GOLD)
    dd.rectangle([LX, 158, LX + 64, 161], fill=GOLD)
    # bullets block, vertically centered
    rows = bullets
    row_h = 92
    block_h = row_h * len(rows)
    y0 = max(200, (H - block_h) // 2 + 10)
    positions = []
    for i, b in enumerate(rows):
        y = y0 + i * row_h
        positions.append(y)
        if i >= n_static:  # these bullets animate in per-frame -> skip in static layer
            continue
        _draw_bullet(dd, img, LX, y, b, bf, 255, 0)
    return img, positions, bf, LX

def _draw_bullet(dd, img, x, y, text, bf, alpha, dx):
    gx = x + dx
    # gold diamond marker
    m = 12
    dd.polygon([(gx + 6, y + 14 - m), (gx + 6 + m, y + 14), (gx + 6, y + 14 + m), (gx + 6 - m, y + 14)],
               fill=(GOLD[0], GOLD[1], GOLD[2], alpha))
    col = (WHITE[0], WHITE[1], WHITE[2], alpha)
    # wrap text to fit left column width (~ up to DIVX-60)
    words = text.split(); line = ""; ty = y - 8
    maxw = DIVX - (x + 44) - 30
    for wd in words:
        test = (line + " " + wd).strip()
        if dd.textlength(test, font=bf) > maxw and line:
            dd.text((x + 44 + dx, ty), line, font=bf, fill=col); ty += 46; line = wd
        else: line = test
    dd.text((x + 44 + dx, ty), line, font=bf, fill=col)

def make_card_clip(bullets, dur_s, out, eyebrow="The play", n_new=1, fps=FPS):
    """Render an mp4 of duration dur_s. The first (len-n_new) bullets are already shown; the last n_new
    animate in STAGGERED across the duration (continuous motion through long hidden-face stretches)."""
    bullets = bullets[:6] or ["—"]
    n_new = max(1, min(n_new, len(bullets)))
    n_static = len(bullets) - n_new
    static, positions, bf, LX = _static(bullets, eyebrow, n_static)
    nframes = max(1, int(round(dur_s * fps)))
    anim_dur = 11  # frames per bullet reveal
    # stagger start frames for the n_new animated bullets across the clip
    starts = [int(k * max(anim_dur, (nframes - anim_dur) / max(1, n_new)) ) for k in range(n_new)]
    tmp = tempfile.mkdtemp()
    for f in range(nframes):
        frame = static.copy(); dd = ImageDraw.Draw(frame)
        for k in range(n_new):
            idx = n_static + k; ly = positions[idx]
            sf = starts[k]
            if f < sf: continue  # not yet revealed
            p = min(1.0, (f - sf) / anim_dur); p = 1 - (1 - p) * (1 - p)
            _draw_bullet(dd, frame, LX, ly, bullets[idx], bf, int(255 * p), int(-46 * (1 - p)))
        frame.convert("RGB").save(os.path.join(tmp, f"f_{f:04d}.png"))
    subprocess.run(["ffmpeg", "-y", "-threads", "2", "-framerate", str(fps), "-i", os.path.join(tmp, "f_%04d.png"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-vsync", "cfr", "-r", str(fps), "-loglevel", "error", out], check=True)
    for p_ in glob.glob(os.path.join(tmp, "*.png")): os.remove(p_)
    os.rmdir(tmp)
    return out

if __name__ == "__main__":  # quick self-test
    make_card_clip(["Not just ad spend", "We're growth partners", "Let's run the numbers"], 3.0,
                   os.path.join(os.path.dirname(__file__), "_bulletcard_test.mp4"))
    print("wrote _bulletcard_test.mp4")
