#!/usr/bin/env python3
"""
Batch analyze thumbnail images using Gemini vision API (layered design approach).

Deconstructs thumbnails into Background -> Graphics -> Text layers.
Based on Meli Garcia's design philosophy.

Usage:
    python "Nick Saraev YouTube Skills/analyze-thumbnails/scripts/analyze_thumbnail_images.py"

Output:
    - Nick Saraev YouTube Skills/thumbnail-analysis-results/individual/[image_name].json
    - Nick Saraev YouTube Skills/thumbnail-analysis-results/aggregated_patterns.md
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List
import time
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv package not installed")
    print("Install with: pip install python-dotenv")
    sys.exit(1)

try:
    import google.generativeai as genai  # Works with both google-generativeai and google-genai
except ImportError:
    try:
        from google import genai  # New SDK (google-genai)
    except ImportError:
        print("ERROR: No Gemini SDK installed")
        print("Install with: pip install google-genai  (preferred)")
        print("       or:    pip install google-generativeai  (legacy)")
        sys.exit(1)

# Load environment variables from .env
load_dotenv()

# Project paths
# Script lives in: Nick Saraev YouTube Skills/analyze-thumbnails/scripts/
# Project root is 3 levels up
SCRIPT_DIR = Path(__file__).parent
SKILL_ROOT = SCRIPT_DIR.parent.parent  # Nick Saraev YouTube Skills/
PROJECT_ROOT = SKILL_ROOT.parent  # Video Editing Workflow/
RESOURCES_DIR = PROJECT_ROOT / "Resources" / "[1] YouTube"
OUTPUT_DIR = SKILL_ROOT / "thumbnail-analysis-results"
LOG_FILE = OUTPUT_DIR / "analysis_log.txt"

# Image directories to analyze
IMAGE_SOURCES = [
    RESOURCES_DIR / "[01] OFFER - Big Idea & Packaging" / "My own Thumbnails",
    RESOURCES_DIR / "[01] OFFER - Big Idea & Packaging" / "YT Thumbnail swipe file",
    RESOURCES_DIR / "Teachers" / "Aprilynne Alter Screenshots",
]

# Gemini API settings
BATCH_SIZE = 5  # Process 5 images at a time to avoid rate limits
DELAY_BETWEEN_BATCHES = 2  # seconds
GEMINI_MODEL = "models/gemini-3-pro-image-preview"  # Gemini 3 Pro with advanced image analysis

# Analysis prompt template (layered structure based on design philosophy)
ANALYSIS_PROMPT = """Analyze this YouTube thumbnail image by deconstructing it into design layers.

Think like a designer: thumbnails are built in layers (background → graphics → text).
Provide a JSON response with the following structure:

