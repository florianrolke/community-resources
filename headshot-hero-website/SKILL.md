# Skill: Headshot Cutout Processing

## Purpose
Transform a low-resolution headshot thumbnail into a high-quality, full-body transparent cutout suitable for premium website hero sections. Solves the common problem of prospect headshots being tiny thumbnails (250px) that look pixelated and have abrupt shoulder crops when used as floating cutouts.

## Pipeline (4 Replicate calls, ~$0.20 total)

### Step 1: Source the highest-resolution original
Before any AI processing, try to get the largest version of the photo available.

**Common CDN resize patterns to bypass:**
```
# Mirus CDN (State Farm, insurance sites)
# Thumbnail:  https://ephemera.mirus.io/imgr/250x0/https://storage.googleapis.com/...
# Full-res:   Change 250x0 to 1000x0 or 2000x0
url = url.replace('/250x0/', '/1000x0/')

# Cloudinary
# Thumbnail:  https://res.cloudinary.com/.../w_200,h_200/image.jpg
# Full-res:   Remove the transformation segment

# WordPress
# Thumbnail:  https://site.com/wp-content/uploads/photo-150x150.jpg
# Full-res:   https://site.com/wp-content/uploads/photo.jpg (remove dimensions)

# Google Storage (direct)
# Usually already full-res, no resize parameter
```

**Download with Python** (avoids Windows curl SSL issues):
```python
import urllib.request
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
data = urllib.request.urlopen(req).read()
with open(output_path, 'wb') as f:
    f.write(data)
```

### Step 2: Upscale to 4K (Real-ESRGAN)
```python
REPLICATE_API_TOKEN=xxx python -c "
import replicate
output = replicate.run(
    'nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa',
    input={
        'image': open('headshot.jpg', 'rb'),
        'scale': 4,
        'face_enhance': True  # GFPGAN face restoration
    })
data = output.read()
with open('headshot-4k.png', 'wb') as f:
    f.write(data)
"
```
- **Cost**: ~$0.02
- **face_enhance=True**: Uses GFPGAN to sharpen facial features (critical for small source images)
- 250px -> 1000px -> 4000px is the sweet spot (upscale source first if possible)

### Step 3: Outpaint body/torso (Flux Fill Dev)
Extends the image downward to show shoulders, chest, and torso — eliminates the "obviously cropped" look.

```python
from PIL import Image, ImageDraw
import io, replicate

img = Image.open('headshot-4k.png').resize((1024, 1024), Image.LANCZOS)

# Create canvas: 1024 wide, 1536 tall (50% taller = room for torso)
canvas = Image.new('RGB', (1024, 1536), (180, 190, 175))  # neutral bg
canvas.paste(img, (0, 0))

# Mask: black = keep, white = generate
mask = Image.new('RGB', (1024, 1536), (0, 0, 0))
draw = ImageDraw.Draw(mask)
# Blend zone: gradual transition from original to generated
for y in range(960, 1024):
    val = int((y - 960) / 64 * 255)
    draw.line([(0, y), (1023, y)], fill=(val, val, val))
draw.rectangle([(0, 1024), (1023, 1535)], fill=(255, 255, 255))

canvas_buf = io.BytesIO(); canvas.save(canvas_buf, format='PNG'); canvas_buf.seek(0)
mask_buf = io.BytesIO(); mask.save(mask_buf, format='PNG'); mask_buf.seek(0)

output = replicate.run(
    'black-forest-labs/flux-fill-dev',
    input={
        'image': canvas_buf,
        'mask': mask_buf,
        'prompt': 'dark charcoal suit jacket lapels, [COLOR] tie, white collared dress shirt, chest and torso of professional businessman, blurred background, corporate photography, no text, no words, no letters, no watermark',
        'guidance': 25,
        'steps': 40,
        'output_format': 'png',
    })
data = output.read()
with open('outpainted.png', 'wb') as f:
    f.write(data)
```

**Key parameters:**
- **Canvas size**: 1024x1536 (SDXL-native width, 1.5x height for torso room)
- **Blend zone**: y=960-1024 gradient prevents visible seam between original and generated
- **guidance=25**: Higher than default — keeps generated content consistent with original
- **steps=40**: More steps = better quality for inpainting
- **Prompt**: Describe the CLOTHING visible in the original (suit color, tie color, shirt). Add "no text, no words" to prevent text artifacts.
- **Cost**: ~$0.05-0.08

**Prompt template by attire:**
- Suit: `dark charcoal suit jacket lapels, [tie color] tie, white dress shirt, torso, corporate photography`
- Casual: `[shirt color] collared polo shirt, torso and arms, professional photography`
- Uniform: `[uniform description], torso visible, professional portrait`

