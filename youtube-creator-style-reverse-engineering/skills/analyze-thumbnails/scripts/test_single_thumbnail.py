#!/usr/bin/env python3
"""Test Gemini 3 Pro Image with a single thumbnail to verify it works and get token count."""

import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()

# Configure Gemini
api_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: No Gemini API key found")
    exit(1)

genai.configure(api_key=api_key)

# Use Gemini 3 Pro Image
model = genai.GenerativeModel("models/gemini-3-pro-image-preview")

# Find first thumbnail
thumbnail_dirs = [
    Path("Resources/[1] YouTube/[01] OFFER - Big Idea & Packaging/My own Thumbnails"),
    Path("Resources/[1] YouTube/[01] OFFER - Big Idea & Packaging/Others Thumbnails"),
    Path("Resources/[1] YouTube/[01] OFFER - Big Idea & Packaging/Screenshot from popular videos to thumbnail mashups"),
]

test_image = None
for dir in thumbnail_dirs:
    if dir.exists():
        for img in dir.rglob("*.png"):  # Use rglob to search subdirectories
            test_image = img
            break
    if test_image:
        break

if not test_image:
    print("ERROR: No test image found")
    exit(1)

print(f"Testing with: {test_image.name}")
print(f"Model: models/gemini-3-pro-image-preview\n")

# Load image
image = Image.open(test_image)

# Simple test prompt
prompt = "Describe this YouTube thumbnail in detail. What colors, text, and visual elements do you see?"

print("Sending request...")
response = model.generate_content([prompt, image])

print(f"\n[SUCCESS]\n")
print(f"Response preview: {response.text[:200]}...\n")

# Get token counts
if hasattr(response, 'usage_metadata'):
    usage = response.usage_metadata
    print("=" * 60)
    print("TOKEN USAGE:")
    print("=" * 60)
    print(f"  Prompt tokens (text):     {usage.prompt_token_count:,}")
    print(f"  Response tokens:          {usage.candidates_token_count:,}")
    print(f"  Total tokens:             {usage.total_token_count:,}")
    print()

    # Estimate cost for all 136 images
    # Gemini 3 Pro Image pricing (approximate):
    # Input: $0.0025/1k tokens
    # Output: $0.01/1k tokens

    input_cost_per_1k = 0.0025
    output_cost_per_1k = 0.01

    single_input_cost = (usage.prompt_token_count / 1000) * input_cost_per_1k
    single_output_cost = (usage.candidates_token_count / 1000) * output_cost_per_1k
    single_total = single_input_cost + single_output_cost

    print(f"COST FOR THIS IMAGE:")
    print(f"  Input:  ${single_input_cost:.4f}")
    print(f"  Output: ${single_output_cost:.4f}")
    print(f"  Total:  ${single_total:.4f}")
    print()
    print("=" * 60)
    print(f"ESTIMATED COST FOR ALL 136 IMAGES:")
    print("=" * 60)
    total_cost = single_total * 136
    print(f"  ${total_cost:.2f}")
    print("=" * 60)
else:
    print("(Token usage metadata not available)")
