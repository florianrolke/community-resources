# headshot-hero-website

Take any business owner's website, find their photo, remove the background, and rebuild their site with them floating as the hero — for ~$0.15 in API credits.

---

## What this does

Most small business websites have one thing in common: a bad headshot buried somewhere on the page. This pipeline finds it, enhances it, and turns it into the centrepiece of a completely redesigned site.

**Input:** A business website URL.

**Output:** A live redesigned page with the owner floating as a transparent cutout hero, deployed to a custom subdomain in minutes.

---

## The pipeline

```
Step 1: Scrape website
  → Find owner's headshot URL (from About page, nav, bio section)
  → Bypass CDN resize patterns to get full-resolution original

Step 2: Enhance photo (Replicate API)
  → Upscale to 4K via Real-ESRGAN + GFPGAN face restoration      (~$0.02)
  → Outpaint torso/shoulders via Flux Fill Dev                    (~$0.06)
  → Upscale outpainted result                                      (~$0.02)
  → Remove background via rembg → transparent PNG                  (~$0.02)

Step 3: Redesign website
  → Generate luxury redesign using brand colors/fonts from scrape
  → Float the cutout PNG as hero section (right side, bottom-anchored)
  → Add gradient overlay, scroll reveals, CTA

Step 4: Deploy
  → Push to GitHub deploy repo
  → Coolify auto-builds nginx Docker container
  → Cloudflare DNS A record
  → SSL via Traefik Let's Encrypt
  → Live in ~2 minutes

Total cost: ~$0.15 per prospect
```

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/Florian1995-ai/headshot-hero-website
cd headshot-hero-website

# 2. Install dependencies
pip install replicate firecrawl-py pillow python-dotenv requests anthropic

# 3. Configure
cp .env.example .env
# edit .env with your API keys

# 4. Run the full pipeline on any business website
python execution/full_transformation.py --url "https://example.com" --slug example-name

# Output: live at https://example-name.preview.yourdomain.com
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `execution/full_transformation.py` | Master pipeline — scrape → enhance → redesign → deploy |
| `execution/generate_hero_path_images_flux.py` | Outpaint + upscale headshot via Flux Fill Dev + Real-ESRGAN |
| `execution/animate_hero_image.py` | Add motion to the hero cutout (Kling/Veo image-to-video) |
| `execution/generate_hero_proposal.py` | Generate the full HTML page with floating cutout hero |
| `execution/capture_website_screenshot.py` | Scrape branding + screenshot from any URL via Firecrawl |

---

## Photo processing detail

The biggest challenge: prospect headshots are almost always small, cropped at the shoulders, and low resolution. The pipeline solves this in 4 Replicate API calls:

1. **Bypass CDN resizing** — most insurance/finance sites serve thumbnails via CDN (e.g. `250x0` in the URL). We strip the resize parameter to get the original.

2. **4K upscale** — Real-ESRGAN with `face_enhance=True` (GFPGAN) sharpens facial features that look blurry at 250px. 

3. **Torso outpainting** — Flux Fill Dev extends the image downward on a 1024×1536 canvas. A blend gradient at y=960–1024 prevents any visible seam. The prompt describes the clothing visible in the original so the generated torso matches.

4. **Background removal** — rembg returns an RGBA PNG. The transparent background is what enables the "floating" CSS effect.

The final cutout is placed via CSS:
```css
.hero-cutout {
    position: absolute;
    right: 5%; bottom: -40px;
    height: 92vh;
    mask-image: linear-gradient(to bottom, black 70%, transparent 97%);
    filter: drop-shadow(0 20px 60px rgba(0,0,0,0.3));
}
```

The bottom fade dissolves the torso seamlessly into the page — no hard edges, no obvious crop.

---

## Required API keys

| Key | Used for | Get it at |
|-----|---------|-----------|
| `REPLICATE_API_TOKEN` | Photo enhancement (upscale, outpaint, rembg) | replicate.com |
| `FIRECRAWL_API_KEY` | Website scraping + screenshot | firecrawl.dev |
| `ANTHROPIC_API_KEY` | Copywriting for redesigned page | anthropic.com |
| `GITHUB_TOKEN` | Push HTML to deploy repo | github.com/settings/tokens |
| `COOLIFY_API_TOKEN` | Register domain + trigger rebuild | your Coolify instance |
| `CLOUDFLARE_API_TOKEN` | Create DNS A record | dash.cloudflare.com |

See `.env.example` for the full list.

---

## Cost breakdown

| Step | Model | Cost |
|------|-------|------|
| Upscale source photo | Real-ESRGAN | ~$0.02 |
| Outpaint torso | Flux Fill Dev | ~$0.05–0.08 |
| Upscale outpainted | Real-ESRGAN | ~$0.02 |
| Remove background | rembg | ~$0.02 |
| Website scrape | Firecrawl | ~$0.01 |
| **Total** | | **~$0.12–0.15** |

---

## See it live

Demo built with this pipeline: [teamsiok.client.florianrolke.com](https://teamsiok.client.florianrolke.com)
