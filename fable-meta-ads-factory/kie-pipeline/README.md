# kie-pipeline — Meta ad statics with baked-in headline text

A small, self-contained generator that turns text prompts into **Meta ad static
images with the headline already burned into the picture**, using the
[Kie AI](https://kie.ai) Jobs API (model `seedream/5-pro-text-to-image`).

Each ad is a pure **text-to-image** generation: no reference photo, just a prompt
describing the scene plus the exact uppercase words you want rendered inside a
headline bar. The model paints both the photorealistic scene and the typography.

This works well for "scene + headline bar" ad statics because you can dictate the
precise words to render — and, importantly, retry a single misspelled image
without re-billing the rest of the set.

---

## What's in here

| File | Purpose |
|------|---------|
| `generate_ads.py` | The generator. Reads prompts, calls Kie, downloads PNGs, writes sidecars. |
| `prompts.example.json` | Two example ad definitions. Copy to `prompts.json` and edit. |
| `.env.example` | Template for the one secret you need (`KIE_AI_API_KEY`). |
| `README.md` | This file. |

Outputs (PNGs + `.task.json` sidecars) land in `./output/` by default.

---

## Setup

1. **Install dependencies** (Python 3.9+):

   ```bash
   pip install requests python-dotenv
   ```

2. **Get a Kie API key.** Sign up at [kie.ai](https://kie.ai), create an API key,
   and top up credits (image generation is a paid call — see cost below).

3. **Create your `.env`.** Copy the template and paste your key:

   ```bash
   cp .env.example .env
   # then edit .env so it reads:
   # KIE_AI_API_KEY=sk-...your real key...
   ```

   The key is read via `python-dotenv` and is **never printed** — the script only
   ever shows a redacted preview like `sk-a...b3f9`.

4. **Create your prompts.** Copy the example and edit it:

   ```bash
   cp prompts.example.json prompts.json
   ```

---

## Run it

**Always dry-run first.** Dry run is the default and makes **no paid call** — it
prints the exact payload that would be sent for each selected ad and an estimated
credit cost:

```bash
python generate_ads.py
```

When the payloads look right, generate for real with `--live`:

```bash
python generate_ads.py --live
```

Common options:

```bash
python generate_ads.py --live --out ./output          # where PNGs are written
python generate_ads.py --prompts ./my-prompts.json    # a different prompt file
python generate_ads.py --aspect-ratio 4:5             # 3:4 (default) or 4:5 etc.
python generate_ads.py --quality basic                # basic == 1K
python generate_ads.py --output-format png
```

---

## The credit cost

At the default settings (3:4 portrait, `basic`/1K, PNG) each image costs
**roughly ~7 credits**. A set of ten ads is therefore ~70 credits. Because every
`--live` image is billed, the script is **dry-run by default** so you never
accidentally spend credits.

---

## The `--only` retry pattern (don't re-bill the whole set)

`--only <substr>` runs **only** the ads whose `stem` contains the given
substring. This is the single most useful flag in day-to-day use.

Text-to-image models occasionally misspell a word. The classic pitfall: the word
**LEAK** rendering as **LEEK** (the vegetable). When that happens you want to
regenerate just that one image, not pay again for the nine that came out fine:

```bash
# The "cheap part" ad rendered LEEK. Strengthen its spelling hint in prompts.json,
# then regenerate ONLY that ad:
python generate_ads.py --live --only cheap-part
```

Because the filter matches on `stem`, keep your stems descriptive and unique
(the script refuses duplicate stems, since two ads with the same stem would
overwrite each other's output).

**Tip for reliable text:** in the prompt, spell the tricky word out
letter-by-letter and say what it is NOT — e.g.
`the word is LEAK spelled L-E-A-K (a water leak, NOT 'LEEK' the vegetable)`.
Exact-spelling instructions plus a one-image `--only` retry is the whole trick to
getting clean baked-in headlines.

---

## `prompts.json` schema

A JSON **list** of ad objects. Each object needs exactly three fields:

```json
[
  {
    "label": "AD 1 - referral loop / ceiling water stain",
    "stem": "example_referral_ceiling-stain",
    "prompt": "Photorealistic vertical Meta advertisement photo. Scene: ... At the top: a solid dark navy rounded headline bar ... reading exactly 'GET PAID FOR WHAT YOU ALREADY SEE' ... No other text, no logos, no faces, no watermarks."
  }
]
```

| Field | Meaning |
|-------|---------|
| `label` | Human-readable name shown in logs. Anything you like. |
| `stem` | Output filename base — becomes `<stem>.png` and `<stem>.task.json`. Must be unique; also what `--only` matches against. Use lowercase-with-hyphens. |
| `prompt` | The full text-to-image prompt: scene description **plus** the exact uppercase headline in quotes, plus spelling and "no logos/faces/watermarks" guards. |

**Prompt-writing notes** (from real use):

- State the headline **verbatim in quotes** and add `All text must be spelled
  exactly as specified.`
- Describe a house-style headline bar consistently (e.g. "a solid dark navy
  rounded headline bar spanning the full width, bold white condensed uppercase").
- Add negative guards: `No other text, no logos, no faces, no watermarks.` and,
  for vehicles, `No readable license plates.`
- Spell out any word the model tends to mangle (see the LEAK/LEEK note above).

---

## Output: the `.task.json` sidecar

For every generated PNG the script writes a `<stem>.task.json` next to it,
recording exactly what happened — `task_id`, `model`, the full `prompt`,
`credits_consumed`, `duration_seconds`, and the `result_url`. Keep these; they're
your audit trail of what was generated, at what cost, from what prompt.

---

## How it works (API pattern)

```
Base:  https://api.kie.ai/api/v1/jobs
POST /createTask   -> returns data.taskId
GET  /recordInfo?taskId=...   -> poll state until success | fail
```

On `success` the script extracts the image URL from `resultJson`, downloads the
PNG, and writes the sidecar. On `fail` it prints the fail code/message and moves
on. Generations run **sequentially** (one paid call at a time), which keeps the
run predictable and easy to stop.
