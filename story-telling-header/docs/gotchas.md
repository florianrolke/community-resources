# Gotchas (already fixed in this repo)

These two bugs cost real debugging time. Both are handled in `templates/hero.js.tmpl` — this
page explains them so you don't re-introduce them if you modify the engine.

## 1. The `video.load()` NaN freeze

**Symptom:** the scrub works the first time you view the page, then on a later visit the hero
is frozen on the first frame while the text beats still animate. Maddening, because it's
intermittent.

**Cause:** if you call `video.load()` *after* the video is already buffered (which happens when
it's served from cache), it resets `video.duration` to `NaN` for a moment. The first scrub
frame then computes `currentTime = p * NaN = NaN`, and `Math.abs(NaN) > 0.005` is always
false — so the code never seeks again. The video is stuck forever.

**Fix:**
- Never call `video.load()` after wiring up the scrub.
- Guard every seek: only run the scrub math when `isFinite(video.duration) && duration > 0`.
- Self-heal: `if (!isFinite(currentTime)) currentTime = 0;`

## 2. Non-seekable hosted video (`seekable == [0,0]`)

**Symptom:** works locally, but on your deployed site every scroll position snaps the video to
frame 0 — no scrubbing at all.

**Cause:** scrubbing requires **random access** to the video. Some hosts/CDNs serve the mp4
without HTTP byte-range support, so `video.seekable` is `[0, 0]` and the browser can only sit
at time 0. (This bit us on Cloudflare Pages.)

**Fix:** fetch the whole file as a `blob` and play it from an object URL, which is always fully
seekable (and scrubs smoother):

```js
fetch(video.dataset.src)
  .then(r => r.blob())
  .then(b => { video.src = URL.createObjectURL(b); })
  .catch(() => { video.src = video.dataset.src; });   // fallback (e.g. file://)
```

This is also why **local preview needs a server** — `fetch()` of a local file over `file://`
fails, so double-clicking `index.html` gives you the stills fallback instead of the scrub. Run
`python -m http.server 8000 --directory dist` and open `http://localhost:8000`.

## 3. Encode the video for scrubbing

Seeking to arbitrary times is only fast if keyframes are dense. The stitch step encodes with a
short GOP and faststart:

```
ffmpeg ... -c:v libx264 -g 4 -sc_threshold 0 -pix_fmt yuv420p -movflags +faststart
```

`-g 4` (a keyframe every 4 frames) is what makes back-and-forth scrubbing crisp. 720p/24fps is
plenty for a hero.

## 4. HappyHorse lives on a different endpoint

`alibaba/happyhorse-1.1` is **not** in OpenRouter's `/models` list — it's a video model on the
separate `POST /api/v1/videos` endpoint (submit → poll `polling_url` → download). Image input
goes in `frame_images` and a base64 data URL works fine despite the docs suggesting hosted URLs.
