# Pop-up art

Photorealistic cutout art around your website's pop-up, so the pop-up shows the outcome your visitor came for. A jaguar
and a vine canopy around a rainforest retreat pop-up, a hillside coffee farm around a land pop-up, a luxury train and an
Andean dinner around a travel pop-up.

It never slows the page: one loader line fetches the art after the page has finished loading, pictures are fetched only
when the browser is idle or the pop-up opens, and pieces hidden on small screens are never downloaded. Your pop-up's
wording and opening rules stay exactly as they are.

## Try it in two minutes

```text
pip install opencv-python numpy scipy playwright
python scripts/build_art.py example/art.json
open example/index.html#preview-popup
```

The demo uses three pictures that are already in `example/source-art`, so it costs nothing.

## Use it on your site

1. Write `prompts.json` (what each picture shows) and generate the pictures with the image model you like:
   `python scripts/generate.py prompts.json --provider openai` (or `gemini`, `replicate`, `file` for your own pictures;
   any MCP image tool such as Floot works too). Add `--dry-run` first: it shows every request and costs nothing.
2. Write `art.json`: your pop-up's selector, where each piece sits, how far it moves with the pointer.
3. `python scripts/build_art.py art.json` cuts out every picture and writes `popup-art.js` and `loader.js`.
4. `python scripts/check.py art.json --page https://your.site/post/ --serve https://your.site/=YOUR_BUILD_FOLDER --trigger exit`
   takes screenshots at five window sizes and checks speed and the pop-up trigger.
5. Append `loader.js` to a script every page already loads. Deploy.

`SKILL.md` has the full method for Claude Code or Codex: how to pick the pieces, prompt rules that give clean cutouts,
the cutout options, placement patterns, small-screen steps and the rollout checklist.

## Image models

| Provider | Key | Approximate cost |
|---|---|---|
| OpenAI `gpt-image-1` | `OPENAI_API_KEY` | a few cents to about 25 cents per picture, by size and quality |
| Google `gemini-2.5-flash-image` | `GEMINI_API_KEY` | a few cents per picture |
| Replicate (Flux and others) | `REPLICATE_API_TOKEN` | a few cents per picture, by model |
| Floot or another MCP image tool | the tool's own login | your plan's credits |
| Your own pictures | none | free |

Prices change; check the provider's page. No key ships with this folder.
