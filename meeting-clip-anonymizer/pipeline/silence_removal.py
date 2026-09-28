#!/usr/bin/env python3
"""
Skill 1: Silence Removal

Remove dead air and verbal hesitations using Silero VAD.
Creates tight, engaging pacing.
"""

import subprocess
import json
import os
import torch
from pathlib import Path


def load_silero_vad():
    """Load Silero VAD model."""
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        onnx=False
    )
    return model, utils


def detect_speech_segments(
    audio_path: str,
    threshold: float = 0.5,
    min_speech_duration: float = 0.25,
    min_silence_duration: float = 0.3,
    sampling_rate: int = 16000
) -> list:
    """
    Detect speech segments using Silero VAD.

    Returns:
        List of {"start": float, "end": float} dicts
    """
    model, utils = load_silero_vad()
    (get_speech_timestamps, _, read_audio, _, _) = utils

    wav = read_audio(audio_path, sampling_rate=sampling_rate)

    speech_timestamps = get_speech_timestamps(
        wav,
        model,
        threshold=threshold,
        min_speech_duration_ms=int(min_speech_duration * 1000),
        min_silence_duration_ms=int(min_silence_duration * 1000),
        sampling_rate=sampling_rate,
        return_seconds=True
    )

    return [{"start": ts["start"], "end": ts["end"]} for ts in speech_timestamps]


def extract_audio(video_path: str, audio_path: str, sample_rate: int = 16000) -> bool:
    """Extract audio from video for VAD processing."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def add_padding(segments: list, padding_before: float, padding_after: float, max_duration: float) -> list:
    """Add padding to speech segments."""
    padded = []
    for seg in segments:
        start = max(0, seg["start"] - padding_before)
        end = min(max_duration, seg["end"] + padding_after)
        padded.append({"start": start, "end": end})
    return padded


def merge_overlapping(segments: list, gap_threshold: float = 0.1) -> list:
    """Merge segments that are very close together."""
    if not segments:
        return []

    merged = [segments[0].copy()]

    for seg in segments[1:]:
        if seg["start"] - merged[-1]["end"] < gap_threshold:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(seg.copy())

    return merged


def remove_silences(
    input_video: str,
    output_video: str,
    min_silence: float = 0.3,
    padding_before: float = 0.05,
    padding_after: float = 0.08,
    min_segment: float = 0.5,
    tmp_dir: str = ".tmp"
) -> dict:
    """
    Remove silences from video using Silero VAD.

    Args:
        input_video: Path to input video
        output_video: Path to output video
        min_silence: Minimum silence duration to cut (seconds)
        padding_before: Audio padding before speech (seconds)
        padding_after: Audio padding after speech (seconds)
        min_segment: Minimum segment duration to keep (seconds)
        tmp_dir: Directory for temporary files

    Returns:
        {
            "segments": [...],
            "original_duration": float,
            "final_duration": float,
            "compression_ratio": float,
            "segments_count": int
        }
    """
    os.makedirs(tmp_dir, exist_ok=True)

    # Get video duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        input_video
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    video_info = json.loads(probe_result.stdout)
    original_duration = float(video_info["format"]["duration"])

    print(f"[SILENCE] Original duration: {original_duration:.1f}s")

    # Extract audio
    audio_path = os.path.join(tmp_dir, "vad_audio.wav")
    print("[SILENCE] Extracting audio...")
    if not extract_audio(input_video, audio_path):
        raise RuntimeError("Failed to extract audio")

    # Detect speech
    print("[SILENCE] Running VAD...")
    segments = detect_speech_segments(
        audio_path,
        min_silence_duration=min_silence,
        min_speech_duration=min_segment
    )

    print(f"[SILENCE] Found {len(segments)} speech segments")

    # Add padding and merge
    segments = add_padding(segments, padding_before, padding_after, original_duration)
    segments = merge_overlapping(segments)

    # Filter very short segments
    segments = [s for s in segments if (s["end"] - s["start"]) >= min_segment]

    print(f"[SILENCE] After merging: {len(segments)} segments")

    if not segments:
        raise RuntimeError("No speech segments found")

    # Build FFmpeg filter complex
    filters = []
    concat_inputs = []

    for i, seg in enumerate(segments):
        filters.append(
            f"[0:v]trim=start={seg['start']:.3f}:end={seg['end']:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )
        filters.append(
            f"[0:a]atrim=start={seg['start']:.3f}:end={seg['end']:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_inputs.append(f"[v{i}][a{i}]")

    filters.append(
        f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=1[outv][outa]"
    )

    filter_complex = ";".join(filters)

    # Run FFmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        output_video
    ]

    print("[SILENCE] Rendering...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[ERROR] FFmpeg failed: {result.stderr[-500:]}")
        raise RuntimeError("FFmpeg render failed")

    # Calculate stats
    final_duration = sum(s["end"] - s["start"] for s in segments)
    compression = (1 - final_duration / original_duration) * 100

    print(f"[SILENCE] Final duration: {final_duration:.1f}s")
    print(f"[SILENCE] Removed {compression:.1f}% of video")

    return {
        "segments": segments,
        "original_duration": original_duration,
        "final_duration": final_duration,
        "compression_ratio": compression,
        "segments_count": len(segments)
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python silence_removal.py <input.mp4> <output.mp4>")
        sys.exit(1)

    result = remove_silences(sys.argv[1], sys.argv[2])
    print(f"\nResult: {json.dumps(result, indent=2)}")