{
  "layers": {
    "background_layer": {
      "type": "solid|gradient|photo|blurred_photo|graphic|pattern",
      "dominant_colors": ["#RRGGBB", "#RRGGBB", "#RRGGBB"],  // Top 3 background colors
      "depth_technique": "none|blur|vignette|shadow|gradient|layering",
      "description": "Brief description of what provides the foundation (e.g., 'Blurred office photo with warm tones')"
    },
    "graphics_layer": {
      "elements_present": ["face", "icons", "shapes", "objects", "arrows", "graphics"],  // What visual elements exist
      "face_details": {
        "present": true|false,
        "position": "left|center|right|none",  // Horizontal position
        "size_percent": 30-80,  // Approximate % of frame height
        "emotion": "excited|serious|surprised|skeptical|neutral|enthusiastic",
        "eye_contact": true|false  // Looking at camera?
      },
      "visual_elements": [
        {
          "type": "icon|shape|object|arrow|graphic|number",
          "position": "top_left|top_right|bottom_left|bottom_right|center",
          "purpose": "visual_interest|context|emphasis|direction|credibility",
          "color": "#RRGGBB"
        }
      ],
      "composition_technique": "rule_of_thirds|centered|asymmetric|dynamic|z_pattern|f_pattern"
    },
    "text_layer": {
      "text_present": true|false,
      "word_count": 0-10,  // Total words across all text elements
      "text_elements": [
        {
          "text": "Approximate text content",
          "hierarchy": "headline|subheadline|caption",
          "size": "huge|large|medium|small",  // Relative to frame
          "color": "#RRGGBB",
          "position": "top|upper_third|middle|lower_third|bottom",
          "alignment": "left|center|right"
        }
      ],
      "typography_style": "bold|outlined|shadow|3d|flat|handwritten",
      "text_effects": ["shadow", "outline", "glow", "background_box", "none"],
      "readability_score": "excellent|good|fair|poor",  // Can you read it at mobile size?
      "color_contrast": "high|medium|low"  // Text vs background
    }
  },
  "design_principles": {
    "overall_contrast": "high|medium|low",  // Overall image contrast
    "visual_hierarchy": "text_first|face_first|balanced|graphics_first",  // What draws attention first
    "color_psychology": "urgency|warmth|authority|energy|calm|excitement|trust",
    "color_harmony": "complementary|analogous|triadic|monochromatic|contrasting",
    "scroll_stoppers": ["face", "numbers", "bright_colors", "high_contrast", "unusual_angle", "mystery", "danger"],
    "click_triggers": ["question", "promise", "shock", "fomo", "benefit", "curiosity_gap", "social_proof"]
  },
  "effectiveness_analysis": {
    "predicted_ctr": "high|medium|low",
    "primary_hook": "What makes you want to click (be specific)",
    "strengths": ["List 2-3 strongest design choices"],
    "improvements": ["List 2-3 specific improvements"],
    "mobile_optimized": true|false,  // Works well at small size?
    "platform_best_practices": "Follows YouTube thumbnail best practices (high contrast, large text, clear focal point)?"
  }
}

IMPORTANT: Think sequentially like a designer building this thumbnail:
1. What's the background foundation?
2. What graphics/visual elements sit on top?
3. What text sits on the very top?

Be specific and quantitative. Extract exact colors in hex. Count words. Estimate percentages."""


def log(message: str):
    """Log message to file and console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"

    print(log_line)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def load_image_for_gemini(image_path: Path):
    """Load image file for Gemini API."""
    from PIL import Image
    return Image.open(image_path)


def analyze_image(model: genai.GenerativeModel, image_path: Path) -> Dict:
    """
    Analyze a single image with Gemini vision API.

    Returns: Dict with analysis results
    """
    try:
        # Load image
        image = load_image_for_gemini(image_path)

        # Call Gemini vision API
        response = model.generate_content([
            ANALYSIS_PROMPT,
            image
        ])

        # Extract JSON from response
        response_text = response.text

        # Try to parse JSON (may have markdown code fences)
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            json_str = response_text.strip()

        analysis = json.loads(json_str)

        # Add metadata with token usage
        metadata = {
            "image_path": str(image_path),
            "image_name": image_path.name,
            "source_directory": image_path.parent.name,
            "analyzed_at": datetime.now().isoformat(),
            "model": GEMINI_MODEL
        }

        # Add token usage if available
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            metadata["tokens"] = {
                "prompt_tokens": usage.prompt_token_count,
                "response_tokens": usage.candidates_token_count,
                "total_tokens": usage.total_token_count
            }

        analysis["metadata"] = metadata
        return analysis

    except json.JSONDecodeError as e:
        log(f"ERROR: Failed to parse JSON for {image_path.name}: {str(e)}")
        log(f"Raw response: {response_text[:500]}")
        return {
            "error": "JSON parse error",
            "raw_response": response_text[:500],
            "metadata": {
                "image_path": str(image_path),
                "image_name": image_path.name,
                "analyzed_at": datetime.now().isoformat()
            }
        }
    except Exception as e:
        log(f"ERROR: Failed to analyze {image_path.name}: {str(e)}")
        return {
            "error": str(e),
            "metadata": {
                "image_path": str(image_path),
                "image_name": image_path.name,
                "analyzed_at": datetime.now().isoformat()
            }
        }


