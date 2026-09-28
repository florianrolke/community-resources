# UNLIMITED Leads — in Claude Code, not n8n

The lead-generation course, rebuilt in Python. Same three systems, same prompts,
no canvas.

> Jack's original build was genuinely ahead of its time. But it was recorded over
> two years ago, and the tools underneath it have moved. Two of the actors it used
> have been overtaken by better ones. A third now does natively what the video
> needed six nodes to do. And Claude Code didn't exist.
>
> This is what that course looks like today. The prompts are still Jack's, ported
> word for word. What changed is everything around them.

**Python 3.10+ · Windows-first · CSV-first · MIT**

---

## The 30-second version

```bash
python -X utf8 scripts/check_setup.py            # what's working, what's missing

# Free. No API key. Start here.
python -X utf8 scripts/03_free_scraping/build_dorks.py --niche "barber" --location "Tuscaloosa AL"

# ~2 cents
python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \
    --search "barbers in Tuscaloosa AL" --limit 5 --out-csv output/test.csv
```

That's a real lead list in two commands. No workflow to import, no credentials to
wire into six nodes, no canvas to keep open.

Those two work on a **free Apify account**. System 1 (LinkedIn search) needs a
paid plan — see the note in its walkthrough below.

---

## What actually changed since the video

Three things, and the third is the big one.

**The B2B contact actor aged out.** The course used `code_crafter/leads-finder`,
an "Apollo alternative" that queries a scraped database. On Apify today that whole
category sits at 2.1–3.9 stars, and the reviews all say the same thing: stale
records, bounced emails, people who left two jobs ago. This repo defaults to
`harvestapi/linkedin-profile-search` (4.8 stars) which searches LinkedIn live.
The old one is still included if you want to follow the video exactly.

**LinkedIn enrichment aged out too.** `dev_fusion/Linkedin-Profile-Scraper` rates
3.55. The harvestapi equivalents rate 4.4–4.8.

**Google Maps swallowed four steps.** To get emails, the video had to: scrape
Maps → loop every result → fetch each website → have an AI read the HTML →
export a CSV → upload it to AnyMailFinder → download. The actor now has flags:

```bash
--contacts        # emails + socials from each business website
--leads 3         # decision-makers: name, title, email, phone, LinkedIn
--verify-emails   # checks they're real before you send
```

The loop node, the fetch node, the AI-extraction node, and the entire
AnyMailFinder round trip are one command now.

### And then there's the part that isn't about actors

| | The n8n build | This repo |
|---|---|---|
| System 1 | 19 nodes | 1 command |
| System 2 | 13 nodes | 1 command |
| Where the logic lives | node config, in a browser tab | `.py` files, in git |
| Change the email copy | click into a Set node, edit an expression | edit `templates/email_template.md` |
| Diff two versions | you can't | `git diff` |
| It died at lead 400 of 1,000 | run the whole thing again | `--resume` |
| Enforce "subject ≤ 11 words" | ask the model nicely | `assert len(subject.split()) <= 11` |
| Onboard a teammate | screen-share the canvas | `git clone` |
| Cost to run | subscription + API | API only |

That last-but-one row is the one that matters most, and it gets its own section
below.

---

## The three systems

| Video | Command | What it uses |
|---|---|---|
| **System 1** — B2B contacts | `scripts/01_b2b_contacts/search_linkedin.py` | LinkedIn search, live |
| **System 2** — Google Maps | `scripts/02_local_businesses/scrape_google_maps.py` | Apify Maps + contact enrichment |
| **System 3** — free scraping | `scripts/03_free_scraping/build_dorks.py` | Google operators + a browser extension |
| (the research step) | `scripts/01_b2b_contacts/research_lead.py` | Claude + Tavily |
| (the writing step) | `scripts/04_outreach/write_outreach.py` | Claude, one line only |

---

## Before you scrape anything: the 3 Ps

The course's niche test, and it's the most valuable ninety seconds in the video.
A niche is worth pursuing only if it has all three:

- **Pain** — a problem that costs them real money, monthly. Not an annoyance.
- **Purchasing power** — someone who can say yes to your price without a committee.
- **Presence** — at least a thousand of them, findable. If you can't build a list, you can't build a pipeline.

