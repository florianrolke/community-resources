"""Turn a picture generated on pure black into a transparent cutout, trimmed to the subject, in two web sizes.

    python cutout.py source-art/jaguar.png --out site/popup-art --css-w 340
    python cutout.py source-art/canopy.png --out site/popup-art --css-w 960 --fade 0 .1 0 .1 --lo 10 --hi 60 --free

Writes <out>/<name>-1x.webp (largest display width, for normal screens), <out>/<name>.webp (double width, for sharp
screens, never larger than the original) and <out>/<name>-cutout.png (full size, for checking on a light background).
Prints one JSON line: {"name", "w", "h", "files"}. Needs: pip install opencv-python numpy scipy

How it works: the edge alpha comes from brightness (lo..hi); pixels brighter than `solid`, plus enclosed dark holes up to
`hole` pixels (hair, shadows inside a figure), are fully opaque; rim pixels that touch the true black background are
unmixed against the subject beside them, so bright subjects get no dark outline on a light page.
"""
import argparse
import json
import pathlib

import cv2
import numpy as np
from scipy import ndimage


def write_sizes(im, dest, name, css_w):
    dest.mkdir(parents=True, exist_ok=True)
    h, w = im.shape[:2]
    files = []
    for suffix, target in (("-1x", css_w), ("", 2 * css_w)):
        tw = min(w, int(target))
        small = cv2.resize(im, (tw, round(h * tw / w)), interpolation=cv2.INTER_AREA) if tw < w else im
        f = dest / f"{name}{suffix}.webp"
        cv2.imwrite(str(f), small, [cv2.IMWRITE_WEBP_QUALITY, 82])
        files.append({"file": f.name, "width": tw, "kb": f.stat().st_size // 1024})
    return files


def cutout(src, dest, name=None, fade=(0, 0, 0, 0), lo=6, hi=30, solid=14, hole=2500, free=False, crop=None, pad=4,
           grabcut=None, mass=False, sky=None, trim=0, css_w=600):
    """src: picture on pure black. fade = (top, right, bottom, left) share of the trimmed picture that fades out, for
    edges the generator cut hard. free=True keeps faint light far from the subject (stars, light rays, steam, wings).
    mass=True makes a mountain solid from its ridge line down. grabcut=(x0, y0, x1, y1) separates subject and a backdrop
    that is not pure black (studio grey, glow) by colour. sky=(ridge points [(x, y), ...], lo, hi, keep box or None)
    turns a glow above a ridge into light on black, so it only brightens the page beneath it."""
    src = pathlib.Path(src)
    name = name or src.stem
    bgr = cv2.imread(str(src), cv2.IMREAD_COLOR)
    assert bgr is not None, f"cannot read {src}"
    if crop:
        x0, y0, x1, y1 = crop
        bgr = bgr[y0:y1, x0:x1]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    lum = cv2.GaussianBlur(rgb.max(axis=2), (0, 0), 0.8)
    ramp = np.clip((lum - lo) / (hi - lo), 0, 1)
    # rim pixels next to a bright subject are a mix of subject and black: alpha = brightness relative to the subject
    # beside them. Only rim pixels touching the true background (black connected to the frame edge) are treated so.
    bgl, _ = ndimage.label(lum < 4)
    edge_ids = np.unique(np.concatenate([bgl[0], bgl[-1], bgl[:, 0], bgl[:, -1]]))
    true_bg = np.isin(bgl, edge_ids[edge_ids > 0])
    local = cv2.dilate(lum, np.ones((7, 7), np.uint8))
    rim = (local > hi) & ndimage.binary_dilation(true_bg, iterations=4)
    ramp = np.where(rim, np.clip((lum - 4) / np.maximum(local - 4, 1), 0, 1), ramp)
    core = ndimage.binary_opening(lum > solid, iterations=1)
    lab, n = ndimage.label(core)
    if n:
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        core = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 300])
    core = ndimage.binary_closing(core, iterations=2)
    holes = ndimage.binary_fill_holes(core) & ~core
    hl, hn = ndimage.label(holes)
    if hn:
        hs = ndimage.sum(holes, hl, range(1, hn + 1))
        core |= np.isin(hl, [i + 1 for i, s in enumerate(hs) if s <= hole])
    if mass:
        lab, n = ndimage.label(core)
        big = lab == (1 + int(np.argmax(ndimage.sum(core, lab, range(1, n + 1)))))
        cols = big.any(axis=0)
        top = np.argmax(big, axis=0)
        rows = np.arange(core.shape[0])[:, None]
        core |= cols[None, :] & (rows >= top[None, :])
    core = ndimage.binary_erosion(core, iterations=2 + trim)
    inner = cv2.GaussianBlur(core.astype(np.float32), (0, 0), 1.2)
    if grabcut:
        mask = np.zeros(lum.shape, np.uint8)
        x0, y0, x1, y1 = grabcut
        mask[:] = cv2.GC_BGD
        mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
        bgm, fgm = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(bgr, mask, None, bgm, fgm, 6, cv2.GC_INIT_WITH_MASK)
        fg = np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD))
        chroma = rgb.max(axis=2) - rgb.min(axis=2)
        fg &= ~((lum < solid) & (chroma < 14))
        fg = ndimage.binary_opening(fg, iterations=2)
        holes = ndimage.binary_fill_holes(fg) & ~fg
        hl, hn = ndimage.label(holes)
        if hn:
            hs = ndimage.sum(holes, hl, range(1, hn + 1))
            fg |= np.isin(hl, [i + 1 for i, s in enumerate(hs) if s <= hole])
        lab, n = ndimage.label(fg)
        if n:
            sizes = ndimage.sum(fg, lab, range(1, n + 1))
            fg = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 2000])
        alpha = cv2.GaussianBlur(fg.astype(np.float32), (0, 0), 1.4)
    elif free:
        alpha = np.maximum(ramp, inner)
    else:
        near = cv2.GaussianBlur(ndimage.binary_dilation(core, iterations=12).astype(np.float32), (0, 0), 5)
        alpha = np.maximum(ramp * near, inner)
    if sky:
        line, s_lo, s_hi, keep = sky
        hh, ww = alpha.shape
        ridge = np.interp(np.arange(ww), [p[0] for p in line], [p[1] for p in line], left=-1, right=-1)
        above = cv2.GaussianBlur((np.arange(hh)[:, None] < ridge[None, :]).astype(np.float32), (0, 0), 6)
        if keep:
            kx0, ky0, kx1, ky1 = keep
            sub = np.ascontiguousarray(bgr[ky0:ky1, kx0:kx1])
            m = np.zeros(sub.shape[:2], np.uint8)
            bgm, fgm = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
            cv2.grabCut(sub, m, (4, 4, sub.shape[1] - 8, sub.shape[0] - 8), bgm, fgm, 6, cv2.GC_INIT_WITH_RECT)
            k = np.zeros_like(above)
            k[ky0:ky1, kx0:kx1] = np.isin(m, (cv2.GC_FGD, cv2.GC_PR_FGD))
            k = cv2.GaussianBlur(k, (0, 0), 1.2)
            above *= 1 - k
            alpha = np.maximum(alpha, k)
        bright = np.clip((lum - s_lo) / (s_hi - s_lo), 0, 1)
        alpha = alpha * (1 - above) + bright * above
        floor = np.where(rim, 0.15, 0.35) * (1 - above) + 0.03 * above
    else:
        floor = np.where(rim, 0.15, 0.35).astype(np.float32)
    ys, xs = np.where(alpha > 0.03)
    assert len(ys), f"{src.name}: nothing left after the cutout; is the background pure black?"
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, alpha.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, alpha.shape[1])
    alpha, rgb, floor = alpha[y0:y1, x0:x1], rgb[y0:y1, x0:x1], floor[y0:y1, x0:x1]
    unfaded = alpha.copy()
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t, r, b, l = fade
    for share, dist in ((t, yy / h), (r, (w - 1 - xx) / w), (b, (h - 1 - yy) / h), (l, xx / w)):
        if share:
            alpha *= np.clip(dist / share, 0, 1) ** 1.3
    # colours were darkened toward black at the soft edge; lift them back so the edge carries no dark fringe
    out = np.clip(rgb / np.clip(np.where(floor < 0.3, unfaded, alpha), floor, 1)[..., None], 0, 255)
    rgba = np.dstack([out[..., ::-1], alpha * 255]).astype(np.uint8)
    dest = pathlib.Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest / f"{name}-cutout.png"), rgba)
    files = write_sizes(rgba, dest, name, css_w)
    return {"name": name, "w": w, "h": h, "files": files}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name")
    ap.add_argument("--css-w", type=int, default=600, help="widest display width in CSS pixels")
    ap.add_argument("--fade", type=float, nargs=4, default=(0, 0, 0, 0), metavar=("TOP", "RIGHT", "BOTTOM", "LEFT"))
    ap.add_argument("--lo", type=float, default=6)
    ap.add_argument("--hi", type=float, default=30)
    ap.add_argument("--solid", type=float, default=14)
    ap.add_argument("--hole", type=int, default=2500)
    ap.add_argument("--free", action="store_true")
    ap.add_argument("--mass", action="store_true")
    ap.add_argument("--trim", type=int, default=0)
    ap.add_argument("--crop", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--grabcut", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--sky", help='JSON: [[[x, y], ...], lo, hi, [x0, y0, x1, y1] or null]')
    a = ap.parse_args()
    sky = json.loads(a.sky) if a.sky else None
    print(json.dumps(cutout(a.source, a.out, a.name, tuple(a.fade), a.lo, a.hi, a.solid, a.hole, a.free, a.crop,
                            grabcut=a.grabcut, mass=a.mass, sky=sky, trim=a.trim, css_w=a.css_w)))


if __name__ == "__main__":
    main()
