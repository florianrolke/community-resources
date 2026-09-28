"""
Gemini-to-Remotion Bridge - Schema converter

Converts the Gemini mograph analysis output (ai_studio_code.txt format)
into a Remotion-compatible GraphicsManifest JSON.

Handles:
- Timestamp strings ("00:06.500") -> frame numbers
- Semantic color names ("salmon_pink") -> hex values
- Component type mapping -> Remotion component names
- Grouping graphics by component_type

Usage:
    python gemini_to_remotion_bridge.py --input gemini_output.json --output manifest.json --fps 30
"""

import json
import re
import argparse
import sys
from typing import Dict, List, Any, Optional


# ─── Color Name to Hex Mapping ───

COLOR_MAP: Dict[str, str] = {
    "white": "#FFFFFF",
    "salmon_pink": "#FF9999",
    "salmon": "#FF9999",
    "yellow": "#FFFF00",
    "red": "#FF0000",
    "green": "#22C55E",
    "blue": "#3B82F6",
    "black": "#000000",
    "dark_grey": "#121212",
    "light_grey": "#E5E5E5",
    "paper_white": "#FAFAFA",
    "none": "transparent",
}

# ─── Component Type Mapping (Gemini -> Remotion) ───

COMPONENT_MAP: Dict[str, str] = {
    "text_highlight_caption": "text_highlight_captions",
    "kinetic_text_phrase": "kinetic_text_phrases",
    "explainer_graphic_scene": "background_takeovers",
    "background_takeover": "background_takeovers",
    "framework_scene": "background_takeovers",
    "table_scene": "background_takeovers",
    "chapter_card": "chapter_cards",
    "headline_stack": "headline_stacks",
    "logo_animation": "text_highlight_captions",  # fallback
    "stat_text_block": "kinetic_text_phrases",  # fallback
}

# ─── Entry Animation Mapping ───

ENTRY_MAP: Dict[str, str] = {
    "fade_in_scale_up": "fade_in_scale_up",
    "pop_in": "pop_in",
    "slide_in_from_bottom": "slide_in_from_bottom",
    "typewriter_reveal": "typewriter",
    "typewriter": "typewriter",
    "stamp_impact": "stamp_impact",
    "scale_up_bounce": "scale_up_bounce",
    "scale_up_fade_in": "fade_in_scale_up",
    "hard_cut": "hard_cut",
}


def parse_timestamp(ts: str) -> float:
    """Convert timestamp string to seconds.

    Supports formats:
    - "00:06.500" (MM:SS.mmm)
    - "01:30.200" (MM:SS.mmm)
    - "6.5" (seconds)
    - "00:01:30.200" (HH:MM:SS.mmm)
    """
    if isinstance(ts, (int, float)):
        return float(ts)

    ts = ts.strip()

    # HH:MM:SS.mmm
    match = re.match(r"(\d+):(\d+):(\d+)(?:\.(\d+))?", ts)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        ms = int(match.group(4)) if match.group(4) else 0
        ms_str = match.group(4) or "0"
        frac = int(ms_str) / (10 ** len(ms_str))
        return h * 3600 + m * 60 + s + frac

    # MM:SS.mmm
    match = re.match(r"(\d+):(\d+)(?:\.(\d+))?", ts)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        ms_str = match.group(3) or "0"
        frac = int(ms_str) / (10 ** len(ms_str))
        return m * 60 + s + frac

    # Plain seconds
    try:
        return float(ts)
    except ValueError:
        raise ValueError(f"Cannot parse timestamp: {ts}")


def time_to_frame(seconds: float, fps: int) -> int:
    """Convert seconds to frame number."""
    return round(seconds * fps)


def resolve_color(color_name: str) -> str:
    """Convert semantic color name to hex value."""
    if not color_name:
        return "#FFFFFF"
    # Already a hex color
    if color_name.startswith("#"):
        return color_name
    return COLOR_MAP.get(color_name.lower().strip(), "#FFFFFF")


