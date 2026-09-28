"""Cut picture to an EXTERNAL voiceover, one shot per spoken phrase.

Unlike build_story_edit.py (which lifts audio out of the source clips), this
keeps the voiceover as ONE continuous, untouched audio track and cuts only the
video to match. That means no joins or clicks in the voice, and the word
timings from the VO's own transcript stay valid — so they feed
render_captions.py directly with no remapping.

Phrase boundaries come from the transcript: a new phrase starts after a pause
longer than --pause, or after sentence-ending punctuation. Shots are assigned
in the order given and cycle if there are more phrases than shots.

Usage:
    python -X utf8 execution/build_vo_edit.py \
        --voiceover assets/vo/my-script.mp3 \
        --words assets/vo/my-script.words.json \
        --shots 93e36439-scene_1__s1,33e0efdf-scene_0__s2,a9caef6d-scene_0__s2 \
        --name my-short-v1 --dry-run

    # let it use every text-free shot, in a sensible order
    python -X utf8 execution/build_vo_edit.py --voiceover ... --words ... --clean-shots --name x
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOTS_JSON = PROJECT_ROOT / "assets" / "scenes" / "shots.json"
OUTPUT_DIR = PROJECT_ROOT / "output" / "stories"

TARGET_W, TARGET_H, TARGET_FPS = 1080, 1920, 30
OVERSCAN_W, OVERSCAN_H = 1242, 2208
SENTENCE_END = (".", "!", "?")


def die(message: str) -> "NoReturn":  # noqa: F821
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        die(f"ffprobe failed for {path}")
    return float(result.stdout.strip())


def load_words(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    words = data.get("words")
    if not words:
        words = [w for s in data.get("segments", []) for w in s.get("words", [])]
    if not words:
        die(f"no word-level timings in {path}")
    return sorted(words, key=lambda w: w["start"])


def group_phrases(words: list[dict], pause: float, min_len: float) -> list[dict]:
    """Split the VO into phrases on sentence ends and pauses."""
    phrases: list[dict] = []
    current: list[dict] = []
    for index, word in enumerate(words):
        current.append(word)
        gap_next = (words[index + 1]["start"] - word["end"]) if index + 1 < len(words) else 999
        ends_sentence = word["word"].strip().endswith(SENTENCE_END)
        if ends_sentence or gap_next >= pause:
            phrases.append({
                "start": current[0]["start"],
                "end": word["end"],
                "text": " ".join(w["word"].strip() for w in current),
            })
            current = []
    if current:
        phrases.append({
            "start": current[0]["start"],
            "end": current[-1]["end"],
            "text": " ".join(w["word"].strip() for w in current),
        })

    # absorb slivers into the previous phrase so no shot flashes by
    merged: list[dict] = []
    for phrase in phrases:
        if merged and phrase["end"] - phrase["start"] < min_len:
            merged[-1]["end"] = phrase["end"]
            merged[-1]["text"] += " " + phrase["text"]
        else:
            merged.append(phrase)
    return merged


def zoom_expression(index: int, frames: int, amount: float) -> str:
    if frames < 2:
        return "1"
    if index % 2 == 0:
        return f"1+{amount:.4f}*on/{frames}"
    return f"{1 + amount:.4f}-{amount:.4f}*on/{frames}"


REMOTE_ROOT = "/home/agent-zero-data/vo-edit"


def render_remote(beats: list[dict], voiceover: Path, out_video: Path, local_cmd: list[str]) -> int:
    """Encode on the remote box. Clips are uploaded once and cached by size."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import hostinger  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        die(f"could not import hostinger.py ({exc})")

    hostinger.ssh(f"mkdir -p {REMOTE_ROOT}/clips", timeout=60)

    # Map each local file to a UNIQUE remote name. Keying by basename collides —
    # a dozen different clips in this library are all called scene_0.mp4, and the
    # render would silently pull the wrong footage.
    def remote_name(path: Path) -> str:
        digest = hashlib.md5(str(path).encode("utf-8")).hexdigest()[:8]
        return f"{digest}_{path.name}"

    locals_needed: dict[str, Path] = {}
    for beat in beats:
        locals_needed[str(Path(beat["path"]))] = Path(beat["path"])
    locals_needed[str(voiceover)] = voiceover

    listing = hostinger.ssh(f"ls -l {REMOTE_ROOT}/clips 2>/dev/null | awk '{{print $5, $9}}'", timeout=60)
    remote_sizes: dict[str, int] = {}
    for line in (listing.stdout or "").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            remote_sizes[parts[1].strip()] = int(parts[0])

    for path in locals_needed.values():
        target = remote_name(path)
        size = path.stat().st_size
        if remote_sizes.get(target) == size:
            print(f"  = {path.name} already on the box")
            continue
        print(f"  ^ uploading {path.name} ({size / (1024 * 1024):.1f} MB) ...")
        result = hostinger.scp_up(str(path), f"{REMOTE_ROOT}/clips/{target}", timeout=3600)
        if result.returncode != 0:
            die(f"upload failed for {path.name}: {result.stderr[:300]}")

    # Rewrite every local path in the ffmpeg command to its remote equivalent.
    remote_out = f"{REMOTE_ROOT}/{out_video.name}"
    remote_cmd: list[str] = []
    for token in local_cmd:
        if token == str(out_video):
            remote_cmd.append(remote_out)
        elif token in locals_needed:
            remote_cmd.append(f"{REMOTE_ROOT}/clips/{remote_name(Path(token))}")
        else:
            remote_cmd.append(token)

    # shlex.quote, not hand-rolled quoting: the filter_complex is full of single
    # quotes from the zoompan expressions and naive wrapping breaks the shell.
    quoted = " ".join(shlex.quote(t) for t in remote_cmd)
    print(f"\nRendering {out_video.name} on the remote box (niced, 4 cores) ...")
    result = hostinger.ssh(f"cd {REMOTE_ROOT} && nice -n 10 {quoted}", timeout=5400)
    if result.returncode != 0:
        die(f"remote ffmpeg failed:\n{(result.stderr or result.stdout)[-1200:]}")

    out_video.parent.mkdir(parents=True, exist_ok=True)
    down = hostinger.scp_down(remote_out, str(out_video), timeout=1800)
    if getattr(down, "returncode", 1) != 0 or not out_video.is_file():
        die(f"download of the rendered file failed: {getattr(down, 'stderr', '')[:300]}")
    hostinger.ssh(f"rm -f {remote_out}", timeout=60)

    print(f"\nDone (remote): {out_video}  ({probe_duration(out_video):.2f}s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut picture to an external voiceover.")
    parser.add_argument("--voiceover", required=True)
    parser.add_argument("--words", required=True, help="Word-level transcript of the VOICEOVER")
    parser.add_argument("--shots", default="", help="Comma-separated shot ids, in order")
    parser.add_argument("--clean-shots", action="store_true",
                        help="Use every shot with has_burned_text == false")
    parser.add_argument("--name", default="vo-edit")
    parser.add_argument("--pause", type=float, default=0.32, help="Gap that starts a new phrase")
    parser.add_argument("--min-phrase", type=float, default=1.6, help="Merge phrases shorter than this")
    parser.add_argument("--max-beat", type=float, default=5.0,
                        help="Longest a single shot may hold before cutting away")
    parser.add_argument("--min-beat", type=float, default=1.2,
                        help="Shortest a shot may appear — prevents one-frame flashes")
    parser.add_argument("--hook-cuts", type=int, default=0,
                        help="Force this many cuts inside the opening window (e.g. 3). The first "
                             "seconds decide retention, so the hook gets its own cutting rhythm "
                             "regardless of where the sentence boundaries fall.")
    parser.add_argument("--hook-window", type=float, default=3.0,
                        help="Length of the opening window that --hook-cuts subdivides")
    parser.add_argument("--tail", type=float, default=1.5,
                        help="Seconds of picture held after the last word, so the CTA and its "
                             "caption can land instead of being cut off")
    parser.add_argument("--zoom-amount", type=float, default=0.05)
    parser.add_argument("--no-zoom", action="store_true")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--remote", action="store_true",
                        help="Encode on the remote box instead of this machine. Source clips "
                             "are uploaded once and reused across runs.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        die("ffmpeg not found on PATH.")
    if not SHOTS_JSON.exists():
        die(f"{SHOTS_JSON} not found. Run detect_shots.py first.")

    voiceover = Path(args.voiceover)
    if not voiceover.is_file():
        die(f"voiceover not found: {voiceover}")
    vo_duration = probe_duration(voiceover)

    all_shots = json.loads(SHOTS_JSON.read_text(encoding="utf-8")).get("shots", [])
    by_id = {s["id"]: s for s in all_shots}

    if args.shots:
        shot_ids = [s.strip() for s in args.shots.split(",") if s.strip()]
        unknown = [s for s in shot_ids if s not in by_id]
        if unknown:
            die(f"unknown shot id(s): {', '.join(unknown)}")
    elif args.clean_shots:
        shot_ids = [s["id"] for s in all_shots if s.get("has_burned_text") is False]
        if not shot_ids:
            die("no shots flagged has_burned_text == false in shots.json")
    else:
        die("give --shots id1,id2,... or --clean-shots")

    words = load_words(Path(args.words))
    phrases = group_phrases(words, args.pause, args.min_phrase)

    # Cut on phrase boundaries, but cover the WHOLE voiceover — the gaps between
    # phrases are part of the timeline too, so each span runs to the next phrase's start.
    spans: list[dict] = []
    for i, phrase in enumerate(phrases):
        start = 0.0 if i == 0 else phrase["start"]
        end = phrases[i + 1]["start"] if i + 1 < len(phrases) else vo_duration
        if end - start > 0.05:
            spans.append({"start": start, "end": end, "text": phrase["text"]})

    # The opening decides whether anyone watches the rest, so it gets its own rhythm:
    # slice the hook window into equal beats instead of inheriting sentence boundaries.
    if args.hook_cuts > 1 and args.hook_window > 0.5:
        beat_len = args.hook_window / args.hook_cuts
        hook_spans = [{"start": round(i * beat_len, 3),
                       "end": round((i + 1) * beat_len, 3),
                       "text": spans[0]["text"] if i == 0 and spans else "  (hook)"}
                      for i in range(args.hook_cuts)]
        rest = []
        for span in spans:
            if span["end"] <= args.hook_window + 0.05:
                continue
            rest.append({**span, "start": max(span["start"], args.hook_window)})
        spans = hook_spans + rest
        print(f"hook: {args.hook_cuts} cuts across the first {args.hook_window:.1f}s "
              f"({beat_len:.2f}s each)")

    # Divide each span into EQUAL chunks that fit inside --max-beat, then place each
    # chunk whole. Splitting a span only when a shot runs dry leaves scraps behind and
    # the tail ends up as a burst of flashes; uniform chunks also cut more rhythmically.
    playhead = {sid: 0.0 for sid in shot_ids}
    last_used = {sid: -999 for sid in shot_ids}
    cursor = 0
    beats: list[dict] = []
    for span in spans:
        span_len = span["end"] - span["start"]
        chunks = max(1, math.ceil(span_len / args.max_beat))
        chunk_len = span_len / chunks
        at = span["start"]
        first_chunk = True
        for _ in range(chunks):
            def left(sid: str) -> float:
                return by_id[sid]["duration"] - playhead[sid]

            previous = beats[-1]["shot"] if beats else None
            if not beats:
                chosen = shot_ids[0]                     # deliberate opener
            else:
                # Only consider shots that can hold the whole chunk. Prefer whichever
                # has gone longest without being on screen, using remaining footage
                # only as a tiebreak — ranking purely by footage left makes one long
                # shot dominate the whole edit.
                fits = [s for s in shot_ids if left(s) >= chunk_len - 0.01 and s != previous]
                if not fits:
                    fits = [s for s in shot_ids if left(s) >= chunk_len - 0.01]
                if not fits:                             # pool spent — reuse from the top
                    for sid in shot_ids:
                        playhead[sid] = 0.0
                    fits = [s for s in shot_ids if s != previous] or list(shot_ids)
                chosen = max(fits, key=lambda s: (len(beats) - last_used[s], left(s)))

            shot = by_id[chosen]
            if shot["duration"] - playhead[chosen] < chunk_len - 0.01:
                playhead[chosen] = 0.0                   # last resort: replay this shot
            v_start = shot["start"] + playhead[chosen]
            playhead[chosen] += chunk_len
            last_used[chosen] = len(beats)
            beats.append({
                "index": len(beats),
                "shot": chosen,
                "path": shot["abs_path"],
                "v_start": round(v_start, 3),
                "duration": round(chunk_len, 3),
                "audio_start": round(at, 3),
                "text": span["text"] if first_chunk else "  (cont.)",
            })
            at += chunk_len
            first_chunk = False

    # Hold the last shot past the final word. Fish leaves only ~0.3s after the CTA,
    # which reads as the video being chopped off and clips the last caption too.
    if args.tail > 0.01 and beats:
        last = beats[-1]
        shot = by_id[last["shot"]]
        room = shot["end"] - (last["v_start"] + last["duration"])
        if room >= args.tail - 0.01:
            last["duration"] = round(last["duration"] + args.tail, 3)   # let it run on, no cut
        else:
            spare = [s for s in shot_ids if (by_id[s]["duration"] - playhead[s]) >= args.tail
                     and s != last["shot"]]
            pick = max(spare, key=lambda s: by_id[s]["duration"] - playhead[s]) if spare else last["shot"]
            picked = by_id[pick]
            v_start = picked["start"] + (playhead[pick] if pick != last["shot"] else 0.0)
            beats.append({
                "index": len(beats), "shot": pick, "path": picked["abs_path"],
                "v_start": round(min(v_start, picked["end"] - args.tail), 3),
                "duration": round(args.tail, 3),
                "audio_start": round(vo_duration, 3), "text": "  (tail)",
            })

    print(f"Voiceover: {voiceover.name} ({vo_duration:.2f}s)")
    print(f"Shots available: {len(shot_ids)}  |  tail: {args.tail:.2f}s\n")
    print(f"{'#':<3} {'SHOT':<24} {'AT':>7} {'LEN':>7}  TEXT")
    print("-" * 104)
    total = 0.0
    for beat in beats:
        print(f"{beat['index'] + 1:<3} {beat['shot']:<24} {beat['audio_start']:>6.2f}s "
              f"{beat['duration']:>6.2f}s  {beat['text'][:48]}")
        total += beat["duration"]
    print("-" * 104)
    print(f"{len(beats)} phrases, video {total:.2f}s vs voiceover {vo_duration:.2f}s")
    if total < vo_duration - 0.3:
        print(f"  ! picture is {vo_duration - total:.2f}s short — add more shots or the tail will freeze")

    if args.dry_run:
        print("\n(dry run — nothing rendered)")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_video = OUTPUT_DIR / f"{args.name}.mp4"

    cmd = ["ffmpeg", "-y", "-v", "error", "-stats"]
    for beat in beats:
        cmd += ["-ss", f"{beat['v_start']:.3f}", "-t", f"{beat['duration']:.3f}", "-i", beat["path"]]
    cmd += ["-i", str(voiceover)]

    filters = []
    for i, beat in enumerate(beats):
        frames = max(int(beat["duration"] * TARGET_FPS), 2)
        chain = (f"[{i}:v]scale={OVERSCAN_W}:{OVERSCAN_H}:force_original_aspect_ratio=increase,"
                 f"crop={OVERSCAN_W}:{OVERSCAN_H},setsar=1,fps={TARGET_FPS}")
        if not args.no_zoom:
            chain += (f",zoompan=z='{zoom_expression(i, frames, args.zoom_amount)}'"
                      f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d=1:s={TARGET_W}x{TARGET_H}:fps={TARGET_FPS}")
        else:
            chain += f",scale={TARGET_W}:{TARGET_H}"
        chain += f",setpts=PTS-STARTPTS[v{i}]"
        filters.append(chain)
    filters.append("".join(f"[v{i}]" for i in range(len(beats))) + f"concat=n={len(beats)}:v=1:a=0[outv]")
    # Pad the voice track with silence so it matches the held tail exactly.
    pad = f",apad=pad_dur={args.tail:.3f}" if args.tail > 0.01 else ""
    filters.append(f"[{len(beats)}:a]loudnorm=I=-14:TP=-1.5:LRA=11{pad}[outa]")

    cmd += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out_video)]

    if args.remote:
        return render_remote(beats, voiceover, out_video, cmd)

    print(f"\nRendering {out_video.name} ...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        die(f"ffmpeg exited with code {result.returncode}")

    print(f"\nDone: {out_video}  ({probe_duration(out_video):.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