def find_all_images() -> List[Path]:
    """Find all image files in source directories."""
    images = []
    supported_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    for source_dir in IMAGE_SOURCES:
        if not source_dir.exists():
            log(f"WARNING: Directory not found: {source_dir}")
            continue

        for image_path in source_dir.rglob("*"):
            if image_path.suffix.lower() in supported_extensions:
                images.append(image_path)

    return sorted(images)


def aggregate_patterns(analyses: List[Dict]) -> str:
    """
    Aggregate patterns across all thumbnails using layered structure.

    Returns: Markdown report with aggregated insights
    """
    # Filter out error analyses
    valid_analyses = [a for a in analyses if "error" not in a]

    if not valid_analyses:
        return "# No valid analyses to aggregate\n"

    # Initialize counters
    total = len(valid_analyses)

    # Background layer
    background_types = {}
    depth_techniques = {}
    all_bg_colors = []

    # Graphics layer
    face_present = 0
    face_emotions = {}
    composition_techniques = {}
    graphic_elements = {}

    # Text layer
    text_present = 0
    word_counts = []
    typography_styles = {}
    readability = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    text_effects = {}

    # Design principles
    contrast_levels = {"high": 0, "medium": 0, "low": 0}
    color_psychology = {}
    visual_hierarchy = {}
    scroll_stoppers = {}
    click_triggers = {}

    # Effectiveness
    ctr_predictions = {"high": 0, "medium": 0, "low": 0}
    mobile_optimized = 0

    for analysis in valid_analyses:
        # Background Layer
        if "layers" in analysis and "background_layer" in analysis["layers"]:
            bg = analysis["layers"]["background_layer"]
            bg_type = bg.get("type", "unknown")
            background_types[bg_type] = background_types.get(bg_type, 0) + 1

            depth = bg.get("depth_technique", "none")
            depth_techniques[depth] = depth_techniques.get(depth, 0) + 1

            all_bg_colors.extend(bg.get("dominant_colors", []))

        # Graphics Layer
        if "layers" in analysis and "graphics_layer" in analysis["layers"]:
            gfx = analysis["layers"]["graphics_layer"]

            # Face tracking
            face_details = gfx.get("face_details", {})
            if face_details.get("present"):
                face_present += 1
                emotion = face_details.get("emotion", "neutral")
                face_emotions[emotion] = face_emotions.get(emotion, 0) + 1

            # Composition
            comp = gfx.get("composition_technique", "unknown")
            composition_techniques[comp] = composition_techniques.get(comp, 0) + 1

            # Graphic elements
            for elem in gfx.get("elements_present", []):
                graphic_elements[elem] = graphic_elements.get(elem, 0) + 1

        # Text Layer
        if "layers" in analysis and "text_layer" in analysis["layers"]:
            text = analysis["layers"]["text_layer"]

            if text.get("text_present"):
                text_present += 1

            wc = text.get("word_count", 0)
            if wc is not None and wc > 0:
                word_counts.append(wc)

            typo_style = text.get("typography_style", "unknown")
            typography_styles[typo_style] = typography_styles.get(typo_style, 0) + 1

            read_score = text.get("readability_score", "fair")
            readability[read_score] = readability.get(read_score, 0) + 1

            for effect in text.get("text_effects", []):
                text_effects[effect] = text_effects.get(effect, 0) + 1

        # Design Principles
        if "design_principles" in analysis:
            principles = analysis["design_principles"]

            contrast = principles.get("overall_contrast", "medium")
            contrast_levels[contrast] = contrast_levels.get(contrast, 0) + 1

            psych = principles.get("color_psychology", "unknown")
            color_psychology[psych] = color_psychology.get(psych, 0) + 1

            hierarchy = principles.get("visual_hierarchy", "unknown")
            visual_hierarchy[hierarchy] = visual_hierarchy.get(hierarchy, 0) + 1

            for stopper in principles.get("scroll_stoppers", []):
                scroll_stoppers[stopper] = scroll_stoppers.get(stopper, 0) + 1

            for trigger in principles.get("click_triggers", []):
                click_triggers[trigger] = click_triggers.get(trigger, 0) + 1

        # Effectiveness
        if "effectiveness_analysis" in analysis:
            eff = analysis["effectiveness_analysis"]

            ctr = eff.get("predicted_ctr", "medium")
            ctr_predictions[ctr] = ctr_predictions.get(ctr, 0) + 1

            if eff.get("mobile_optimized"):
                mobile_optimized += 1

    # Generate report
    report = f"""# Thumbnail Analysis - Layered Design Patterns

> **Analyzed:** {total} thumbnails
> **Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> **Approach:** Deconstructed thumbnails into Background → Graphics → Text layers

---

## 📐 Layer 1: Background Foundation

### Background Types
{chr(10).join(f"- **{bg_type.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for bg_type, count in sorted(background_types.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Depth Techniques
{chr(10).join(f"- **{technique.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for technique, count in sorted(depth_techniques.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Most Common Background Colors
{chr(10).join(f"- {color}" for color in list(dict.fromkeys(all_bg_colors[:15])))}

**Insight:** {sorted(background_types.items(), key=lambda x: x[1], reverse=True)[0][0].replace('_', ' ').title() if background_types else 'N/A'} is the most common background type.

---

## 🎨 Layer 2: Graphics & Visual Elements

### Face Presence
- **Thumbnails with faces:** {face_present}/{total} ({face_present/total*100:.1f}%)
- **Thumbnails without faces:** {total - face_present}/{total} ({(total-face_present)/total*100:.1f}%)

**Insight:** Faces appear in {face_present/total*100:.1f}% of thumbnails (industry benchmark: faces boost CTR by 20-30%)

### Face Emotions (when faces present)
{chr(10).join(f"- **{emotion.title()}:** {count}/{face_present} ({count/face_present*100:.1f}% of faces)" for emotion, count in sorted(face_emotions.items(), key=lambda x: x[1], reverse=True) if count > 0) if face_present > 0 else "- No face emotion data"}

### Composition Techniques
{chr(10).join(f"- **{comp.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for comp, count in sorted(composition_techniques.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Graphic Elements Used
{chr(10).join(f"- **{elem.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for elem, count in sorted(graphic_elements.items(), key=lambda x: x[1], reverse=True)[:10] if count > 0)}

---

## ✍️ Layer 3: Text & Typography

### Text Presence
- **Thumbnails with text:** {text_present}/{total} ({text_present/total*100:.1f}%)
- **Thumbnails without text:** {total - text_present}/{total} ({(total-text_present)/total*100:.1f}%)

### Word Count Statistics
- **Average:** {sum(word_counts)/len(word_counts) if word_counts else 0:.1f} words
- **Min:** {min(word_counts) if word_counts else 0} words
- **Max:** {max(word_counts) if word_counts else 0} words

**Best Practice:** Keep under 5 words for mobile readability (avg: {sum(word_counts)/len(word_counts) if word_counts else 0:.1f})

### Typography Styles
{chr(10).join(f"- **{style.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for style, count in sorted(typography_styles.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Readability Scores
{chr(10).join(f"- **{level.title()}:** {count}/{total} ({count/total*100:.1f}%)" for level, count in sorted(readability.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Text Effects
{chr(10).join(f"- **{effect.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for effect, count in sorted(text_effects.items(), key=lambda x: x[1], reverse=True)[:8] if count > 0)}

---

## 🎯 Design Principles

### Contrast Levels
- **High contrast:** {contrast_levels['high']}/{total} ({contrast_levels['high']/total*100:.1f}%)
- **Medium contrast:** {contrast_levels['medium']}/{total} ({contrast_levels['medium']/total*100:.1f}%)
- **Low contrast:** {contrast_levels['low']}/{total} ({contrast_levels['low']/total*100:.1f}%)

**Insight:** {contrast_levels['high']/total*100:.1f}% use high contrast (critical for scroll-stopping)

### Color Psychology
{chr(10).join(f"- **{psych.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for psych, count in sorted(color_psychology.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Visual Hierarchy
{chr(10).join(f"- **{hierarchy.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for hierarchy, count in sorted(visual_hierarchy.items(), key=lambda x: x[1], reverse=True) if count > 0)}

### Scroll Stoppers (Attention Grabbers)
{chr(10).join(f"- **{stopper.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for stopper, count in sorted(scroll_stoppers.items(), key=lambda x: x[1], reverse=True)[:10] if count > 0)}

### Click Triggers (CTR Boosters)
{chr(10).join(f"- **{trigger.replace('_', ' ').title()}:** {count}/{total} ({count/total*100:.1f}%)" for trigger, count in sorted(click_triggers.items(), key=lambda x: x[1], reverse=True)[:10] if count > 0)}

---

## 📊 Effectiveness Analysis

### Predicted CTR
- **High:** {ctr_predictions['high']}/{total} ({ctr_predictions['high']/total*100:.1f}%)
- **Medium:** {ctr_predictions['medium']}/{total} ({ctr_predictions['medium']/total*100:.1f}%)
- **Low:** {ctr_predictions['low']}/{total} ({ctr_predictions['low']/total*100:.1f}%)

### Mobile Optimization
- **Mobile-optimized:** {mobile_optimized}/{total} ({mobile_optimized/total*100:.1f}%)
- **Not optimized:** {total - mobile_optimized}/{total} ({(total-mobile_optimized)/total*100:.1f}%)

---

## 💡 Design Recommendations

Based on layered analysis of {total} thumbnails:

### Background Layer
1. **Type:** Use {sorted(background_types.items(), key=lambda x: x[1], reverse=True)[0][0].replace('_', ' ')} ({sorted(background_types.items(), key=lambda x: x[1], reverse=True)[0][1]/total*100:.0f}% do)
2. **Depth:** Apply {sorted(depth_techniques.items(), key=lambda x: x[1], reverse=True)[0][0].replace('_', ' ')} for depth

### Graphics Layer
3. **Faces:** {'Include faces' if face_present/total > 0.5 else 'Consider faces'} ({face_present/total*100:.0f}% of thumbnails use them)
4. **Composition:** Use {sorted(composition_techniques.items(), key=lambda x: x[1], reverse=True)[0][0].replace('_', ' ')} technique
5. **Elements:** Combine {', '.join([elem.replace('_', ' ') for elem, _ in sorted(graphic_elements.items(), key=lambda x: x[1], reverse=True)[:3]])}

### Text Layer
6. **Word count:** Keep to {sum(word_counts)/len(word_counts) if word_counts else 3:.0f} words or fewer
7. **Style:** Use {sorted(typography_styles.items(), key=lambda x: x[1], reverse=True)[0][0].replace('_', ' ')} typography
8. **Readability:** Aim for "excellent" or "good" ({(readability.get('excellent', 0)+readability.get('good', 0))/total*100:.0f}% achieved this)

### Design Principles
9. **Contrast:** Use high contrast ({contrast_levels['high']/total*100:.0f}% of successful thumbnails do)
10. **Psychology:** Target {sorted(color_psychology.items(), key=lambda x: x[1], reverse=True)[0][0]} emotion

---

## 📁 Individual Analysis Files

All {total} individual thumbnail analyses saved to:
`.tmp/thumbnail_analysis/[image_name].json`

Each JSON file contains layered breakdown:
- **Background layer:** Type, colors, depth techniques
- **Graphics layer:** Face details, visual elements, composition
- **Text layer:** Typography, readability, effects
- **Design principles:** Contrast, psychology, triggers
- **Effectiveness:** CTR prediction, mobile optimization

Use these for detailed pattern extraction when writing thumbnail-design-strategy.md skill file.
"""

    return report


