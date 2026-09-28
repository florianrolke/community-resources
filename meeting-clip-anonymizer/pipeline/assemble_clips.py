"""Recorded call -> per-clip base. HOST-vs-client (on-screen label): HOST=face (bar-cropped),
client=B-roll (quick ~3s cuts) + voice anonymized (pitch). VAD silence-trim + PII bleep + word remap.
Usage: python assemble_impromptu.py <clipname>   (clipname from CLIPS)."""
import json, os, subprocess, sys, wave, importlib.util, glob
import numpy as np
BASE = os.path.dirname(__file__)
# Paths are env-overridable so this runs UNCHANGED on the cloud box (set CLIP_* env vars there).
SRC = os.environ.get("CLIP_SRC", "recording.mp4")
BG = os.environ.get("CLIP_BG", os.path.join(BASE, "assets", "branded_bg.png"))  # logo card
BROLL = os.environ.get("CLIP_BROLL", os.path.join(BASE, "broll"))
VAD = os.environ.get("CLIP_VAD", r"C:\Users\flori\OneDrive\Dokumente\Agentic Workflows\Agentic Workflows-Nick Saraev\AgentZero - Cuts\execution\skills\silence_removal.py")
FPS, W, H = 30, 1280, 720
TR = json.load(open(os.path.join(BASE, "transcript.json"), encoding="utf-8"))
WORDS = [w for w in TR["words"] if w.get("start") is not None]
CLIENT_PITCH = 0.82  # anonymize clients' voices: LOWER pitch (deeper, ~0.82x f0) - not childlike. Clearly audible.
_civ = os.path.join(BASE, "client_intervals.json")
CLIENT_IV = json.load(open(_civ))["client_intervals"] if os.path.exists(_civ) else []
def client_frac(a, b):  # fraction of [a,b] that is a client speaking (pyannote-diarized)
    ov = sum(max(0.0, min(b, y) - max(a, x)) for x, y in CLIENT_IV)
    return ov / (b - a) if b > a else 0.0
# PII to bleep (audio mute + caption mask). Put the names / places / companies from YOUR call here, lowercase.
BLEEP = {"example-firstname", "example-company", "example-city"}
DEFAULT_BROLL = {
    "trust": ["business-handshake-deal", "business-coffee-meeting", "two-people-talking-cafe"],
    "outreach": ["person-typing-laptop", "social-media-marketing-phone", "marketing-team-office-meeting"],
    "casestudy": ["business-coffee-meeting", "salesman-client-meeting", "city-skyline-business"],
    "events": ["networking-event-people", "busy-city-street-people", "marketing-team-office-meeting"],
    "niche": ["luxury-home-construction", "kitchen-renovation", "construction-worker-site"],
    "database": ["scrolling-phone-contacts", "person-typing-laptop", "editing-video-on-computer"],
}
# Define your clips here: start/end seconds in the recording + a B-roll theme (key of DEFAULT_BROLL).
# (Example only — replace with your own moments after reading your transcript.)
CLIPS = {
    "example-clip": {"start": 120.0, "end": 165.0, "broll": "outreach"},
}
# Per-clip BULLETS for the hidden-face card (bullets left, gold divider, logo right). Build cumulatively
# across the answer's hidden-face moments. Authored from each clip's advice. eyebrow = small gold label.
CARD_BULLETS = {
    "example-clip": {"eyebrow": "The play", "bullets": [
        "First key point", "Second key point", "Third key point", "Fourth key point"]},
}
from make_bullet_card import make_card_clip

cs = importlib.util.module_from_spec(importlib.util.spec_from_file_location("cs", os.path.join(BASE, "classify_speakers.py")))
importlib.util.spec_from_file_location("cs", os.path.join(BASE, "classify_speakers.py")).loader.exec_module(cs)
REF_F = cs.load_label_gray(os.path.join(BASE, "frames", "f_350.jpg"), True)
CROPS = sorted(glob.glob(os.path.join(BASE, "labels_1fps", "lbl_*.jpg")))
_lc = {}
def is_host(t):
    t = int(t)
    if t in _lc: return _lc[t]
    if t >= len(CROPS): _lc[t] = False; return False
    g = cs.load_label_gray(CROPS[t], False)
    sf = cs.ncc(cs.text_mask(g), cs.text_mask(REF_F))
    ok = sf > 0.6  # high correlation to HOST's label -> it's him; else a client
    _lc[t] = ok; return ok

