# Put your own images here

Nothing in this folder is shipped with the repo - it is where **your** images live. They stay on your machine (gitignored) and are only uploaded to Kie for the generation call.

## 1. Your face (required for a consistent face)

Drop a photo of yourself here and name it **`your-face.png`** (or `.jpg`).

Best results:
- A clear, well-lit photo where your face is fully visible and unobstructed.
- Looking toward the camera, neutral or warm expression.
- Higher resolution is better. One good photo is enough; the tool reuses it for every thumbnail so you always look the same.

Then run with `--face assets/your-face.png`.

## 2. Your brand style (optional)

Want the thumbnail to match your brand instead of the default white + accent look? Drop a reference here as **`your-brand-style.png`** - a past thumbnail, a brand board, or a style tile that shows your colors and feel.

Then add `--brand-ref assets/your-brand-style.png` (and optionally `--brand-colors "#..,#.."` and `--brand-notes "..."`).

---

The repo intentionally ships **no face and no brand image** - you provide your own so every thumbnail is yours.
