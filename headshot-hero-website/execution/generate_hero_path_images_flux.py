"""
Generate 2 Hero's Arc path images via Flux Pro on Replicate.
Stage 1: The Ordinary World - business owner stuck at ceiling
Stage 2: Meeting the Guide - hope, new capabilities revealed

Usage: python execution/generate_hero_path_images_flux.py
"""

import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

api_token = os.getenv("REPLICATE_API_TOKEN")
if not api_token:
    print("ERROR: REPLICATE_API_TOKEN not found in .env")
    sys.exit(1)

output_dir = Path(".tmp/hero-path-images-flux")
output_dir.mkdir(parents=True, exist_ok=True)

# Shared style instructions for consistency
STYLE = (
    "Digital illustration style, warm muted color palette with soft blues and golds. "
    "Clean vector-like aesthetic similar to modern infographic illustrations. "
    "Slightly stylized but grounded and realistic. NOT fantasy, NOT mystical, NOT cartoon. "
    "Professional business context. Landscape orientation 4:3. "
    "No text, no words, no letters, no watermarks in the image."
)

# STAGE 1: The Ordinary World
prompt_1 = (
    "A 60-year-old male small business owner sitting alone at a cluttered desk in a modest office. "
    "He looks tired and overwhelmed. Stacks of paper, a ringing phone, sticky notes everywhere. "
    "Through the window behind him you can see manufactured homes and mobile homes in a sales lot. "
    "The lighting is dim and warm but the mood is heavy — he's stuck, exhausted, at his ceiling. "
    "His posture shows someone who has been grinding for decades and is running out of steam. "
    "A coffee cup sits half-empty. The computer screen shows a basic spreadsheet. "
    + STYLE
)

# STAGE 2: Meeting the Guide
prompt_2 = (
    "The same 60-year-old male business owner, now standing next to a younger professional consultant "
    "who is showing him something on a modern tablet or large screen. The screen glows with a clean "
    "dashboard showing upward-trending graphs and pipeline stages. "
    "The business owner's expression is shifting from skepticism to cautious hope — eyes widening slightly. "
    "The consultant is pointing at the screen with confidence but warmth, not arrogance. "
    "The office is the same but the lighting is brighter now, more hopeful. "
    "Through the window, the same manufactured home lot is visible but now bathed in morning light. "
    "The mood is a turning point — the moment everything changes. "
    + STYLE
)

prompts = [
    ("stage1-ordinary-world.png", prompt_1),
    ("stage2-meeting-the-guide.png", prompt_2),
]

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "Prefer": "wait",
}

for filename, prompt in prompts:
    print(f"\nGenerating: {filename}")
    print(f"Prompt length: {len(prompt)} chars")

    try:
        # Use Flux 1.1 Pro (black-forest-labs/flux-1.1-pro)
        response = requests.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": "4:3",
                    "output_format": "png",
                    "output_quality": 95,
                    "safety_tolerance": 5,
                    "prompt_upsampling": True,
                }
            },
        )
        response.raise_for_status()
        prediction = response.json()
        prediction_id = prediction["id"]
        status = prediction.get("status")
        print(f"  Prediction ID: {prediction_id}, status: {status}")

        # Poll for completion
        poll_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        while status not in ("succeeded", "failed", "canceled"):
            time.sleep(3)
            poll_resp = requests.get(poll_url, headers={"Authorization": f"Bearer {api_token}"})
            poll_resp.raise_for_status()
            prediction = poll_resp.json()
            status = prediction["status"]
            print(f"  Status: {status}")

        if status == "succeeded":
            output = prediction.get("output")
            # Output can be a string URL or list of URLs
            if isinstance(output, list):
                image_url = output[0]
            else:
                image_url = output

            print(f"  Downloading from: {image_url[:80]}...")
            img_resp = requests.get(image_url)
            img_resp.raise_for_status()

            out_path = output_dir / filename
            out_path.write_bytes(img_resp.content)
            print(f"  Saved: {out_path} ({len(img_resp.content) / 1024:.0f} KB)")
        else:
            error = prediction.get("error", "Unknown error")
            print(f"  FAILED: {error}")

    except Exception as e:
        print(f"  ERROR: {e}")

print("\nDone.")