def run(c):
    r = subprocess.run(c, capture_output=True, text=True)
    if r.returncode != 0: sys.stderr.write(" ".join(map(str, c)) + "\n" + r.stderr[-1200:]); raise SystemExit("ffmpeg fail")
def vad():
    srm = importlib.util.module_from_spec(importlib.util.spec_from_file_location("sr", VAD))
    importlib.util.spec_from_file_location("sr", VAD).loader.exec_module(srm)
    import torch
    wav = os.path.join(BASE, "vad_full.wav")
    if not os.path.exists(wav):
        run(["ffmpeg", "-y", "-i", SRC, "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", "-loglevel", "error", wav])
    with wave.open(wav, "rb") as wf: raw = wf.readframes(wf.getnframes())
    a = torch.from_numpy(np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0)
    m, u = srm.load_silero_vad()
    # aggressive pause removal: higher threshold (0.6) so HELD/filler sounds (e.g. a stretched "liiife" while
    # searching for a word) score below speech and get cut too; short min_silence catches brief hesitations.
    ts = u[0](a, m, threshold=0.6, min_speech_duration_ms=150, min_silence_duration_ms=180, sampling_rate=16000, return_seconds=True)
    segs = [{"start": float(t["start"]), "end": float(t["end"])} for t in ts]
    return srm.merge_overlapping(srm.add_padding(segs, 0.03, 0.03, 1e9), 0.05)

