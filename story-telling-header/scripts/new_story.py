#!/usr/bin/env python3
"""
Interactive wizard: build a story.config.json by describing a customer journey.

Run it, answer a few questions, and it writes a ready-to-generate config:

    python scripts/new_story.py

It first asks whether you're making a PROPOSAL (win a client) or a BLOG / landing
page (show off a product), then walks you through a 4-scene customer journey. It bakes in the two cinematic rules for
you automatically: every camera move drifts upward (so the four scenes feel like
one continuous ascent) and the scenes brighten as they rise.

Output: story.config.json at the repo root (or --out PATH). Then:
    python scripts/generate_images.py   # 4 keyframes
    python scripts/generate_video.py    # 4 clips -> ascent.mp4
    python scripts/build.py             # -> dist/
"""
import json, sys, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---- the two journey frameworks (this is the "lead them through it" part) ----
FRAMEWORKS = {
    "proposal": {
        "label": "Proposal — win a client (lead them to a decision)",
        "brand_q": "Your headline (e.g. 'Acme x You' or your name)",
        "prepared_for_q": "Who is this proposal for? (client / company name)",
        "eyebrow_tmpl": "PROPOSAL - PREPARED FOR {prepared_for}",
        "intro": "A proposal leads the client from where they are today to the future you're\n"
                 "selling them. Picture their world as a rising journey in four scenes:",
        "scenes": [
            ("The starting point",
             "Where your client stands today - the ground-level reality of their world.",
             "e.g. an industrial workshop floor at blue hour"),
            ("The work",
             "Your system / your craft in motion - what you actually do for them.",
             "e.g. a calm desk at sunrise where the work gets done"),
            ("The stakes",
             "What it protects, or who it's really for - why this matters.",
             "e.g. a warm family neighbourhood at dusk"),
            ("The summit",
             "The future you're leading them to - the aspiration, the payoff.",
             "e.g. open countryside at golden hour, freedom and calm"),
        ],
        "palette": {"ink": "#0e1a28", "gold": "#c9a068", "gold_bright": "#dcb87e", "cream": "#f2e8dc"},
        "cta": {"primary": ("Let's go", "mailto:you@example.com"),
                 "secondary": ("Read the proposal", "#body")},
    },
    "blog": {
        "label": "Blog / landing page — show off a product (the honey-site pattern)",
        "brand_q": "Your brand name (e.g. 'Mountain Honey Co.')",
        "prepared_for_q": None,
        "eyebrow_tmpl": "{brand}",
        "intro": "A product page tells the story of the product as a rising journey in four\n"
                 "scenes, from where it comes from to what your customer gets:",
        "scenes": [
            ("The origin",
             "Where your product begins - the place, the source, the raw material.",
             "e.g. misty green mountains and a river valley at golden hour"),
            ("The craft",
             "How it's made - the process, the hands, the care.",
             "e.g. hands lifting a honeycomb frame, bees, warm light"),
            ("The moment",
             "Your product in your customer's real life.",
             "e.g. a family table with bread, tea and honey"),
            ("The payoff",
             "The result - the product itself, the thing they take home.",
             "e.g. a jar of golden honey backlit against the hills"),
        ],
        "palette": {"ink": "#1b1206", "gold": "#e0a526", "gold_bright": "#f6c453", "cream": "#fdf7ec"},
        "cta": {"primary": ("Order now", "#body"),
                 "secondary": ("Learn more", "#body")},
    },
}

# camera moves per scene position — always upward, so it reads as one ascent
MOVES = [
    "Slow upward crane / gentle push-in, tilting up to reveal more of the scene.",
    "Slow rise and soft push-in toward the subject.",
    "Slow rising crane drifting gently forward over the scene.",
    "Slow forward glide with a gentle rise, opening up the horizon.",
]
# brightness ramp appended to each image prompt so the journey lifts from dark to bright
BRIGHTNESS = [
    "moody blue-hour lighting, the darkest scene",
    "soft early-morning golden light, a touch brighter",
    "warm late-afternoon light, brighter still",
    "radiant golden-hour light, the brightest and warmest scene",
]
GRADE = ("photorealistic, cinematic, consistent color grade with deep shadows and warm "
         "golden highlights, 16:9, no text, no watermark")


def ask(prompt, default=""):
    d = f" [{default}]" if default else ""
    try:
        v = input(f"  {prompt}{d}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled."); sys.exit(1)
    return v or default


def choose_style():
    print("\nWhat are you making?")
    keys = list(FRAMEWORKS)
    for i, k in enumerate(keys, 1):
        print(f"  [{i}] {FRAMEWORKS[k]['label']}")
    while True:
        c = ask("Choose 1 or 2", "1")
        if c in ("1", "2"):
            return keys[int(c) - 1]
        if c.lower() in FRAMEWORKS:
            return c.lower()


def wrap(s, indent="      "):
    return "\n".join(textwrap.wrap(s, 78, initial_indent=indent, subsequent_indent=indent))


def main():
    out = ROOT / "story.config.json"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])

    print("=" * 70)
    print(" story-telling-header - describe your journey, get a cinematic hero")
    print("=" * 70)

    style = choose_style()
    fw = FRAMEWORKS[style]

    brand = ask(fw["brand_q"], "Your Brand")
    prepared_for = ask(fw["prepared_for_q"], "Acme Co.") if fw["prepared_for_q"] else ""
    eyebrow = fw["eyebrow_tmpl"].format(brand=brand, prepared_for=prepared_for)

    print("\n" + fw["intro"] + "\n")

    scenes = []
    for i, (title, guide, example) in enumerate(fw["scenes"]):
        print(f"--- Scene {i+1}/4 - {title} ---")
        print(wrap(guide))
        print(wrap(f"({example})", indent="      "))
        desc = ask("Describe what this scene looks like", example)
        image_prompt = f"{desc}. {BRIGHTNESS[i]}. {GRADE}."
        motion = ask("Camera motion (Enter for the recommended upward move)", MOVES[i])
        headline = ask("Headline for this scene (short)", title + ".")
        highlight = ask("Word(s) to highlight in gold (Enter to skip)", "")
        sub = ask("One supporting sentence", "")
        scenes.append({
            "id": f"scene{i+1}",
            "image_prompt": image_prompt,
            "motion_prompt": motion,
            "beat_headline": headline,
            "beat_highlight": highlight,
            "beat_sub": sub,
        })
        print()

    p_label, p_href = fw["cta"]["primary"]
    s_label, s_href = fw["cta"]["secondary"]
    print("--- Call to action ---")
    cta_primary = {"label": ask("Primary button label", p_label),
                    "href": ask("Primary button link", p_href)}
    cta_secondary = {"label": ask("Secondary button label (Enter to skip)", s_label),
                      "href": ask("Secondary button link", s_href)}

    config = {
        "style": style,
        "brand": brand,
        "site_url": "https://example.com",
        "palette": fw["palette"],
        "hero": {
            "eyebrow": eyebrow,
            "track_height": "520vh",
            "scenes": scenes,
            "cta_primary": cta_primary,
            "cta_secondary": cta_secondary,
        },
        "body": {"note": "Add your page body here - see examples/*/story.config.json for the shape."},
    }
    out.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 70)
    print(f"Wrote {out}")
    print("Next:")
    print("  python scripts/generate_images.py   # 4 keyframes (review them!)")
    print("  python scripts/generate_video.py    # 4 clips -> ascent.mp4")
    print("  python scripts/build.py             # -> dist/index.html")
    print("=" * 70)


if __name__ == "__main__":
    main()
