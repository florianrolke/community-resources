# yt-thumbnail-repurposer

Scrape high-performing YouTube thumbnails from any channel and regenerate them with your face, brand, and colors using [Kie.ai](https://kie.ai) image-to-image.

**The idea:** The best thumbnails already exist. Find what's performing in your niche → let AI adapt the layout, composition, and visual energy to your brand.

---

## How It Works

```
1. Scrape thumbnails from any YouTube channel (via yt-dlp, free)
   ↓
2. Rank by view count → pick the best performers
   ↓
3. Send each thumbnail to Kie.ai with your prompt
   ↓
4. Download your augmented thumbnail (4K PNG)
```

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/florianrolke/yt-thumbnail-repurposer
cd yt-thumbnail-repurposer
pip install -r requirements.txt

# 2. Add your Kie.ai API key
cp .env.example .env
# Edit .env and add: KIE_AI_API_KEY=your_key_here

# 3. Full pipeline: scrape top 20 from a channel, augment top 3
python pipeline.py \
  --channel "@MrBeast" \
  --scrape 20 \
  --augment 3 \
  --prompt "Replace the person with a professional man in a dark suit, keep all composition and colors" \
  --style mrbeast-energy
```

---

## Example: "4 HOUR COURSE" Thumbnail

> **Source thumbnail:** Nick Saraev's Claude Code 4-hour course video — 3.5M+ views, Anthropic logo, cinematic orange backlight, person silhouetted at laptop.

This is the kind of thumbnail this tool is built for. High view count, distinctive visual formula, immediately replicable layout.

**Step 1 — Scrape Nick's channel:**
```bash
python scrape_channel_thumbnails.py --channel "@nickosaraev" --limit 30 --sort views
```

Output:
```
thumbnails/nickosaraev/
├── dQw4w9WgXcY__4-hour-claude-code-course.jpg   ← 3.5M views
├── abc123__how-i-made-10k-with-ai.jpg
└── metadata.json
```

**Step 2 — Augment the top thumbnail:**
```bash
python kie_image_to_image.py \
  --source "thumbnails/nickosaraev/dQw4w9WgXcY__4-hour-claude-code-course.jpg" \
  --prompt "Keep the exact layout: person silhouetted at laptop with dramatic orange-amber backlight from behind, dark room, cinematic mood. Replace the person with a professional man in a dark suit. Keep the bold white text overlay and the AI logo icon in orange on the left. Same color grading." \
  --style cinematic-dark
```

**What Kie.ai generates:**

The output thumbnail keeps:
- ✅ Silhouette-at-laptop composition (proven hook for course thumbnails)
- ✅ Dramatic orange/amber backlighting (creates cinematic tension)
- ✅ Dark room atmosphere (premium production feel)
- ✅ Bold text area in the upper portion
- ✅ Icon placement (left side, orange)

And swaps:
- 🔄 The person → your face / suited professional
- 🔄 Text content → your course title
- 🔄 Logo → your brand icon

**Full pipeline version (one command):**
```bash
python pipeline.py \
  --channel "@nickosaraev" \
  --scrape 30 \
  --rank 1 \
  --prompt "Person in dark suit at laptop, dramatic orange backlight from behind, cinematic dark room, keep bold text layout and icon" \
  --style cinematic-dark
```

---

## All Commands

### Scrape thumbnails from any channel

```bash
# Sort by date (default)
python scrape_channel_thumbnails.py --channel "@hubermanlab" --limit 20

# Sort by views (best performers first)
python scrape_channel_thumbnails.py --channel "@MrBeast" --limit 50 --sort views

# Custom output folder
python scrape_channel_thumbnails.py --channel "@alex_hormozi" --limit 30 --output my_thumbnails/
```

### Augment a single thumbnail

```bash
python kie_image_to_image.py \
  --source thumbnails/mrBeast/abc123__title.jpg \
  --prompt "Replace the person with a professional suited man, keep all text and graphic elements"
```

### Augment a whole folder

```bash
python kie_image_to_image.py \
  --folder thumbnails/mrBeast/ \
  --prompt "Professional suited man, same composition and energy" \
  --limit 5 \
  --style mrbeast-energy
```

### Full pipeline

```bash
# Top 3 most-viewed thumbnails from a channel
python pipeline.py \
  --channel "@YourNicheChannel" \
  --scrape 30 \
  --augment 3 \
  --prompt "your augmentation prompt" \
  --style cinematic-dark
```

---

## Style Presets

Pass `--style` to append a proven visual direction to your prompt:

| Preset | Best for |
|--------|---------|
| `cinematic-dark` | Course thumbnails, serious topics, tech/AI content |
| `mrbeast-energy` | High-energy content, entertainment, challenges |
| `educational` | Business, tutorials, how-to content |
| `tech-ai` | AI/tech topics, developer content |

---

## Writing Effective Prompts

The prompt tells Kie.ai what to **change** and what to **keep**.

**Template:**
```
Keep [composition / layout / colors / text position].
Replace [person / background / logo] with [your description].
Add [any new element if needed].
[Style descriptor: cinematic, bold, clean, etc.]
```

**Example prompts for different thumbnail types:**

Course thumbnail (like "4 HOUR COURSE"):
```
Keep the dramatic backlit silhouette composition, dark room atmosphere, orange/amber glow from behind,
and bold text overlay. Replace the person with a professional man in a charcoal suit. Keep the
company logo icon in the top left in orange. Cinematic 4K quality.
```

Reaction/commentary thumbnail:
```
Keep the split-screen layout with large bold text on the right half.
Replace the face on the left with a professional man in a suit showing a surprised expression.
Keep all graphic elements and color scheme identical.
```

Before/after thumbnail:
```
Keep the left-right before/after layout with the dividing line.
Replace both person instances with a suited professional.
Keep background colors, text labels, and arrow graphics exactly as-is.
```

---


---

## Face Swap with Gemini (Recommended)

The `gemini_faceswap.py` script passes your **actual reference photo** alongside the source thumbnail to Google Gemini's image model in a single multimodal call. This produces accurate face swaps because the model sees your real face — not a text description of it.

> **Why this beats text-to-image:** Describing a face in words generates a generic face. Showing Gemini a reference photo locks it to *your* actual features, hair style, and facial structure.

### Quick start

```bash
# 1. Add your Gemini key to .env
GOOGLE_GEMINI_API_KEY=your_key_here

# 2. Swap your face into a single thumbnail
python gemini_faceswap.py \
  --source thumbnails/channel/video.jpg \
  --reference my_photo.jpg

# 3. Control pose, zoom, or expression
python gemini_faceswap.py \
  --source thumbnails/channel/video.jpg \
  --reference my_photo.jpg \
  --prompt "person facing camera, smiling warmly, zoomed in waist-up"

# 4. Batch — process a full channel folder
python gemini_faceswap.py \
  --folder thumbnails/mrBeast/ \
  --reference my_photo.jpg \
  --limit 5
```

### How it works

1. Loads your reference photo and the source thumbnail
2. Sends both images to Gemini with structured rules:
   - Keep layout, text, background, and color grade pixel-identical
   - Replace only the face and hair with yours from the reference
   - Match head angle, wardrobe, and lighting from the original
3. Returns a 16:9 PNG with your face inserted

### Tips for best results

- Use a **clear, well-lit reference photo** facing the camera directly
- Source thumbnails with a **clearly visible, forward-facing person** work best
- Use `--prompt` to adjust pose/zoom/expression without changing identity
- If face drift occurs, add more specifics to `--identity` (hair color, beard, etc.)
- Download source thumbnails via `scrape_channel_thumbnails.py` — YouTube CDN thumbnails are clean, no player overlays or timestamps

### Cost

| Step | Cost |
|------|------|
| Gemini face-swap per image | ~$0.15–0.25 |
| 10 face-swapped thumbnails | ~$1.50–2.50 |

## Requirements

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — for YouTube scraping (free, no API needed)
- [Kie.ai](https://kie.ai) API key — for image-to-image generation
- `requests`, `python-dotenv`, `Pillow`

```bash
pip install -r requirements.txt
```

---

## Output Structure

```
thumbnails/
└── channelname/
    ├── VIDEO_ID__video-title.jpg    ← scraped thumbnails
    └── metadata.json                ← title, views, dates

output/
└── augmented_01_VIDEO_ID__title_kie.png   ← your augmented thumbnails
```

---

## Cost

| Step | Cost |
|------|------|
| Scraping thumbnails | Free (yt-dlp, no API) |
| Kie.ai image generation | ~$0.05–0.15 per image (4K Nano Banana 2) |
| 10 augmented thumbnails | ~$0.50–$1.50 |

---

## License

MIT — free to use, modify, and distribute.
