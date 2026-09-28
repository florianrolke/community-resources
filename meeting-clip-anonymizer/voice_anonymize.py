#!/usr/bin/env python3
"""
voice_anonymize.py — anonymize a meeting participant's VOICE in a video (the hero capability).

WHY: When you repurpose a recorded call into clips, the other person never agreed to be a public
figure. You can keep their words (the value) while protecting their identity by SHIFTING THEIR PITCH
so the voice isn't recognizable — and (optionally) bleeping names/figures. This is the audio half of a
full "meeting -> clips" pipeline; the video half hides their face (see README).

HOW THE PITCH SHIFT WORKS (duration-preserving, ffmpeg only — no ML, instant, deterministic):
    asetrate=SR*P , aresample=SR , atempo=1/P
  - asetrate*P then aresample resamples the audio -> pitch scaled by P, but duration scaled by 1/P.
  - atempo=1/P restores the original duration WITHOUT undoing the pitch change.
  - P < 1.0  => LOWER / DEEPER voice  (recommended for male voices: 0.80-0.86 = clearly anonymized,
                not "chipmunk"). P > 1.0 => higher. Use P below 1 to go deeper.

WHICH PARTS TO SHIFT: you pass the time intervals where the OTHER person speaks (--intervals), in the
ORIGINAL video's timeline. How to get them:
  1) Zoom/Meet "speaker view": the active tile = whoever is talking. Detect when the other person is the
     on-screen tile (template-match their name label) -> those intervals. ROBUST for 2-similar voices.
  2) Diarization (pyannote): works, but UNRELIABLE for two similar same-mic voices — verify before trusting.
  3) Manual: just list the intervals.

USAGE:
  python voice_anonymize.py in.mp4 out.mp4 --intervals 0:9,41:48 --pitch 0.82
  python voice_anonymize.py in.mp4 out.mp4 --intervals-file other_speaker.json --pitch 0.82 \
         --bleep 12.3:12.8,40.1:41.0     # mute PII windows (names / figures)

intervals-file JSON:  {"intervals": [[0.0, 9.1], [41.0, 48.3]]}
"""
import argparse, json, subprocess, sys


def _parse_pairs(s):
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        a, b = part.split(":")
        out.append((float(a), float(b)))
    return out


def build_filter(intervals, pitch, bleeps):
    """Build an ffmpeg -af chain: deepen pitch only inside `intervals`, then mute `bleeps`.

    We render TWO versions of the audio (normal + pitched), then crossfade-select between them per
    interval using `volume` envelopes, and sum. This keeps your voice untouched and only the
    other person's segments shifted, with no duration drift.
    """
    P = float(pitch)
    # pitched copy of the whole track (duration-preserving)
    f = [f"[0:a]asetrate=48000*{P},aresample=48000,atempo={1/P:.6f}[pit]"]
    # gate: 1 inside intervals, 0 outside  (build via volume enable windows on each branch)
    norm_gate = "".join(f"volume=enable='between(t,{a:.3f},{b:.3f})':volume=0," for a, b in intervals)
    pit_keep = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in intervals) or "0"
    f.append(f"[0:a]{norm_gate}anull[norm]")                       # original with the shifted spans muted out
    f.append(f"[pit]volume=enable='not({pit_keep})':volume=0[pitg]")  # pitched, only the shifted spans kept
    f.append("[norm][pitg]amix=inputs=2:normalize=0[mix]")
    last = "mix"
    if bleeps:
        vol = "".join(f"volume=enable='between(t,{a:.3f},{b:.3f})':volume=0," for a, b in bleeps)
        f.append(f"[{last}]{vol}anull[out]")
        last = "out"
    else:
        f.append(f"[{last}]anull[out]")
    return ";".join(f), "[out]"


def main():
    ap = argparse.ArgumentParser(description="Anonymize a participant's voice (pitch shift) in a video.")
    ap.add_argument("input"); ap.add_argument("output")
    ap.add_argument("--intervals", help="comma list start:end (s) where the OTHER person speaks")
    ap.add_argument("--intervals-file", help="JSON {'intervals': [[a,b],...]} in original timeline")
    ap.add_argument("--pitch", type=float, default=0.82, help="pitch factor; <1 = deeper (default 0.82)")
    ap.add_argument("--bleep", default="", help="comma list start:end (s) to MUTE (names/figures)")
    a = ap.parse_args()

    intervals = _parse_pairs(a.intervals) if a.intervals else []
    if a.intervals_file:
        intervals += [tuple(x) for x in json.load(open(a.intervals_file))["intervals"]]
    if not intervals:
        sys.exit("No intervals given. Pass --intervals or --intervals-file (the OTHER person's speech).")
    bleeps = _parse_pairs(a.bleep)

    filt, out_label = build_filter(intervals, a.pitch, bleeps)
    cmd = ["ffmpeg", "-y", "-i", a.input, "-filter_complex", filt,
           "-map", "0:v?", "-map", out_label, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", a.output]
    print(f"[voice] pitch={a.pitch} on {len(intervals)} interval(s), {len(bleeps)} bleep(s)")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit("ffmpeg failed")
    print(f"[voice] wrote {a.output}")


if __name__ == "__main__":
    main()
