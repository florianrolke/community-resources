# story-telling-header

**A scroll-scrubbed cinematic video hero. Describe 4 scenes. Get a continuous camera-ascent.**

As the visitor scrolls, the hero plays a video like a flip-book tied to the scrollbar — a
smooth camera journey rising through four scenes, with headline "beats" fading in on each. It's
the [Apple-style scroll-scrub](https://www.apple.com/) effect, but the footage is AI-generated
from four prompts you write. Ships with two skins — a **blog** landing page and a **proposal**
page — plus two fully pre-generated examples so you can see it before spending a cent.

> Built with OpenRouter: **Nano Banana Pro** (Gemini 3 Pro Image) for the keyframes and
> **HappyHorse 1.1** (Alibaba) for the image-to-video.

---

## What it costs

You bring your own [OpenRouter](https://openrouter.ai) API key. One full hero:

| Step | Model | Qty | Cost |
|------|-------|-----|------|
| Keyframe images | `google/gemini-3-pro-image` | 4 | ~$0.32 |
| Scene videos | `alibaba/happyhorse-1.1` | 4 × ~5s | **4 × $0.639 = $2.56** |
| **Total per hero** | | | **≈ $2.90** |

The two examples in [`examples/`](examples/) are already generated — **previewing them is free.**

---

## Quickstart

```bash
git clone https://github.com/florianrolke/story-telling-header
cd story-telling-header
pip install -r requirements.txt

cp .env.example .env            # then paste your OPENROUTER_API_KEY into .env

# --- create your config: describe your 4 scenes (the only thing you must write) ---
python scripts/new_story.py     # guided wizard (recommended) — see "Guided setup" below
#   ...or start from an example and edit by hand:
#   cp examples/blog/story.config.json story.config.json

python scripts/generate_images.py   # 4 keyframes  -> assets/hero/  (~$0.32, review them!)
python scripts/generate_video.py    # 4 clips + stitched ascent.mp4 -> assets/hero/  (~$2.56, ~12 min)
python scripts/build.py             # -> dist/index.html

# preview (a local server is required — see note below)
python -m http.server 8000 --directory dist
# open http://localhost:8000
```

**Preview note:** open the page through a **local server**, not by double-clicking the file.
The scroll-scrub uses a `blob:` video source that only works over `http://` (see
[docs/gotchas.md](docs/gotchas.md)). Without a server it falls back to a still-image
cross-fade — still nice, but not the scrub.

---

## Guided setup — `new_story.py`

Don't want to hand-write JSON? Run the wizard:

```bash
python scripts/new_story.py
```

It asks the one question that matters first — **are you making a proposal or a blog page?** —
then leads you through a **customer journey** in four scenes:

- **Proposal** (win a client — the pattern behind a real client proposal): *the starting point →
  the work → the stakes → the summit.* You lead the client from where they stand today to the
  future you're selling them.
- **Blog / landing page** (show off a product — the pattern behind a product site): *the origin →
  the craft → the moment → the payoff.* You walk the product from where it comes from to what your
  customer gets.

For each scene it asks what it looks like and one headline, and it **bakes in the cinematic rules
for you** — every camera move drifts upward and the scenes brighten as they rise, so the four clips
feel like one continuous ascent. It writes `story.config.json`; then run the three generate/build
commands above.

---

## Describing the 4 scenes

Your entire creative input is four scenes in `story.config.json`. Each scene has two prompts:

- **`image_prompt`** — what the still *looks like* (the keyframe).
- **`motion_prompt`** — how the *camera moves*. **Always include an upward drift** ("slow crane
  up", "rising push-in") — that's what makes the four scenes feel like one continuous ascent.

Two tips that make it cinematic:

1. **Ramp the brightness** across the four scenes (darker → brighter) so the journey reads as
   a rise from ground to summit.
2. Keep a **consistent grade** — mention the same palette/lighting in every prompt so the
   crossfades feel like one film, not four clips.

```jsonc
{
  "id": "scene1",
  "image_prompt":  "Aerial golden-hour view of misty green mountains and a winding river valley, warm light breaking through clouds, photorealistic.",
  "motion_prompt": "Slow upward crane revealing more sky and valley, mist drifting, treetops swaying.",
  "beat_headline": "Where it begins.",
  "beat_highlight": "In the mountains.",   // rendered in the accent color
  "beat_sub":       "One sentence that sets the scene."
}
```

---

## Three examples to look at and borrow

All three are fully pre-generated — clone and preview them immediately, no key, no spend.
Copy any one's `story.config.json` as your starting point.

| Example | Style | Journey | Live demo |
|---------|-------|---------|-----------|
| [`examples/blog/`](examples/blog/) — *Mountain Honey Co.* | `blog` | mountains → bees → table → jar | [demo](https://story-header-blog.pages.dev) |
| [`examples/proposal/`](examples/proposal/) — *Acme × You* | `proposal` | workshop → desk → neighbourhood → countryside | [demo](https://story-header-proposal-acme.pages.dev) |
| [`examples/proposal-alt/`](examples/proposal-alt/) — *Ironline × You* | `proposal` | same page, alternate heavy-industry footage | [demo](https://story-header-proposal-alt.pages.dev) |

The two proposals share the same layout with **different generated footage** — a side-by-side of
how much the clips change the feel. Preview any locally:
```bash
python -m http.server 8001 --directory examples/blog/dist
python -m http.server 8002 --directory examples/proposal/dist
python -m http.server 8003 --directory examples/proposal-alt/dist
```

---

## Deploy

Static output — host `dist/` anywhere. Cloudflare Pages one-liner and the seekability caveat
are in [docs/deploy.md](docs/deploy.md).

---

## Docs

- [docs/how-it-works.md](docs/how-it-works.md) — the scroll → `currentTime` scrub, explained.
- [docs/gotchas.md](docs/gotchas.md) — the two bugs that will bite you (and the fixes baked in here):
  the `video.load()` NaN freeze and the `blob:` seekability fix.
- [docs/deploy.md](docs/deploy.md) — Cloudflare Pages.

---

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) on your PATH (stitches the clips)
- An OpenRouter API key

## License

MIT © Florian Rolke. You own everything you generate. Fonts are served from Google Fonts
([Merriweather](https://fonts.google.com/specimen/Merriweather),
[Source Sans 3](https://fonts.google.com/specimen/Source+Sans+3),
[Playfair Display](https://fonts.google.com/specimen/Playfair+Display)) under the OFL.
