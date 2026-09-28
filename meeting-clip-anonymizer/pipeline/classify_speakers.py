"""Speaker diarization for Zoom speaker-view recordings via on-screen name label.

No pyannote/HF needed. The recording switches to the active speaker full-screen and
burns a bottom-left name label (e.g. "Person A" vs "personb"). We classify each
1fps label crop against two reference crops using a white-text binary mask + normalized
cross-correlation, smooth, then build a speaker timeline. If a whisper transcript is
present, each segment is assigned the majority speaker over its time window.
HOST = you (kept on camera); OTHER = the participant to anonymize (face hidden, voice shifted).
"""
import argparse
import glob
import json
import os
import re

import numpy as np
from PIL import Image

LABEL_BOX = (0, 670, 280, 720)  # crop region in full 1280x720 frame
TEXT_COLS = slice(58, 230)      # focus on the name text, drop far-left icon/empty
WHITE_T = 175                   # white-text threshold on grayscale


def text_mask(gray: np.ndarray) -> np.ndarray:
    """Binary mask of bright label text within the text columns."""
    m = (gray[:, TEXT_COLS] > WHITE_T).astype(np.float32)
    return m


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    af, bf = a.ravel(), b.ravel()
    na, nb = np.linalg.norm(af), np.linalg.norm(bf)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    return float(np.dot(af, bf) / (na * nb))


def load_label_gray(path: str, is_full_frame: bool) -> np.ndarray:
    im = Image.open(path).convert("L")
    if is_full_frame:
        im = im.crop(LABEL_BOX)
    return np.asarray(im, dtype=np.float32)


def classify(gray: np.ndarray, ref_f: np.ndarray, ref_d: np.ndarray):
    m = text_mask(gray)
    white = float(m.sum())
    if white < 20:  # essentially no label text visible
        return "unknown", 0.0, 0.0, white
    sf = ncc(m, text_mask_ref(ref_f))
    sd = ncc(m, text_mask_ref(ref_d))
    if max(sf, sd) < 0.18:
        return "unknown", sf, sd, white
    return ("HOST" if sf >= sd else "OTHER"), sf, sd, white


# cache reference masks
_REF_CACHE = {}
def text_mask_ref(ref_gray: np.ndarray) -> np.ndarray:
    key = id(ref_gray)
    if key not in _REF_CACHE:
        _REF_CACHE[key] = text_mask(ref_gray)
    return _REF_CACHE[key]


def median_smooth(labels, k=3):
    out = list(labels)
    half = k // 2
    for i in range(len(labels)):
        lo, hi = max(0, i - half), min(len(labels), i + half + 1)
        window = [labels[j] for j in range(lo, hi) if labels[j] != "unknown"]
        if window:
            out[i] = max(set(window), key=window.count)
    return out


def build_segments(per_sec, min_dur=1):
    segs = []
    if not per_sec:
        return segs
    cur = per_sec[0]
    start = 0
    for t in range(1, len(per_sec)):
        if per_sec[t] != cur:
            segs.append({"start": start, "end": t, "speaker": cur})
            cur = per_sec[t]
            start = t
    segs.append({"start": start, "end": len(per_sec), "speaker": cur})
    return [s for s in segs if (s["end"] - s["start"]) >= min_dur or s["speaker"] != "unknown"]


def assign_segment_speaker(per_sec, start, end):
    lo, hi = int(round(start)), int(round(end))
    hi = max(hi, lo + 1)
    votes = [per_sec[t] for t in range(lo, min(hi, len(per_sec))) if t < len(per_sec)]
    votes = [v for v in votes if v != "unknown"] or votes
    if not votes:
        return "unknown"
    return max(set(votes), key=votes.count)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels-dir", required=True)
    ap.add_argument("--ref-host", required=True, help="full frame where the HOST is shown")
    ap.add_argument("--ref-other", required=True, help="full frame where the OTHER person is shown")
    ap.add_argument("--transcript", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ref_f = load_label_gray(args.ref_host, is_full_frame=True)
    ref_d = load_label_gray(args.ref_other, is_full_frame=True)

    crops = sorted(glob.glob(os.path.join(args.labels_dir, "lbl_*.jpg")))
    per_sec = []
    diag = []
    for idx, path in enumerate(crops):
        g = load_label_gray(path, is_full_frame=False)
        lab, sf, sd, white = classify(g, ref_f, ref_d)
        per_sec.append(lab)
        diag.append({"t": idx, "label": lab, "sf": round(sf, 3), "sd": round(sd, 3), "white": white})

    per_sec = median_smooth(per_sec, k=5)

    n = len(per_sec)
    cnt = {"HOST": per_sec.count("HOST"), "OTHER": per_sec.count("OTHER"), "unknown": per_sec.count("unknown")}
    segs = build_segments(per_sec, min_dur=2)

    result = {
        "seconds": n,
        "counts_sec": cnt,
        "video_segments": segs,
    }

    if args.transcript and os.path.exists(args.transcript):
        tr = json.loads(open(args.transcript, encoding="utf-8").read())
        out_segs = []
        for s in tr["segments"]:
            spk = assign_segment_speaker(per_sec, s["start"], s["end"])
            out_segs.append({"start": s["start"], "end": s["end"], "speaker": spk, "text": s["text"]})
        result["transcript"] = out_segs

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # readable diarized transcript
    if "transcript" in result:
        lines = []
        for s in result["transcript"]:
            mm = int(s["start"] // 60); ss = int(s["start"] % 60)
            lines.append(f"[{mm:02d}:{ss:02d}] {s['speaker']}: {s['text']}")
        open(os.path.splitext(args.out)[0] + ".txt", "w", encoding="utf-8").write("\n".join(lines))

    print(json.dumps({"seconds": n, "counts_sec": cnt, "num_video_segments": len(segs)}, indent=2))
    # print a sanity sample of diagnostics every ~300s
    for d in diag[::300]:
        print(d)


if __name__ == "__main__":
    main()
