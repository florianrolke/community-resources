---
name: popup-art
description: Put photorealistic cutout art around a website's existing pop-up (exit pop-up, WhatsApp or lead-form pop-up) without slowing the page down. Generate the pictures on pure black with any image model (OpenAI, Google Gemini, Replicate, Floot or any other MCP image tool, or your own files), cut them out, place them around the card in layers that move with the pointer, and load everything only after the page has finished loading. Use for "add art around the pop-up", "make the pop-up look like the jaguar one", "pop-up art for another blog", "roll the pop-up art out across all pages", or "swap the image model for the pop-up art".
---

# Pop-up art

The visitor's pop-up opens over a lighter backdrop. Photorealistic cutouts of the outcome they came for stand around the
card (a piece above it, one on each side, a small one in front of a corner, optionally branches hanging in from the window
corners), fade in one after another, and shift a few pixels with the pointer, nearer pieces more. The card gets a thin gold
frame and the main button a light sweep on hover. Small screens drop pieces in steps. Nothing about the pop-up itself
changes: its wording, its buttons, when and how often it opens.

## Rules that are not optional

1. **Page speed comes first.** No art file is part of the page load. One loader line fetches `popup-art.js` after the
   page's `load` event; that script fetches the pictures when the browser is idle or the pop-up opens, skips pieces hidden
   at the current screen size, and serves a 1x or 2x WebP. Never add the art as `<img src>` in the page, as a stylesheet in
   `<head>`, or as an extra `<script src>` in the page. `check.py` must report `"passed": true` for speed.
2. **Leave the pop-up's behavior alone.** Decorate the pop-up that is actually active on each page. If a page carries two
   pop-ups, find out which one its scripts open before choosing.
3. **The front layer never covers text, form fields, the main button or the close button.** Side pieces sit behind the
   card, so they may overlap its edge.
4. **Show the real place.** The art must match where the business really is (landscape, plants, animals, clothing, light).
   Use the site's own photos as references: search their alt texts ("hill", "valley", "river", the town name) to find them.
   A flat, terraced valley is not a steep jungle valley; the owner will notice.
5. **Paid generation needs a yes.** Run `generate.py --dry-run` first, give the number of pictures and the cost, and wait
   for approval unless the person has already said the credits may be used.
6. **Never overwrite or delete.** `generate.py` saves a new round under a new name; keep earlier rounds and restore points.

## Workflow

### 1. Read the site

- Find the pop-up element and its card. Decide its kind:

| Kind | The pop-up is | What the engine does |
|---|---|---|
| `dialog` | a `<dialog>` with a card element inside | art before the card and at the end of the dialog |
| `overlay` | a full-screen `div` that centers a card and opens with a class (`is-open`) | wraps the card in a stage that carries the art |
| `wrap` | a `<dialog>` whose content sits directly inside it | moves the content into a new card element, art around it |