def main():
    """Run batch thumbnail analysis."""

    # Setup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Check for API key
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        log("ERROR: GOOGLE_GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
        log("Set it in .env file or export GOOGLE_GEMINI_API_KEY=your-key")
        sys.exit(1)

    # Configure Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # Find all images
    log("Finding thumbnail images...")
    images = find_all_images()
    log(f"Found {len(images)} images across {len(IMAGE_SOURCES)} directories")

    if not images:
        log("No images found. Check paths:")
        for source_dir in IMAGE_SOURCES:
            log(f"  - {source_dir} (exists: {source_dir.exists()})")
        sys.exit(1)

    # Analyze in batches
    all_analyses = []

    for i in range(0, len(images), BATCH_SIZE):
        batch = images[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(images) + BATCH_SIZE - 1) // BATCH_SIZE

        log(f"")
        log(f"Batch {batch_num}/{total_batches} ({len(batch)} images)")

        for image_path in batch:
            log(f"  Analyzing: {image_path.name}")

            analysis = analyze_image(model, image_path)
            all_analyses.append(analysis)

            # Save individual analysis
            individual_dir = OUTPUT_DIR / "individual"
            individual_dir.mkdir(parents=True, exist_ok=True)
            output_file = individual_dir / f"{image_path.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2)

            log(f"    Saved: {output_file.name}")

        # Delay between batches to avoid rate limits
        if i + BATCH_SIZE < len(images):
            log(f"  Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    # Generate aggregated report
    log("")
    log("Generating aggregated patterns report...")
    report = aggregate_patterns(all_analyses)

    report_file = OUTPUT_DIR / "aggregated_patterns.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    log(f"Saved aggregated report: {report_file}")

    # Summary
    valid_count = len([a for a in all_analyses if "error" not in a])
    error_count = len([a for a in all_analyses if "error" in a])

    log("")
    log("="*80)
    log("ANALYSIS COMPLETE")
    log("="*80)
    log(f"Total images: {len(images)}")
    log(f"Successfully analyzed: {valid_count}")
    log(f"Errors: {error_count}")
    log(f"Output directory: {OUTPUT_DIR}")

    # Calculate total cost
    total_prompt_tokens = 0
    total_response_tokens = 0
    for analysis in all_analyses:
        if "metadata" in analysis and "tokens" in analysis["metadata"]:
            tokens = analysis["metadata"]["tokens"]
            total_prompt_tokens += tokens.get("prompt_tokens", 0)
            total_response_tokens += tokens.get("response_tokens", 0)

    if total_prompt_tokens > 0 or total_response_tokens > 0:
        # Gemini 3 Pro Image pricing (approximate)
        input_cost_per_1k = 0.0025
        output_cost_per_1k = 0.01

        input_cost = (total_prompt_tokens / 1000) * input_cost_per_1k
        output_cost = (total_response_tokens / 1000) * output_cost_per_1k
        total_cost = input_cost + output_cost

        log("")
        log("="*80)
        log("COST ANALYSIS")
        log("="*80)
        log(f"Total prompt tokens:    {total_prompt_tokens:,}")
        log(f"Total response tokens:  {total_response_tokens:,}")
        log(f"Total tokens:           {total_prompt_tokens + total_response_tokens:,}")
        log(f"Input cost:             ${input_cost:.4f}")
        log(f"Output cost:            ${output_cost:.4f}")
        log(f"Total cost:             ${total_cost:.4f}")

        # Extrapolate to all 136 images if this was a test
        if len(images) == 10:
            full_cost = total_cost * (136 / 10)
            log("")
            log(f"ESTIMATED COST FOR ALL 136 IMAGES:")
            log(f"  ${full_cost:.2f}")
            log("="*80)

    log("")
    log("Next steps:")
    log("1. Review aggregated_patterns.md for insights")
    log("2. Check individual JSON files for detailed analysis")
    log("3. Write skill 3: thumbnail-design-strategy.md")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n\nINTERRUPTED by user (Ctrl+C)")
        log("Partial results saved to .tmp/thumbnail_analysis/")
        sys.exit(1)
    except Exception as e:
        log(f"\n\nFATAL ERROR: {str(e)}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
