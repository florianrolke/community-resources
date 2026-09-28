"""Dense v6 manifest per recorded clip. Client (question) -> captions; HOST (answer) -> circled
phrases + cards (per-clip beats). whoosh -30%, hold zooms, cool flashes, mfcc music.
Usage: python build_manifest_impromptu.py <clipname>"""
import json, os, re, sys
BASE = os.path.dirname(__file__)
GOLD, COPPER, PALE = "#c9a96e", "#b87333", "#f0d68a"
DING = ["sfx/luxury-ding.wav", "sfx/luxury-click.wav", "sfx/course-ding.mp3", "sfx/course-pop.mp3"]

# Per-clip authored beats. AUTHOR THESE FROM YOUR TRANSCRIPT so the editing MATCHES what is said:
#   cards   = (anchor_phrase, kind, fields)  -> an overlay card appears when `anchor_phrase` is spoken.
#             kinds: full_screen_statement | fade_up_key | delta_panel | bullet_reveal
#   circles = (anchor_phrase, display_text)  -> circles the last word of display_text when anchor is spoken.
# Rules: place on the speaker's face only; one text element at a time; ~1 per 5-7s. Example below:
BEATS = {
 "example-clip": {
   "cards": [("spoken anchor phrase", "full_screen_statement",
              dict(eyebrow="Section label", title="Setup line", goldTitle="the payoff", body="One supporting line.")),
             ("another anchor", "fade_up_key",
              dict(eyebrow="The point", title="Key idea", goldTitle="in gold", side="left", body="One line."))],
   "circles": [("first key phrase", "FIRST key phrase"), ("second phrase", "SECOND phrase")] },
}