def convert_text_highlight_caption(graphic: Dict, fps: int) -> Dict:
    """Convert a Gemini text_highlight_caption to Remotion format."""
    timing = graphic.get("timing", {})
    spatial = graphic.get("spatial", {})
    text_props = graphic.get("text_properties", {})
    color_behavior = graphic.get("color_behavior", {})
    transform = graphic.get("transform", {})

    start_time = parse_timestamp(timing.get("start", "0"))
    end_time = parse_timestamp(timing.get("end", "0"))
    duration_sec = end_time - start_time

    return {
        "text": text_props.get("content", graphic.get("text", "")),
        "startFrame": time_to_frame(start_time, fps),
        "durationFrames": max(1, time_to_frame(duration_sec, fps)),
        "yPercent": int(spatial.get("y_percent", spatial.get("y", 60))),
        "maxWidthPercent": int(spatial.get("max_width_percent", spatial.get("max_width", 80))),
        "rotationDegrees": float(spatial.get("rotation", transform.get("rotation_start", 0))),
        "fontWeight": int(text_props.get("font_weight", text_props.get("weight", 700))),
        "highlightColor": resolve_color(
            color_behavior.get("highlight", color_behavior.get("highlight_color", "white"))
        ),
        "highlightBehavior": text_props.get("highlight_behavior", "speech_synced"),
        "wordsVisibleAtOnce": int(text_props.get("words_visible_at_once", 8)),
    }


def convert_kinetic_text_phrase(graphic: Dict, fps: int) -> Dict:
    """Convert a Gemini kinetic_text_phrase to Remotion format."""
    timing = graphic.get("timing", {})
    spatial = graphic.get("spatial", {})
    text_props = graphic.get("text_properties", {})
    color_behavior = graphic.get("color_behavior", {})
    transform = graphic.get("transform", {})

    start_time = parse_timestamp(timing.get("start", "0"))
    end_time = parse_timestamp(timing.get("end", "0"))
    duration_sec = end_time - start_time

    content = text_props.get("content", graphic.get("text", ""))
    words = content.upper().split() if content else []

    # Find highlight word index
    highlight_idx = None
    highlight_word = text_props.get("emphasis_word", "")
    if highlight_word and words:
        highlight_upper = highlight_word.upper()
        for i, w in enumerate(words):
            if w == highlight_upper or highlight_upper in w:
                highlight_idx = i
                break
        if highlight_idx is None:
            highlight_idx = len(words) - 1  # default to last word

    return {
        "words": words,
        "startFrame": time_to_frame(start_time, fps),
        "durationFrames": max(1, time_to_frame(duration_sec, fps)),
        "rotationDegrees": float(spatial.get("rotation", transform.get("rotation_start", -3))),
        "highlightColor": resolve_color(
            color_behavior.get("highlight", color_behavior.get("highlight_color", "yellow"))
        ),
        "baseColor": resolve_color(
            color_behavior.get("base_text", color_behavior.get("base_color", "white"))
        ),
        "highlightWordIndex": highlight_idx,
        "intonationAligned": text_props.get("intonation_aligned", True),
    }


def convert_background_takeover(graphic: Dict, fps: int) -> Dict:
    """Convert a Gemini explainer/framework/table scene to Remotion format."""
    timing = graphic.get("timing", {})
    text_props = graphic.get("text_properties", {})
    transform = graphic.get("transform", {})
    bg = graphic.get("background", {})

    start_time = parse_timestamp(timing.get("start", "0"))
    end_time = parse_timestamp(timing.get("end", "0"))
    duration_sec = end_time - start_time

    bg_type = bg.get("type", graphic.get("background_type", "desk_surface"))
    if bg_type in ("desk_surface_with_paper_prop", "desk_surface"):
        bg_type = "desk_surface"
    elif bg_type in ("paper", "printed_document"):
        bg_type = "paper"
    else:
        bg_type = "solid"

    entry = transform.get("entry_animation", transform.get("entry", "slide_in_from_bottom"))
    entry = ENTRY_MAP.get(str(entry), "slide_in_from_bottom")

    return {
        "startFrame": time_to_frame(start_time, fps),
        "durationFrames": max(1, time_to_frame(duration_sec, fps)),
        "backgroundType": bg_type,
        "headline": text_props.get("headline", text_props.get("content", "")),
        "bodyText": text_props.get("body_text", text_props.get("body", "")),
        "entryAnimation": entry,
        "elements": [],
    }


def convert_chapter_card(graphic: Dict, fps: int) -> Dict:
    """Convert a Gemini chapter_card to Remotion format."""
    timing = graphic.get("timing", {})
    text_props = graphic.get("text_properties", {})

    start_time = parse_timestamp(timing.get("start", "0"))
    end_time = parse_timestamp(timing.get("end", "0"))
    duration_sec = end_time - start_time

    chapter_num = text_props.get("chapter_number", text_props.get("number", 1))
    if isinstance(chapter_num, str):
        nums = re.findall(r"\d+", chapter_num)
        chapter_num = int(nums[0]) if nums else 1

    return {
        "startFrame": time_to_frame(start_time, fps),
        "durationFrames": max(1, time_to_frame(duration_sec, fps)),
        "chapterNumber": int(chapter_num),
        "title": text_props.get("title", text_props.get("content", "")).upper(),
    }


