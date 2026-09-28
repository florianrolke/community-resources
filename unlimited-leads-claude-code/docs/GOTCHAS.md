# Things learned the hard way

## Windows

**`UnicodeEncodeError: 'charmap' codec can't encode character`**
Windows defaults to cp1252. One accented business name and the run dies. Always
`python -X utf8 script.py`. Every script also calls `fix_encoding()` on import as
a backstop, but the flag is the reliable fix.

**Excel shows `CafÃ©` instead of `Café`**
The CSV needs a UTF-8 BOM for Excel to detect the encoding. `scripts/lib/output.py`
writes `utf-8-sig` for exactly this reason. If you write CSVs yourself, do the same.

**Blank row between every row in Excel**
`open(path, "w")` on Windows turns `\n` into `\r\n`, and the CSV writer adds its
own. `newline=""` fixes it — again handled in `scripts/lib/output.py`.

**Paths with spaces**
Quote them: `--input "C:\My Leads\file.csv"`.

## The .env trap

This one is worth understanding because it fails silently.

`load_dotenv()` with no arguments walks **up** the directory tree until it finds a
`.env`. Clone this repo into a folder that already has one above it and every
script quietly uses those keys. It works on your machine and fails on everyone
else's, and neither run produces an error.

This repo only reads `<repo root>/.env`, via `scripts/lib/env.py`, and
`check_setup.py` prints the path it used. Never call bare `load_dotenv()` in a
script you add here.

## Scraping

**~15% of business websites block scrapers.** 403s are normal, not a bug. The
pipeline records what it can and moves on.

**Google Maps: put the city in the search string.** `"barbers in Tuscaloosa AL"`
beats `"barbers"` with `--location`. And one location per run — two cities in one
search returns mush.

**Fewer results than `--limit`** means the source genuinely has that many. Broaden
the term or the area.

**LinkedIn location matching is fuzzy.** "UK" resolves to Ukraine. Use "United
Kingdom". Test the term in LinkedIn's own search box first.

**Test 25 before scraping 1,000.** If fewer than 20 are right, the filters are
wrong. This is the single most expensive lesson in lead gen.

## AI steps

**A lead with no facts gets flagged, not an invented opener.** `needs_research: true`
means the research found nothing. `write_outreach.py` skips those on purpose.
Don't work around it — an opener referencing something that didn't happen is worse
than no email at all.

**Validators exist because prompts are requests.** The prompt asks for 11 words or
fewer; the code checks. When a lead fails twice it's held back with a reason in
`outreach_status`. If lots of leads fail, the research was thin — don't loosen the
validators.

**Cap your agent loops.** `--max-tool-calls` defaults to 8 per lead. Without a cap,
one weird lead can drain a search quota.

**Checkpoint anything long.** Runs get interrupted. `--resume` picks up where it
stopped instead of re-paying.

## Apify plan limits

**System 1 returns 0 profiles and says the filters are wrong.** They probably
aren't. `harvestapi/linkedin-profile-search` caps free accounts at 10 runs, then
reports SUCCEEDED with an empty dataset and `statusMessage: free user run limit
reached`. The script checks for this and tells you — but if you write your own
actor wrapper, check `run["statusMessage"]` when the dataset is empty, or you'll
debug the wrong thing.

**The video's actor wants full-account permissions.** `code_crafter/leads-finder`
errors on first run with an approval URL. Open it once, approve, done.

**System 2 has no such cap** and was verified end to end on a free account. So
was System 3, which needs no Apify account at all.

## API keys

**Rotate on exhaustion.** Add `TAVILY_API_KEY_2`, `_3` and the research step moves
on automatically when one hits its monthly cap.

**Anthropic "credit balance too low"** means the key is valid but unfunded. Add
billing at console.anthropic.com.

**Run `check_setup.py` after any key change.** It makes a real call, so a typo
fails there rather than 200 leads in.

## Google Sheets

**It's optional.** CSV is the default and needs nothing. Only set up OAuth if you
specifically want a live shared sheet.

**Browser opens every run** → delete `token.json` and authorize once more.

**403 on an existing sheet** → the account you authorized can't edit that sheet.

**Big lists** → Sheets rate-limits writes. Past a few thousand rows, use CSV.

## Sending

**Verify before you send.** Bounces damage domain reputation and it's slow to
rebuild. Keep bounce rate under 2%.

**Never send to a pattern-guessed address.** `first@company.com` is how a domain
gets burned.

**Warm up a new domain** over two to three weeks before volume.

**Catch-all domains accept everything**, so verification tells you nothing there.
Send, but keep them in a separate batch so a bad group doesn't poison the rest.