def main(name):
    M = json.load(open(os.path.join(BASE, name + "-meta.json"), encoding="utf-8"))
    FPS = M["fps"]
    REDACT = M.get("redact", [])  # [s,e] spans muted in audio -> mask the matching caption words too
    def _is_red(s, e): return any(not (e <= ra or s >= rb) for ra, rb in REDACT)
    WORDS = []
    for t in M["turns"]:
        for w in t["words"]:
            masked = _is_red(w["s"], w["e"])
            raw = "•••" if masked else w["w"]
            WORDS.append({"w": "" if masked else re.sub(r"[^a-z0-9']", "", (w["w"] or "").lower()), "raw": raw, "f": int(w["s"] * FPS), "sp": t["speaker"]})
    def find(p):
        tk = p.lower().split()
        for i in range(len(WORDS)):
            if all(i+k < len(WORDS) and WORDS[i+k]["w"] == tk[k] for k in range(len(tk))): return WORDS[i]["f"]
        return None
    overlays, captions, zooms, flashes, sfx = [], [], [], [], []
    n = [0]
    def sid(): n[0] += 1; return f"s{n[0]}"
    text_windows = []  # (start,end) of EVERY on-screen text element (card/circle/caption) -> never overlap two
    GAP_T = int(0.35 * FPS)
    def free(s, e):  # is the [s,e] window clear of all existing text (with a small gap)?
        return all(e + GAP_T <= a or s >= b + GAP_T for a, b in text_windows)
    def reg(s, e): text_windows.append((s, e))
    fstart = next((w["f"] for w in WORDS if w["sp"] == "HOST"), 0)
    # span timeline (frames): foot=HOST face, card=branded logo (client hidden), qbroll=B-roll (client question)
    SPANS = M.get("spans", [])
    foot_spans = [(int(s["s"] * FPS), int(s["e"] * FPS)) for s in SPANS if s["src"] == "foot"]
    qbroll_spans = [(int(s["s"] * FPS), int(s["e"] * FPS)) for s in SPANS if s["src"] == "qbroll"]
    def in_spans(fr, spans): return any(a <= fr < b for a, b in spans)
    def foot_window(fr):  # the HOST-face span that should host an overlay near frame fr
        for a, b in foot_spans:
            if a <= fr < b: return (a, b)
        after = [(a, b) for a, b in foot_spans if a >= fr]
        if after: return min(after, key=lambda x: x[0])
        return max(foot_spans, key=lambda x: x[1] - x[0]) if foot_spans else (fstart, M["durationFrames"])
    # PLAIN CAPTIONS: ONLY the client's question (over B-roll, NO face). HOST's answer = circles + cards, never subtitles.
    cw = [w for w in WORDS if w["sp"] == "CLIENT" and in_spans(w["f"], qbroll_spans)]
    i = 0
    while i < len(cw):
        line, ch, j = [], 0, i
        while j < len(cw) and len(line) < 5 and ch < 26:
            line.append(cw[j]["raw"]); ch += len(cw[j]["raw"]) + 1; j += 1
        s = cw[i]["f"] - 2; e = cw[j-1]["f"] + 10
        captions.append({"id": f"q{len(captions)}", "startFrame": max(0, s), "durationFrames": max(14, e-s),
                         "lines": [" ".join(line)], "zone": "center", "size": "normal", "highlightLines": []})
        reg(max(0, s), e)
        i = j
    def find_fb(anchor):  # try full phrase, then drop trailing words, then last word -> circles never silently vanish
        tk = anchor.split()
        for n_ in range(len(tk), 0, -1):
            fr = find(" ".join(tk[:n_]))
            if fr is not None: return fr
        return find(tk[-1])
    # one overlay card per HOST-face span (so two cards are NEVER on screen at once, and never over the branded logo)
    used_foot, card_ranges = [], []
    def alloc_foot(fr):
        cand = [(a, b) for a, b in foot_spans if (a, b) not in used_foot and b - a >= 60]
        if not cand: return None
        inside = [(a, b) for a, b in cand if a <= fr < b]
        if inside: pick = inside[0]
        else:
            after = [(a, b) for a, b in cand if a >= fr]
            pick = min(after, key=lambda x: x[0]) if after else min(cand, key=lambda x: abs(x[0] - fr))
        used_foot.append(pick); return pick
    def card(anchor, kind, fields, dur=140, lead=4):
        fr = find_fb(anchor)
        if fr is None: print("  miss card:", anchor); return
        win = alloc_foot(fr - lead)
        if win is None: print("  skip card (no free face span):", anchor); return
        wa, wb = win; m0 = 8
        # cap card at ~3.2s so the rest of the face window stays free for circles + visible face (denser edit)
        start = wa + m0; dur = min(dur, 95, (wb - m0) - start)
        if dur < 55: print("  skip card (face span too short):", anchor); return
        card_ranges.append((start, start + dur)); reg(start, start + dur)
        overlays.append({"kind": kind, "startFrame": start, "durationFrames": dur, **fields, "accentColor": fields.get("accentColor", GOLD)})
        # whoosh-type SFX that rides every card overlay: -30% per HOST (0.28 -> 0.20). Paper/riser/boom untouched.
        is_paper = kind in ("bullet_reveal", "delta_panel")
        sfx.append({"id": sid(), "startFrame": start, "file": "sfx/luxury-paper.wav" if is_paper else "sfx/course-whoosh.mp3", "volume": 0.28 if is_paper else 0.20})
        if kind == "full_screen_statement":
            sfx.append({"id": sid(), "startFrame": start-12, "file": "sfx/luxury-riser.wav", "volume": 0.32})
            sfx.append({"id": sid(), "startFrame": start, "file": "sfx/luxury-subboom.wav", "volume": 0.5})
        flashes.append({"id": f"fl{len(flashes)}", "startFrame": start-6, "durationFrames": 14, "intensity": 0.5, "coolWash": True})
    CDUR = 50  # circle on screen ~1.7s
    def circle(anchor, phrase, di=0):
        fr = find_fb(anchor)
        if fr is None: print("  miss circ:", anchor); return
        if not in_spans(fr, foot_spans): print("  skip circ (not on face):", anchor); return
        if not free(fr - 2, fr - 2 + CDUR): return  # never overlap another text element
        captions.append({"id": f"circ{len(captions)}", "startFrame": fr-2, "durationFrames": CDUR, "lines": [phrase], "circleWord": phrase.split()[-1].lower(), "circleLeftPct": 62, "circleWidth": 190, "zone": "center", "size": "large", "highlightLines": []})
        reg(fr - 2, fr - 2 + CDUR)
        sfx.append({"id": sid(), "startFrame": fr-1, "file": DING[di % 4], "volume": 0.15})
    b = BEATS[name]
    for a, k, f in b["cards"]: card(a, k, f)            # cards first (claim face spans + register windows)
    for idx, (a, p) in enumerate(b["circles"]): circle(a, p, idx)   # AUTHORED, transcript-matched circles only
    # (No mechanical grid auto-fill: circles are hand-authored per clip in BEATS to land on the KEY phrases as
    #  they're spoken - the editing must match the transcript, not sprinkle circles on a timer.)
    overlays.sort(key=lambda x: x["startFrame"])
    end = M["durationFrames"]
    for o in overlays:  # keep everything inside the clip
        if o["startFrame"] + o["durationFrames"] > end - 4:
            o["durationFrames"] = max(55, end - 4 - o["startFrame"])
    # ONE gentle, continuous zoom per face shot: a single slow Ken-Burns drift across the whole foot span
    # (no 8s pulsing, no snap-back to 1.0, consistent mode). Calm, motivated push-ins - never erratic.
    end = M["durationFrames"]
    for zi, (a, bnd) in enumerate(foot_spans):
        seg = min(bnd, end - 2) - a
        if seg < int(2.0 * FPS):  # skip short shots (a quick push-in there would feel jumpy)
            continue
        zooms.append({"id": f"z{zi}", "startFrame": a, "durationFrames": seg, "zoom": 1.045, "mode": "slow"})
    # (punch-zoom "jump cuts" removed - they read as erratic. Cuts come only from tight silence removal, like c2.)
    # match the proven 2026-06-06 v6 music object EXACTLY (loop + ducking + pulse-on-overlay = audibly present)
    music = [{"src": "mfcc-optimistic-positive-background-music-303472.mp3", "startFrame": 0,
              "durationFrames": M["durationFrames"], "volume": 0.024, "fadeInFrames": 24, "fadeOutFrames": 120,
              "duckToVolume": 0.0165, "duckPaddingFrames": 9, "duckFadeFrames": 12,
              "pulseOnOverlay": True, "pulseVolume": 0.0345, "pulseFrames": 16, "loop": True}]
    man = {"videoSrc": name + "-base.mp4", "fps": FPS, "width": 640, "height": 360, "durationFrames": M["durationFrames"],
           "overlays": sorted(overlays, key=lambda x: x["startFrame"]), "hybridCaptions": sorted(captions, key=lambda x: x["startFrame"]),
           "hybridZoomEvents": sorted(zooms, key=lambda x: x["startFrame"]), "hybridFlashes": sorted(flashes, key=lambda x: x["startFrame"]),
           "tickerBands": [], "sfxCues": sorted(sfx, key=lambda x: x["startFrame"]), "backgroundMusic": music, "videoEffects": {"jumpCuts": []}}
    json.dump({"manifest": man}, open(os.path.join(BASE, name + "-props.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"{name}: overlays={len(overlays)} caps/circ={len(captions)} zooms={len(zooms)} sfx={len(sfx)} dur={M['durationFrames']}f")

if __name__ == "__main__":
    main(sys.argv[1])