def convert_headline_stack(graphic: Dict, fps: int) -> Dict:
    """Convert to headline stack format."""
    timing = graphic.get("timing", {})
    text_props = graphic.get("text_properties", {})
    color_behavior = graphic.get("color_behavior", {})

    start_time = parse_timestamp(timing.get("start", "0"))
    end_time = parse_timestamp(timing.get("end", "0"))
    duration_sec = end_time - start_time

    content = text_props.get("content", graphic.get("text", ""))
    # Split into lines at newlines or at natural break points
    if "\n" in content:
        lines = [l.strip().upper() for l in content.split("\n") if l.strip()]
    else:
        words = content.upper().split()
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])] if len(words) > 3 else [content.upper()]

    return {
        "lines": lines,
        "startFrame": time_to_frame(start_time, fps),
        "durationFrames": max(1, time_to_frame(duration_sec, fps)),
        "highlightColor": resolve_color(
            color_behavior.get("highlight", "yellow")
        ),
        "highlightLineIndex": len(lines) - 1,  # highlight last line by default
    }


# ─── Converter dispatch ───

CONVERTERS = {
    "text_highlight_captions": convert_text_highlight_caption,
    "kinetic_text_phrases": convert_kinetic_text_phrase,
    "background_takeovers": convert_background_takeover,
    "chapter_cards": convert_chapter_card,
    "headline_stacks": convert_headline_stack,
}


def convert_gemini_output(
    gemini_data: Dict[str, Any],
    fps: int = 30,
    video_src: str = "edited_base.mp4",
    width: int = 1920,
    height: int = 1080,
) -> Dict[str, Any]:
    """Convert full Gemini analysis output to Remotion GraphicsManifest.

    Accepts either:
    - A list of graphics under "graphics" key
    - A flat list at the top level
    - The ai_studio_code.txt format with nested structure
    """
    # Extract graphics list
    graphics_list = []
    if isinstance(gemini_data, list):
        graphics_list = gemini_data
    elif "graphics" in gemini_data:
        g = gemini_data["graphics"]
        graphics_list = g if isinstance(g, list) else []
    elif "first_30s" in gemini_data:
        # ai_studio_code.txt format
        first_30 = gemini_data.get("first_30s", {}).get("graphics", [])
        full_video = gemini_data.get("full_video", {}).get("graphics", [])
        graphics_list = first_30 + full_video

    # Initialize manifest
    manifest = {
        "videoSrc": video_src,
        "fps": fps,
        "width": width,
        "height": height,
        "durationFrames": 0,
        "graphics": {
            "text_highlight_captions": [],
            "kinetic_text_phrases": [],
            "background_takeovers": [],
            "chapter_cards": [],
            "headline_stacks": [],
        },
    }

    max_frame = 0

    for graphic in graphics_list:
        # Determine component type
        comp_type = graphic.get("component_type", graphic.get("type", "text_highlight_caption"))
        remotion_key = COMPONENT_MAP.get(comp_type, "text_highlight_captions")

        converter = CONVERTERS.get(remotion_key)
        if not converter:
            continue

        try:
            converted = converter(graphic, fps)
            manifest["graphics"][remotion_key].append(converted)

            end_frame = converted.get("startFrame", 0) + converted.get("durationFrames", 0)
            max_frame = max(max_frame, end_frame)
        except Exception as e:
            print(f"Warning: Failed to convert graphic {graphic.get('id', '?')}: {e}", file=sys.stderr)

    # Set total duration
    manifest["durationFrames"] = max_frame + fps * 5  # 5s padding

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Convert Gemini mograph analysis to Remotion GraphicsManifest"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to Gemini JSON output")
    parser.add_argument("--output", "-o", required=True, help="Path to write Remotion manifest")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second (default: 30)")
    parser.add_argument("--video-src", default="edited_base.mp4", help="Video source path for manifest")
    parser.add_argument("--width", type=int, default=1920, help="Video width (default: 1920)")
    parser.add_argument("--height", type=int, default=1080, help="Video height (default: 1080)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        gemini_data = json.load(f)

    manifest = convert_gemini_output(
        gemini_data,
        fps=args.fps,
        video_src=args.video_src,
        width=args.width,
        height=args.height,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Print summary
    g = manifest["graphics"]
    total = sum(len(v) for v in g.values())
    print(f"Converted {total} graphics to Remotion manifest:")
    for key, items in g.items():
        if items:
            print(f"  {key}: {len(items)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
