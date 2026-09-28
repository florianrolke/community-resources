#!/usr/bin/env python3
"""
Turn scraped website text into a 50-word summary and up to 5 useful facts.

This is the n8n `AI Agent` node from the Google Maps workflow. The prompt is
Jack's, word for word — see prompts/website_summary.md.

One difference worth knowing about: the n8n version asked the model for JSON
and hoped. This uses the API's structured-output mode, which constrains
generation to the schema. You get valid JSON or an exception. Never a
half-parsed string that breaks three nodes downstream.

(The original workflow also had a bug here — its Google Sheets node wrote
`{{ $json.output }}`, the whole object, into the Summary column instead of
`{{ $json.output.summary }}`. Everyone who ran it got `[object Object]` in
their spreadsheet. That class of mistake is exactly what a typed return value
prevents.)

Usage:
    # Standalone, on a text file
    python -X utf8 scripts/02_local_businesses/summarize_website.py --file page.txt

    # Usually called for you by gmaps_lead_pipeline.py
"""

import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.env import load_env
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.claude import structured, load_prompt, DEFAULT_MODEL

fix_encoding()
load_env()

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "About 50 words: what they do, who they serve, what makes them different.",
        },
        "facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Up to 5 specific facts — awards, milestones, specialisms, differentiators.",
        },
    },
    "required": ["summary", "facts"],
    "additionalProperties": False,
}

# Cap the page text we send. Most business sites say everything useful in the
# first few thousand characters, and the rest is nav, footer, and cookie banner.
MAX_CHARS = 12000


def summarize_website(page_text: str, business_name: str = "", model: str = DEFAULT_MODEL) -> dict:
    """Return {"summary": str, "facts": [str, ...]}."""
    if not page_text or not page_text.strip():
        return {"summary": "", "facts": []}

    system, _ = load_prompt("website_summary")
    text = page_text[:MAX_CHARS]

    user = f"Website content for {business_name}:\n\n{text}" if business_name else f"Website content:\n\n{text}"

    result = structured(system=system, user=user, schema=SCHEMA, model=model, max_tokens=2048)
    result["facts"] = [f for f in (result.get("facts") or []) if f][:5]
    return result


def main():
    parser = argparse.ArgumentParser(description="Summarize website text (System 2, step 2)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Path to a file containing the page text")
    src.add_argument("--text", help="The page text directly")
    parser.add_argument("--name", default="", help="Business name, for context")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    page_text = open(args.file, encoding="utf-8", errors="replace").read() if args.file else args.text
    result = summarize_website(page_text, business_name=args.name, model=args.model)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
