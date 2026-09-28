# Working in this repo

Instructions for Claude Code. If you're a human, `README.md` is the one you want.

## What this is
The Python replacement for a lead-generation course that was taught in n8n. Three ways to find leads, then research and outreach on top. The user is often a non-developer on Windows following along with a video.

## Before anything else

Run the setup check. It catches missing keys, missing packages, and the wrong `.env` — all of which fail confusingly later:

```bash
python -X utf8 scripts/check_setup.py
```

## Rules

**Always `python -X utf8`.** Windows defaults to cp1252 and a single accented business name crashes the run.

**CSV is the deliverable.** Google Sheets is opt-in behind `--sheet-url` and needs OAuth. Never route someone through Google Cloud setup to get their first leads out.

**Test 25 before scraping 1,000.** Every scraping skill says this. Read the test output and confirm it's the right kind of business or person. Scraping the wrong list faster helps nobody.

**Say what it costs before spending.** These scripts spend real money per run. Print the estimate, and get a yes before a large run.

**Never invent a lead detail.** No guessed email addresses, no invented trigger events. If research found nothing, the lead is flagged (`needs_research: true`) and skipped by the outreach step. That's the designed behavior — don't work around it.

**The AI writes one line.** In `write_outreach.py`, the model fills `{opener}` and nothing else. The rest of the email is the user's copy, byte-identical every time. If asked to "let the AI write the whole email", explain why that breaks testability, then follow the user's decision.

**Free first.** System 3 costs nothing. For anyone new, or anyone unsure, start there — it proves the pipeline works before a card is involved.

## Layout

```
scripts/
  check_setup.py          run this first
  lib/                    env, output, claude, checkpoint — shared plumbing
  01_b2b_contacts/        System 1: LinkedIn search -> research -> outreach
  02_local_businesses/    System 2: Google Maps
  03_free_scraping/       System 3: Google dorks, no keys
  04_outreach/            writing and email verification
  common/                 lead classification, Sheets I/O
prompts/                  the four AI prompts, ported from the n8n nodes
templates/                the email template — the fixed part
.claude/skills/           what you read to know how to run each system
reference/n8n-original/   the original workflows, for comparison
```

## Where things live

- `.env` is read **only** from the repo root, via `scripts/lib/env.py`. Never call bare `load_dotenv()` — it walks up the directory tree and will silently use a parent folder's keys. `scripts/lib/env.py` documents why.
- Prompts are markdown in `prompts/`, not string literals. Edit copy there.
- The email template is `templates/email_template.md`. Edit it, don't edit the script.
- Everything the user generates goes in `output/`, which is gitignored.

## Typical flows

**"Find me local businesses"** → `finding-local-businesses` skill
**"Find me people with job title X"** → `finding-b2b-contacts` skill
**"I have no budget"** → `free-lead-scraping` skill
**"Write me emails for these"** → `researching-leads`, then `writing-cold-outreach`

Full pipeline:
```bash
python -X utf8 scripts/01_b2b_contacts/search_linkedin.py --titles "Owner" --locations "Alabama" --limit 25 --output output/leads.json
python -X utf8 scripts/01_b2b_contacts/research_lead.py --input output/leads.json --output output/researched.json
python -X utf8 scripts/04_outreach/write_outreach.py --input output/researched.json --out-csv output/outreach.csv --sender-name "..." --pain "..." --similar-company "..." --metric "..."
```

## When something breaks

`UnicodeEncodeError` → add `-X utf8`.
`APIFY_API_TOKEN is not set` → the error names the exact file it looked in.
Empty results → filters too narrow; drop one and retry.
403 on ~15% of business websites → expected, they block scrapers.
Sheets asks to authorize every run → delete `token.json`.

## Adding to it
See the `extending-this-repo` skill. Short version: match the existing script shape, always emit CSV, always checkpoint loops, and check the Apify store for a better-rated actor before wiring one in — two of this repo's actors were replaced that way.