def build(name):
    cfg = CLIPS[name]; S, E = cfg["start"], cfg["end"]
    brolls = DEFAULT_BROLL[cfg["broll"]]
    speech = [s for s in vad() if s["end"] > S and s["start"] < E]
    # question vs answer: leading contiguous client block = the QUESTION (b-roll + voice-anon);
    # once HOST first appears = his ANSWER (his face; view-flickers to a client -> branded card, voice NOT shifted)
    host_secs = [t for t in range(int(S), int(E) + 1) if is_host(t)]
    host_start = host_secs[0] if host_secs else E
    def vsrc(t):
        if int(t) < host_start:
            return "qbroll"  # client's question -> b-roll + pitch
        return "foot" if is_host(int(t)) else "card"  # answer: HOST face, or branded card on view-flicker
    subs = []
    for sp in speech:
        a, b = max(S, sp["start"]), min(E, sp["end"])
        if b - a <= 0.1: continue
        cur_a, cur = a, vsrc(a); t = int(a) + 1
        while t < b:
            v = vsrc(t)
            if v != cur: subs.append({"a": cur_a, "b": float(t), "src": cur}); cur_a, cur = float(t), v
            t += 1
        subs.append({"a": cur_a, "b": b, "src": cur})
    subs = [s for s in subs if s["b"] - s["a"] > 0.12]
    TMP = os.path.join(BASE, "seg_" + name); os.makedirs(TMP, exist_ok=True)
    # FACE SAFETY: re-check every foot segment at 4fps; any sub-second client flash -> card (with +-0.3s pad).
    FT = os.path.join(TMP, "facecheck"); os.makedirs(FT, exist_ok=True)
    refined = []
    for s in subs:
        if s["src"] != "foot":
            refined.append(s); continue
        a, b = s["a"], s["b"]
        run(["ffmpeg", "-y", "-ss", f"{a}", "-to", f"{b}", "-i", SRC, "-vf", "fps=4,crop=280:50:0:670", "-q:v", "4", "-loglevel", "error", os.path.join(FT, "f_%04d.jpg")])
        fr = sorted(__import__("glob").glob(os.path.join(FT, "f_*.jpg")))
        ok = []
        for k, fp in enumerate(fr):
            g = cs.load_label_gray(fp, False)
            ok.append(cs.ncc(cs.text_mask(g), cs.text_mask(REF_F)) > 0.6)
            os.remove(fp)
        if not ok:  # too short to sample -> keep original foot segment as-is
            refined.append({**s, "_g": True}); continue
        # dilate client (not-ok) frames by +-2 steps (0.5s) for a wider safe zone, then build runs on the grid
        client = set(i for i, o in enumerate(ok) if not o)
        client = set(j for i in client for j in range(i - 2, i + 3) if 0 <= j < len(ok))
        for k in range(len(ok)):
            t0 = a + k * 0.25
            t1 = b if k == len(ok) - 1 else a + (k + 1) * 0.25
            src = "card" if k in client else "foot"
            # only extend the previous grid run if it's ACTUALLY adjacent (same source seg). A gap here means a
            # silence was cut between two foot segments -> starting a new run preserves the cut (don't span it).
            if refined and refined[-1].get("_g") and refined[-1]["src"] == src and t0 - refined[-1]["b"] < 0.04:
                refined[-1]["b"] = t1
            else:
                refined.append({"a": t0, "b": t1, "src": src, "_g": True})
    subs = [x for x in refined if x["b"] - x["a"] > 0.12]
    subs = [(x if not (x["src"] == "foot" and x["b"] - x["a"] < 0.5) else {**x, "src": "card"}) for x in subs]
    # CORNER EROSION: at every speaker transition Zoom lags onto the client's face for a beat -> cover the
    # first/last 0.4s of any HOST ("foot") run that borders a non-foot run (card/qbroll) with the name card.
    ER = 0.4
    eroded = []
    for i, s in enumerate(subs):
        if s["src"] != "foot":
            eroded.append(s); continue
        a, b = s["a"], s["b"]
        prev_nf = i > 0 and subs[i - 1]["src"] != "foot"
        next_nf = i < len(subs) - 1 and subs[i + 1]["src"] != "foot"
        if prev_nf and (b - a) > ER + 0.12:
            eroded.append({"a": a, "b": a + ER, "src": "card"}); a = a + ER
        if next_nf and (b - a) > ER + 0.12:
            eroded.append({"a": a, "b": b - ER, "src": "foot"}); eroded.append({"a": b - ER, "b": b, "src": "card"})
        else:
            eroded.append({"a": a, "b": b, "src": "foot"})
    subs = eroded
    # FLICKER REDUCTION: a short (<1.0s) glimpse of HOST's face sandwiched between two hidden-face moments
    # reads as flicker -> stay on the card instead (only ever shows the card MORE, never re-exposes the client).
    for i in range(1, len(subs) - 1):
        if subs[i]["src"] == "foot" and subs[i]["b"] - subs[i]["a"] < 1.0 \
           and subs[i - 1]["src"] != "foot" and subs[i + 1]["src"] != "foot":
            subs[i]["src"] = "card"
    # merge consecutive same-src segments so the card holds steady -- BUT only if they are truly ADJACENT.
    # If there's a gap (a silence VAD cut between them), do NOT merge: spanning it would RE-FILL the silence.
    merged = []
    for s in subs:
        if (merged and merged[-1]["src"] == s["src"] and s["src"] in ("card", "qbroll")
                and s["a"] - merged[-1]["b"] < 0.04):
            merged[-1]["b"] = s["b"]
        else:
            merged.append(dict(s))
    subs = merged
    if os.environ.get("CLIP_DEBUG"):
        gsum = sum(subs[i+1]["a"] - subs[i]["b"] for i in range(len(subs)-1) if subs[i+1]["a"] - subs[i]["b"] > 0.05)
        print("FINAL_SUBS total=%.2f gapsum=%.2f n=%d" % (sum(s["b"]-s["a"] for s in subs), gsum, len(subs)))
        print("SUBS", [(round(s["a"],2), round(s["b"],2), s["src"]) for s in subs])
    foot_vf = "crop=1280:628:0:46,scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1"
    card_cfg = CARD_BULLETS.get(name); card_reveal = 0  # cumulative bullet count across hidden-face moments
    vlist, alist, segmap = [], [], []; et = 0.0; bi = 0
    for i, s in enumerate(subs):
        a, b = s["a"], s["b"]; dur = round(b - a, 3)
        v = os.path.join(TMP, f"v{i}.mp4"); au = os.path.join(TMP, f"a{i}.wav")
        if s["src"] == "foot":
            run(["ffmpeg", "-y", "-threads", "3", "-ss", f"{a}", "-to", f"{b}", "-i", SRC, "-an", "-r", str(FPS), "-vf", foot_vf,
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-vsync", "cfr", "-loglevel", "error", v])
        elif s["src"] == "qbroll":
            src = os.path.join(BROLL, brolls[bi % len(brolls)] + ".mp4"); bi += 1
            run(["ffmpeg", "-y", "-threads", "3", "-stream_loop", "-1", "-i", src, "-t", f"{dur}", "-r", str(FPS),
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,eq=brightness=-0.04:saturation=1.05",
                 "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-vsync", "cfr", "-loglevel", "error", v])
        elif card_cfg and dur >= 0.8:  # substantial hidden-face moment -> branded BULLET card (bullets|divider|logo)
            bl = card_cfg["bullets"]; want = max(1, int(dur // 3.5)); prev = card_reveal
            card_reveal = min(card_reveal + want, len(bl)); n_new = card_reveal - prev
            if n_new < 1: n_new = min(len(bl), want)  # bullets exhausted -> re-animate last few for continued motion
            make_card_clip(bl[:card_reveal], dur, v, eyebrow=card_cfg["eyebrow"], n_new=n_new, fps=FPS)
        else:  # short hidden-face flash -> plain branded logo card (no time for a bullet to animate)
            run(["ffmpeg", "-y", "-threads", "3", "-loop", "1", "-t", f"{dur}", "-i", BG, "-r", str(FPS), "-vf", f"scale={W}:{H},setsar=1",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-vsync", "cfr", "-loglevel", "error", v])
        # LIP-SYNC: force audio to exactly the video segment's (CFR-rounded) duration -> no cumulative drift
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v], capture_output=True, text=True)
        vdur = float(pr.stdout.strip() or dur)
        af = []
        # Anonymize the client's voice using Zoom's speaker view as the signal: the question block (qbroll)
        # AND every SUBSTANTIAL hidden-face moment (card >=0.8s = Zoom switched to the client because they're
        # talking). Tiny <0.8s flicker bits are HOST's voice tail -> NOT shifted. (client_frac kept for when
        # reliable diarized intervals exist.)
        is_client_voice = s["src"] == "qbroll" or (s["src"] == "card" and (b - a) >= 0.8) or client_frac(a, b) > 0.4
        if CLIENT_PITCH and is_client_voice:
            af.append(f"asetrate=48000*{CLIENT_PITCH},aresample=48000,atempo={1/CLIENT_PITCH:.5f}")
        af += ["apad", f"atrim=0:{vdur:.4f}"]
        run(["ffmpeg", "-y", "-ss", f"{a}", "-to", f"{b}", "-i", SRC, "-vn", "-ac", "1", "-ar", "48000",
             "-af", ",".join(af), "-c:a", "pcm_s16le", "-loglevel", "error", au])
        vlist.append(f"file '{v}'"); alist.append(f"file '{au}'")
        segmap.append({"a": a, "b": b, "src": s["src"], "speaker": "CLIENT" if s["src"] == "qbroll" else "HOST", "es": round(et, 3), "ee": round(et + dur, 3)})
        et += dur
    open(os.path.join(TMP, "v.txt"), "w").write("\n".join(vlist)); open(os.path.join(TMP, "a.txt"), "w").write("\n".join(alist))
    catv = os.path.join(TMP, "video.mp4"); cata = os.path.join(TMP, "audio.wav")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(TMP, "v.txt"), "-c", "copy", "-loglevel", "error", catv])
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(TMP, "a.txt"), "-c", "copy", "-loglevel", "error", cata])
    def remap(t):
        for s in segmap:
            if s["a"] - 0.01 <= t < s["b"] + 0.01: return round(s["es"] + (t - s["a"]), 3)
        return None
    # FINANCIAL FIGURES: beep clients' actual revenue numbers HOST repeats back (e.g. "e.g. dollar figures").
    # A word is a figure if it has a digit, or is a magnitude word (k/grand/million/thousand) adjacent to a digit word.
    MAG = {"k", "grand", "grands", "million", "millions", "thousand", "thousands", "mil"}
    import re as _re
    def _hasdigit(s): return bool(_re.search(r"\d", s or ""))
    fig_ts = set()
    clipw = [w for w in WORDS if S - 1 <= w["start"] <= E + 1]
    for i, w in enumerate(clipw):
        lw = (w["word"] or "").lower().strip(" .,!?$")
        is_fig = _hasdigit(lw)
        if not is_fig and lw in MAG:
            nb = (clipw[i - 1]["word"] if i > 0 else "") + (clipw[i + 1]["word"] if i + 1 < len(clipw) else "")
            is_fig = _hasdigit(nb)
        if is_fig: fig_ts.add(w["start"])
    ew, mutes = [], []
    for w in WORDS:
        if not (S - 1 <= w["start"] <= E + 1): continue
        em = remap(w["start"])
        if em is None: continue
        ee = remap(w.get("end") or w["start"]) or em + 0.25
        ew.append({"s": em, "e": ee, "w": w["word"], "speaker": next((x["speaker"] for x in segmap if x["a"]-0.01 <= w["start"] < x["b"]+0.01), "?")})
        if "".join(ch for ch in (w["word"] or "").lower() if ch.isalpha()) in BLEEP or w["start"] in fig_ts:
            mutes.append((max(0, em-0.05), ee+0.07))
    vol = "".join(f"volume=enable='between(t,{a:.3f},{b:.3f})':volume=0," for a, b in mutes)
    enh = "highpass=f=80,lowpass=f=12000,equalizer=f=3000:t=q:w=1:g=2,acompressor=threshold=-18dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-1.5:LRA=11"
    enha = os.path.join(TMP, "audio_enh.wav")
    run(["ffmpeg", "-y", "-i", cata, "-af", vol + enh, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", "-loglevel", "error", enha])
    out = os.path.join(BASE, name + "-base.mp4")
    run(["ffmpeg", "-y", "-i", catv, "-i", enha, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-loglevel", "error", out])
    turns = []
    for w in ew:
        if turns and turns[-1]["speaker"] == w["speaker"] and w["s"] - turns[-1]["e"] < 0.8:
            turns[-1]["e"] = w["e"]; turns[-1]["words"].append(w)
        else: turns.append({"speaker": w["speaker"], "s": w["s"], "e": w["e"], "words": [w]})
    for t in turns: t["text"] = " ".join(x["w"] for x in t["words"])
    # spans = the foot(HOST face)/card(branded logo, client hidden)/qbroll(B-roll, client question) timeline in edited seconds.
    # build_manifest uses this: plain captions only over qbroll; circles+overlay cards only over foot (never over a branded card or B-roll).
    spans = [{"src": s["src"], "s": s["es"], "e": s["ee"]} for s in segmap]
    meta = {"name": name, "fps": FPS, "width": W, "height": H, "duration": round(et, 3), "durationFrames": int(round(et * FPS)), "base_video": out, "bleeps": len(mutes), "redact": [[round(a, 3), round(b, 3)] for a, b in mutes], "spans": spans, "turns": turns}
    json.dump(meta, open(os.path.join(BASE, name + "-meta.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"OUT {out} dur {et:.1f}s frames {meta['durationFrames']} bleeps {len(mutes)} foot/qbroll/card {sum(1 for s in subs if s['src']=='foot')}/{sum(1 for s in subs if s['src']=='qbroll')}/{sum(1 for s in subs if s['src']=='card')}")
    for t in turns: print(f"  [{t['s']:6.1f}-{t['e']:6.1f}] {t['speaker']:7s} {t['text'][:70]}")

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "c1-its-you")
