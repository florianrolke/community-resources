# Consistent-Face Thumbnails

Make YouTube / LinkedIn thumbnails that show **the same face every time** (real character consistency) **plus premium 3D "infographic" cards** - all from **one photo of yourself** and, if you want, a reference of **your own brand colors and style**.

You upload a photo of your own face. The tool never ships anyone else's face - there's a placeholder where your photo goes, and you drop yours in. Same for your brand: point it at your colors and it matches your look instead of the default.

## What it does

- **Character consistency** - the person in every thumbnail is unmistakably *you*, because your photo is passed to the model as a real image input (not a text description) with a hard instruction to leave your face unaltered.
- **3D infographic cards** - premium, photographed-looking data cards (price ladders, pillars, numbered systems) driven by a simple prompt file. Your face is optional on these.
- **Your brand, not a template** - keep the clean default text style, or pass your own colors / a brand reference image and the thumbnail matches your brand.
- **Costs almost nothing** - runs on one API. See the money math below.

## The one thing that makes the face consistent

The model is given **your face photo as an image input** under the key `input_urls`, and the prompt contains this line:

> keep their EXACT face, hair, and natural expression completely unaltered - do not beautify, restyle, age, slim, or augment their facial features in any way.

If you pass the reference under the wrong key, the model silently ignores it and invents a generic stranger. This repo already uses the right key - you don't have to think about it.

## APIs you need

| Service | What for | Required | Get a key |
|--------|----------|----------|-----------|
| **Kie AI** | Image generation (`gpt-image-2-image-to-image`) + temporary image hosting | **Yes - this is the only one** | https://kie.ai |

That's it. One key. No OpenAI account, no cloud storage, no image host - Kie hosts your reference upload temporarily for you.

## Cost - how many images for $5?

Kie prices in credits. **$5 tops up 1,000 credits.** Each thumbnail costs **~10 credits**.

```
1,000 credits  ÷  10 credits per image  =  100 images
```

**$5 = 100 thumbnails.** That's **5 cents per thumbnail**. A dry run (the default) costs **0 credits**, so you can perfect the prompt for free and only spend when you add `--live`.

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. add your key
cp .env.example .env          # then paste your Kie key into .env

# 3. add YOUR face (a clear, well-lit photo, face unobstructed)
#    drop it at assets/your-face.png

# 4. dry run - costs nothing, prints the exact request
python thumbnail_pipeline.py generate \
  --headline "The One Habit That 10x'd My Output" \
  --slug one-habit \
  --face assets/your-face.png

# 5. when it looks right, spend ~10 credits
python thumbnail_pipeline.py generate \
  --headline "The One Habit That 10x'd My Output" \
  --slug one-habit \
  --face assets/your-face.png \
  --live
```

## Match your own brand

Keep the default look, or make it yours:

```bash
python thumbnail_pipeline.py generate \
  --headline "Ship Faster" --slug ship-faster \
  --face assets/your-face.png \
  --brand-ref assets/your-brand-style.png \
  --brand-colors "#0B5FFF,#FFFFFF" \
  --brand-notes "clean, minimal, tech-startup feel" \
  --live
```

- `--brand-colors` - your hex colors for the text/accents.
- `--brand-notes` - a few words on the feel.
- `--brand-ref` - an image of your existing brand (a past thumbnail, a style tile). The model matches its palette and mood.

## 3D infographic cards

For a photographed 3D data card instead of a talking-head thumbnail, edit the prompt file (start from [`prompts/infographic-template.txt`](prompts/infographic-template.txt)) and run:

```bash
python thumbnail_pipeline.py generate \
  --mode infographic \
  --slug pricing-ladder \
  --prompt-file prompts/infographic-template.txt \
  --face assets/your-face.png \
  --live
```

Each layer in the template is one thing the image has to accomplish (grab attention, prove the claim, feel physical instead of AI-generated). Keep on-card text to ~5 short rows so it renders crisply.

## Notes

- **Dry-run by default.** Nothing is generated (and nothing is spent) unless you pass `--live`.
- **Your face and your key never leave your machine except to Kie.** `.env`, your photos, and outputs are all gitignored.
- **Aspect / resolution** default to `16:9` / `2K`; override with `--aspect-ratio` / `--resolution`.
- Every live generation is logged locally to `output/generation-log.jsonl`.

## License

MIT - see [LICENSE](LICENSE).