Fail any one and stop. Pick another niche. Scraping the wrong list faster is not
progress, and it's the most common way people waste their first month.

---

## Setup (Windows, about 10 minutes)

```powershell
git clone https://github.com/florianrolke/unlimited-leads-claude-code.git
cd unlimited-leads-claude-code

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env      # then paste your keys in
python -X utf8 scripts\check_setup.py
```

Mac or Linux: `python3 -m venv .venv && source .venv/bin/activate`, and `cp` instead of `copy`.

### Keys

| Key | What it's for | Cost | Get it |
|---|---|---|---|
| `APIFY_API_TOKEN` | Systems 1 and 2 | free credit; System 2 works on the free plan, System 1 needs paid | [console.apify.com](https://console.apify.com) |
| `ANTHROPIC_API_KEY` | research + writing | pay-per-use, cents | [console.anthropic.com](https://console.anthropic.com) |
| `TAVILY_API_KEY` | research search | **free**, 1,000/month | [tavily.com](https://tavily.com) |

System 3 needs none of them.

`check_setup.py` makes a real call to each service, so a typo'd key fails there
rather than 200 leads into a run.

---

## Walkthrough: System 1

> **Needs a paid Apify plan.** This actor gives free accounts 10 runs total, then
> quietly returns nothing. On the free plan, do System 2 or System 3 first — both
> work fully and cost less. The script detects the cap and tells you, rather than
> letting you tune filters that were never the problem.

```bash
# 1. Test 25 and READ THEM. Right kind of person?
python -X utf8 scripts/01_b2b_contacts/search_linkedin.py \
    --titles "Owner" "Founder" --locations "Alabama" --limit 25 \
    --out-csv output/test.csv                                        # ~$0.10

# 2. The real list
python -X utf8 scripts/01_b2b_contacts/search_linkedin.py \
    --titles "Owner" "Founder" --locations "Alabama" \
    --recently-changed-jobs --limit 200 --output output/leads.json   # ~$0.80

# 3. Find five sourced facts per lead
python -X utf8 scripts/01_b2b_contacts/research_lead.py \
    --input output/leads.json --output output/researched.json        # ~$2-6

# 4. Check the copy on ONE before spending
python -X utf8 scripts/04_outreach/write_outreach.py \
    --input output/researched.json --dry-run \
    --sender-name "Armin" \
    --pain "leads going cold because nobody follows up past email one" \
    --similar-company "a 12-truck HVAC company in Mobile" \
    --metric "31 extra booked jobs in 60 days"

# 5. Write them all
python -X utf8 scripts/04_outreach/write_outreach.py \
    --input output/researched.json --out-csv output/outreach.csv \
    --sender-name "Armin" --pain "..." --similar-company "..." --metric "..."   # ~$1
```

**`--recently-changed-jobs` is the highest-leverage flag in the repo.** Someone
three weeks into a new role is rebuilding their stack and has budget to prove.
It also hands the research step a trigger event for free — which is the entire
thing the video's AI agent was built to go hunting for.

## Walkthrough: System 2

```bash
python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \
    --search "roofing contractors in Mobile AL" --limit 100 \
    --contacts --leads 2 --departments "C-Suite" --verify-emails \
    --out-csv output/roofers.csv
```

One command: 100 businesses, their emails, two named decision-makers each with
direct contact details, every address verified.

## Walkthrough: System 3 (free)

```bash
python -X utf8 scripts/03_free_scraping/build_dorks.py \
    --niche "barber" --location "Tuscaloosa AL" --output output/dorks.md
```

Open `output/dorks.md`, click a search, scrape the page with the free
[Instant Data Scraper](https://chrome.google.com/webstore) extension, then:

```bash
python -X utf8 scripts/03_free_scraping/parse_scraper_export.py \
    --input ~/Downloads/instant-data-scraper.csv --out-csv output/free_leads.csv
```

Total: nothing.

---

## Using it with Claude Code

You don't have to type any of the above.

Open Claude Code in this folder and say what you want:

> find me 50 barbers in Tuscaloosa AL and write me LinkedIn connection requests

It reads `.claude/skills/`, picks the right systems, runs the setup check first,
and gives you a CSV. The skills carry the same guidance a good operator would —
test 25 first, start with the free system, don't invent a fact.

---

## What the AI is allowed to write

This is the course's best idea, and the repo enforces it rather than suggesting it.

The email is fixed. You wrote it, you tested it, it works:

```
Hi {first_name},

{opener}                   <-- the ONLY line the AI writes

Most companies scaling this fast hit the same bottleneck: {pain_point}.

We helped {similar_company} solve this and saw {metric} in 60 days.

Worth a 15-min chat to see if we can do the same for {company}?

{sender_name}
```

Everything except `{opener}` is your copy, byte-identical in every email. That's
what makes a sequence testable: when reply rates move, you know why.

The prompts *ask* the model for a subject under 11 words, an opener under 15 that
starts with "I noticed", no congratulations, no dates. Prompts ask. `write_outreach.py`
checks — and on failure feeds the exact reason back for one retry, then holds the
lead out with a note rather than shipping it:

```
subject must start with "Quick question about {Company}'s", ≤ 11 words
body must start with "I noticed {Company} recently", ≤ 15 words
no "Congratulations" / "Congrats" / "amazing" / "great work"
no years, no month names, no quoted event names
LinkedIn request ≤ 200 chars, no "building my network"
```

You will never send a 14-word subject line by accident. On a canvas, you can.

---

## Cost

| Step | Per unit | 100 leads | 1,000 |
|---|---|---|---|
| System 1 — LinkedIn, short | ~$0.004 | $0.40 | $4 |
| System 1 — with email lookup | ~$0.014 | $1.40 | $14 |
| System 2 — Maps, plain | ~$0.004–0.02 | $0.40–2 | $4–20 |
| System 2 — `--contacts` | add-on | +$1–3 | +$10–30 |
| System 2 — `--leads` + verify | add-on | +$2–5 | +$20–50 |
| Research (Claude + Tavily) | ~$0.01–0.03 | $1–3 | $10–30 |
| Outreach writing | ~$0.005 | $0.50 | $5 |
| **System 3** | — | **free** | **free** |
| **Typical end-to-end** | | **~$3–5** | **~$30–50** |

Apify pricing changes — check the actor page before a big run. Every script prints
its estimate before it spends anything. Full breakdown in [docs/COSTS.md](docs/COSTS.md).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `UnicodeEncodeError` | Add `-X utf8`. Windows defaults to cp1252. |
| `APIFY_API_TOKEN is not set` | The error prints the exact file it looked in. |
| Wrong keys being used | `check_setup.py` prints which `.env` it loaded — see [the note below](#the-env-trap). |
| No results | Filters too narrow. Drop one. |
| 403 on some business sites | ~15% block scrapers. Expected. |
| Google Sheets re-asks every run | Delete `token.json`. |
| Run died partway | `--resume`. |

### The .env trap

Most Python code loads `.env` by walking **up** the directory tree until it finds
one. Clone this repo into a folder that has a `.env` above it and every script
silently uses those keys — works on your machine, fails on everyone else's, with
no error either way.

This repo only ever reads its own `.env`, and `check_setup.py` prints the path so
you can confirm. `scripts/lib/env.py` explains the whole thing.

---

## Where to go next

- `reference/n8n-original/` — the original workflows, if you want to compare
- [docs/03-n8n-blueprint-mapping.md](docs/03-n8n-blueprint-mapping.md) — every node, and what replaced it
- [docs/GOTCHAS.md](docs/GOTCHAS.md) — things learned the hard way
- The `extending-this-repo` skill — adding your own source

---

## Credit

The three systems, the 3 Ps framing, the determinism idea, and the four AI prompts
in `prompts/` are **Jack Roberts'**, from *UNLIMITED leads for FREE (FULL COURSE)*
in the AI Automations by Jack community. Included with his permission.

This repo is the Python port, maintained by [Florian Rolke](https://github.com/florianrolke).

## License
MIT — see [LICENSE](LICENSE).
