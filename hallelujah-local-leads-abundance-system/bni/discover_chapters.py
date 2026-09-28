#!/usr/bin/env python3
"""Discover BNI chapters in a region using Perplexity Deep Research."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.windows_compat import fix_encoding
fix_encoding()

import argparse, json, requests, re
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


def discover_chapters(city: str, state: str, radius_miles: int = 50) -> list[dict]:
    """Use Perplexity to find BNI chapters near a city."""
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        print("[ERROR] PERPLEXITY_API_KEY required for chapter discovery")
        return []

    prompt = f"""Find all BNI (Business Network International) chapters within {radius_miles} miles of {city}, {state}.

For each chapter, provide:
- Chapter name
- Meeting day and time
- Meeting location/venue
- Chapter website URL (the specific BNI chapter page)
- Approximate number of members
- BNI region/portal (e.g., bni-nc.com, bni-mi.com)

Return as a JSON array. Example:
[
  {{
    "name": "Power Players",
    "meeting_day": "Tuesday",
    "meeting_time": "7:00 AM",
    "venue": "Marriott Hotel, 123 Main St",
    "url": "https://bni-nc.com/chapters/power-players",
    "members_approx": 35,
    "portal": "bni-nc.com"
  }}
]

Return ONLY the JSON array, no markdown."""

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=60,
        )
        if response.ok:
            content = response.json()["choices"][0]["message"]["content"]
            # Parse JSON from response
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines)
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                match = re.search(r'\[[\s\S]*\]', content)
                if match:
                    return json.loads(match.group(0))
                print(f"[ERROR] Could not parse JSON from Perplexity response")
                print(f"[DEBUG] Response content: {content[:500]}")
        else:
            print(f"[ERROR] Perplexity returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[ERROR] Discovery failed: {e}")
    return []


def build_chapters_config(chapters: list[dict], city: str, state: str) -> dict:
    """
    Convert discovered chapters into a chapters.json config format
    suitable for scrape_chapters.py.
    """
    config_chapters = []
    for ch in chapters:
        slug = ch.get("name", "").lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')

        config_chapters.append({
            "name": ch.get("name", "Unknown"),
            "slug": slug,
            "url": ch.get("url", ""),
            "meeting_day": ch.get("meeting_day", ""),
            "meeting_time": ch.get("meeting_time", ""),
            "venue": ch.get("venue", ""),
            "members_approx": ch.get("members_approx", 0),
            "city": city,
            "state": state,
        })

    portal = chapters[0].get("portal", "") if chapters else ""

    return {
        "portal": portal,
        "region": f"{city}, {state}",
        "discovered_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "chapters": config_chapters,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover BNI chapters in a region")
    parser.add_argument("--city", required=True, help="City name")
    parser.add_argument("--state", required=True, help="State abbreviation")
    parser.add_argument("--radius", type=int, default=50, help="Search radius in miles")
    parser.add_argument("--output", default="data/discovered_chapters.json",
                        help="Output file path (default: data/discovered_chapters.json)")
    parser.add_argument("--as-config", action="store_true",
                        help="Also save as a chapters.json config for scrape_chapters.py")
    args = parser.parse_args()

    chapters = discover_chapters(args.city, args.state, args.radius)
    print(f"\nFound {len(chapters)} BNI chapters near {args.city}, {args.state}")

    for ch in chapters:
        members = ch.get("members_approx", "?")
        print(f"  - {ch.get('name', '?')} ({ch.get('meeting_day', '?')} {ch.get('meeting_time', '?')}, ~{members} members)")
        if ch.get("venue"):
            print(f"    Venue: {ch['venue']}")
        if ch.get("url"):
            print(f"    URL: {ch['url']}")

    # Resolve output path relative to script directory
    script_dir = Path(__file__).resolve().parent
    output_path = script_dir / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {output_path}")

    # Optionally save as a config file for scrape_chapters.py
    if args.as_config and chapters:
        config = build_chapters_config(chapters, args.city, args.state)
        config_path = script_dir / "data" / "chapters.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"Saved config to {config_path}")
        print(f"\nNext step: python scrape_chapters.py --config data/chapters.json --all")