- Find which script every page already loads (a shared `site.js`, the pop-up's own script). The loader line goes at the
  end of that file. Pages with no shared script get the line inline before `</body>`.
- On a large site, count pages per pop-up type with a small scan (which pop-up id, which shared script). Every type needs
  its own check.
- Measure the card (width and height) at desktop size. The art is placed against those edges.
- Ask the reviewer for their real browser window size, or open a page that prints `innerWidth x innerHeight`. A
  1536 x 791 window (a 4K laptop at 250% scaling) hides pieces that a 1600 x 900 screenshot shows.

### 2. Decide the pieces

Ask why people land on the page and what they want. The art shows that outcome, not the product.

| Slot | Role | Typical depth `--d` |
|---|---|---|
| Top | landscape or canopy behind the card's top edge, translucent | 0 (still) to 6 |
| Left, right | the main scenes, half behind the card | 10 to 16 |
| Front corner | a small object that overlaps a card corner | 22 to 28 |
| Window corners (optional, wide screens) | branches or flowers hanging in, `position:fixed` | 4 |
| Below the card (optional) | a view or ground strip tucked behind the bottom edge | 6 |

Fewer, larger pieces that touch each other read as one scene. Spread pieces over the corners; one corner must not hold
everything, and a piece must never sit on another one in a way that makes no sense (a waterfall on a roof).

### 3. Generate the pictures (any image model)

Write `prompts.json` (see `example/prompts.json`), then pick the model:

| Provider | Command | Key | Notes |
|---|---|---|---|
| OpenAI | `python scripts/generate.py prompts.json --provider openai` | `OPENAI_API_KEY` | default `gpt-image-1`; reference photos go to the edits endpoint |
| Google Gemini | `--provider gemini` | `GEMINI_API_KEY` | default `gemini-2.5-flash-image`; up to several reference photos |
| Replicate | `--provider replicate` | `REPLICATE_API_TOKEN` | default `black-forest-labs/flux-1.1-pro`, with a reference `flux-kontext-pro`; any model via `--model owner/name` |
| Any MCP or chat image tool (Floot, others) | call the tool, save each picture as `source-art/<name>.png` | the tool's own login | Floot: `generate_image` with up to 4 pictures per call; upload references with `upload_asset` first |
| Your own pictures | `--provider file` | none | copies the file named in `"file"` |

Add `--dry-run` to see every request without sending it. To add a provider, write one function that takes
`(item, model, dry)` and returns PNG bytes, and add it to the dictionary in `main()`.

Prompt rules that work:
- People and objects: "isolated cutout on a pure black background (#000000), full body from head to shoes, completely
  inside the frame with empty black margin on every side". Without it people come back cut at the knees and look like
  they float.
- Landscapes: "pure black at the left, right and bottom edges" (or a soft irregular opening framed in black).
- Skies: "the sky must be completely pure black everywhere above the ridge line, no clouds, no haze; only a soft golden
  glow hugs the ridge".
- Hanging branches: "enters from the top-left corner of the image (cut off by the top and left edges) ... completely pure
  black everywhere, also between the leaves: no glow, no haze, no bokeh".
- Always: "photorealistic editorial photography, warm golden light, no text, no logos". For technology and robots:
  "bright, optimistic, friendly, nothing dark or threatening".
- Pass one or two of the site's own photos as references so people, clothing and places match.

### 4. Cut out

`build_art.py` cuts every piece with `scripts/cutout.py`. Tune per piece in `art.json` under `"cutout"`:

| Option | Use it when |
|---|---|
| `lo`, `hi` | brightness range of the soft edge (default 6 and 30 for a clean black background) |
| `solid` | pixels brighter than this are opaque; lower it (10) for people in dark clothing |
| `hole` | dark gaps inside a figure up to this many pixels are filled; larger gaps stay see-through |
| `free` | faint light far from the subject must stay (stars, light rays, steam, wings) |
| `mass` | a mountain must be solid from its ridge line down |
| `sky` | a glow above a ridge should only lighten the page beneath it |
| `grabcut` | the background came back dark grey instead of black |
| `fade` | the generator cut an edge hard: share of the picture that fades out (top, right, bottom, left) |
| `crop` | use only part of the picture, in source pixels |

Look at every `-cutout.png` on a light grey background as well as on the dark backdrop: fringes and haze only show on
light ground.

### 5. Place the pieces

In `art.json` each piece has `style` (position against the card), `depth`, `from` (direction it slides in from), `delay`
and `shadow`. Patterns:
- `right:calc(100% - 70px)` puts a piece on the left with 70 px tucked behind the card; `left:calc(100% - 30px)` does the
  same on the right.
- Side widths follow the free space: `width:clamp(400px,calc(50vw - 270px),600px)`.
- Window-corner pieces: `position:fixed;left:-14px;top:-14px;width:clamp(220px,21vw,360px)`. They only work while no
  ancestor of the art has a `transform` or `filter`.
- Large translucent backdrops through which the page shows (a mountain, a ruin) stay still (`depth` 0). A moving
  translucent backdrop makes the page itself look like it slides.
- Add `media` rules that drop pieces in steps: below 1180 px wide the right piece, below 900 px the left piece and the
  window corners, phones keep the top piece and the small corner piece, windows under 620 px high keep only the top.
  Also handle short wide windows (1440 px wide or more, under 800 px high): shrink the bottom pieces rather than hide
  scenes the reviewer approved.
- For an `overlay` pop-up whose card is shorter than the card you designed around, set `stage_width` and `min_height` in
  `popup` to the approved card's size; the content centers inside and the art keeps its approved positions.

### 6. Build and check

```text
python scripts/build_art.py art.json
python scripts/check.py art.json --page https://site.test/post/ --serve https://site.test/=PUBLIC_FOLDER --trigger exit
```

`check.py` saves screenshots at 1600x900, 1536x791, 1280x720, 820x1000 and 390x800 and prints per size how many pieces
are shown and loaded, broken pictures and script errors. Then the speed check (art requests before the load event: must be
none; it needs an http(s) address, which `--serve` provides for local files) and, with `--trigger exit`, whether the site's
own rules open the pop-up with its art. Some pop-ups wait 8 seconds and need the reader to scroll first: raise `--wait`
and `--scroll`. Look at every screenshot yourself. Show the reviewer one page per pop-up type, at their window size.

### 7. Roll out

- Append `loader.js` to the shared script (or inline it in pages without one). Set `public_url` in `art.json` to the
  address `popup-art.js` will have on the live site, including any subfolder.
- A site with several pop-up types: build one `art.json` per type, or one script that picks the active pop-up.
- A pop-up you create from scratch (the page had none): keep its markup, wording and opening rules inside `popup-art.js`
  too, so a later wording change is one file and one deploy.
- When several people deploy the same site, build the release on the version that is live now, and check every live file
  after the deploy.
- Going back: remove the loader line. The art files can stay.

## Files

```text
SKILL.md                  this workflow
README.md                 short human introduction
scripts/generate.py       pictures from OpenAI, Gemini, Replicate or your own files (MCP image tools: see step 3)
scripts/cutout.py         picture on black -> transparent WebP in two sizes
scripts/build_art.py      art.json -> popup-art.js (engine, styles, pictures list) and loader.js
scripts/check.py          screenshots at five sizes, speed check, trigger check
example/                  a demo page with a plain <dialog> pop-up, art.json, prompts.json and three source pictures
```

Requirements: Python 3.10+, `pip install opencv-python numpy scipy playwright`, then `playwright install chromium`
(or pass `--channel chrome` to `check.py` to use an installed Chrome).