### Step 4: Upscale the outpainted result
Same Real-ESRGAN call as Step 2, applied to the outpainted image:
```python
output = replicate.run('nightmareai/real-esrgan:...', input={'image': open('outpainted.png', 'rb'), 'scale': 4, 'face_enhance': True})
```
- Takes 832x1248 -> 3328x4992
- **Cost**: ~$0.02

### Step 5: Remove background (rembg)
```python
output = replicate.run(
    'cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003',
    input={'image': open('outpainted-4k.png', 'rb')})
data = output.read()
with open('final-cutout.png', 'wb') as f:
    f.write(data)
```
- Returns RGBA PNG with transparent background
- **Cost**: ~$0.02

### Step 6: Optimize for web
```python
from PIL import Image
img = Image.open('final-cutout.png')
# Resize to 1200px wide (sharp enough for hero, reasonable file size)
w, h = img.size
new_w = 1200
new_h = int(h * new_w / w)
img = img.resize((new_w, new_h), Image.LANCZOS)
img.save('brad-siok.png', optimize=True, compress_level=9)
# Target: ~1.5-2MB for a hero cutout PNG with transparency
```

## CSS Integration

### Floating cutout in hero section (Royal Wines style)
```css
.hero-cutout {
    position: absolute;
    right: 5%; bottom: -40px;
    height: 92vh; max-height: 860px;
    z-index: 3;
    filter: drop-shadow(0 20px 60px rgba(0,0,0,0.3));
    object-fit: contain;
    object-position: bottom;
    /* Bottom fade — dissolves torso into the page naturally */
    mask-image: linear-gradient(to bottom, black 0%, black 70%, transparent 97%);
    -webkit-mask-image: linear-gradient(to bottom, black 0%, black 70%, transparent 97%);
}
@media (max-width: 768px) {
    .hero-cutout {
        right: -5%; height: 55vh; max-height: 450px;
        opacity: 0.4;  /* Fades on mobile so text stays readable */
    }
}
```

**Why bottom: -40px**: Pushes the very bottom edge (where outpainting meets nothing) below the viewport fold. Combined with the CSS mask gradient, the cutout dissolves seamlessly into the page background.

### Hero background setup
Pair with a scenic background + asymmetric gradient overlay (heavier on text side):
```css
.hero-gradient {
    position: absolute; inset: 0;
    background: linear-gradient(105deg,
        rgba(26,35,50,0.88) 0%,    /* Dark over text */
        rgba(26,35,50,0.72) 30%,
        rgba(26,35,50,0.40) 55%,
        rgba(26,35,50,0.15) 75%,   /* Light over cutout */
        rgba(26,35,50,0.08) 100%
    );
}
/* Bottom vignette blends hero into next section */
.hero-bottom-fade {
    position: absolute; bottom: 0; left: 0; right: 0; height: 200px;
    background: linear-gradient(to top, #faf8f5 0%, transparent 100%);
    z-index: 2;
}
```

## Gotchas & Lessons Learned

1. **Windows curl SSL errors**: `CRYPT_E_REVOCATION_OFFLINE` — use Python `urllib.request` instead of curl for image downloads
2. **Replicate auth on Windows**: `source .env` fails silently on some .env files. Pass token explicitly: `REPLICATE_API_TOKEN=xxx python -c "..."`
3. **Replicate FileOutput**: `replicate.run()` returns `FileOutput` objects — call `.read()` for bytes, don't convert to string
4. **SDXL outpainting dark fill**: If canvas fill color is too dark (grey/black), SDXL generates dark/black content. Use a neutral light color (180,190,175) matching the image edges
5. **Flux text artifacts**: Flux Fill can generate random text in outpainted areas. Always include "no text, no words, no letters, no watermark" in prompt
6. **OneDrive file locks**: Copy files to `/tmp/` or `%TEMP%` before deploying if OneDrive sync locks them
7. **Never modify the face**: The entire point is keeping the real face. Only outpaint BELOW the original crop line. The blend zone (y=960-1024) ensures seamless transition without touching facial features.
8. **PNG transparency**: rembg outputs RGBA. Keep as PNG (not JPEG) to preserve transparency for the floating cutout effect.

## File Locations (reference)
- Intermediate files: `.tmp/videos/{slug}-headshot-*.png`
- Final cutout: `.tmp/sites/{slug}/brad-siok.png` (or `{name}.png`)
- Deployed alongside `index.html` via `deploy_site_files()`

## Cost Summary
| Step | Model | Cost |
|------|-------|------|
| Upscale source | Real-ESRGAN | ~$0.02 |
| Outpaint torso | Flux Fill Dev | ~$0.05-0.08 |
| Upscale outpainted | Real-ESRGAN | ~$0.02 |
| Remove background | rembg | ~$0.02 |
| **Total** | | **~$0.11-0.14** |
