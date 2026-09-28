# What this costs

Every script prints an estimate before it spends anything. These are the numbers
behind those estimates.

Apify actor pricing changes. Check the actor page before a large run.

## What works on a free Apify account

Worth knowing before you pick a system — this is per-actor, not per-plan-price.

| System | Free Apify plan | Notes |
|---|---|---|
| **System 3** — free scraping | ✅ no Apify account needed at all | Start here |
| **System 2** — Google Maps | ✅ works | Verified on a free account |
| **System 1** — LinkedIn search | ❌ 10 runs, then returns nothing | Needs Apify paid (from $39/mo) |
| **System 1** — the video's actor | ⚠️ works, but Apify makes you approve full-account permissions in the browser once | One-time, then fine |

If you're evaluating this repo, do System 2 and 3 first. They cover local
businesses and free scraping completely, and together that's most people's use
case anyway.

## System 1 — B2B contacts

`harvestapi/linkedin-profile-search`, billed per search page plus per profile.

| Mode | What you get | Per profile | 100 | 1,000 |
|---|---|---|---|---|
| `short` | name, title, company, LinkedIn URL | ~$0.004 | $0.40 | $4 |
| `full` | + experience, education, about | ~$0.008 | $0.80 | $8 |
| `email` | + email address | ~$0.014 | $1.40 | $14 |

The video's actor (`code_crafter/leads-finder`) is cheaper at roughly $0.0015 per
lead, and still included. It queries a scraped database rather than LinkedIn.

## System 2 — Google Maps

`compass/google-maps-extractor`. The base scrape is cheap; each add-on bills
separately, which is why they're off by default.

| What | Per place | 100 | 1,000 |
|---|---|---|---|
| Base scrape | ~$0.004–0.02 | $0.40–2 | $4–20 |
| `--contacts` | add-on | +$1–3 | +$10–30 |
| `--leads N` | add-on, per lead found | +$2–5 | +$20–50 |
| `--verify-emails` | add-on, per email | +$0.50–1 | +$5–10 |

## AI steps

Claude Opus 5: $5 per million input tokens, $25 per million output.

| Step | Per lead | 100 | 1,000 |
|---|---|---|---|
| Research (several searches + page reads) | ~$0.01–0.03 | $1–3 | $10–30 |
| Website summary + 5 facts | ~$0.002 | $0.20 | $2 |
| Outreach writing | ~$0.005 | $0.50 | $5 |

Every AI script takes `--model`. `claude-sonnet-5` is roughly 40% cheaper and
fine for the extraction steps; keep Opus for the copywriting, where the
difference shows.

## Free

| | |
|---|---|
| Tavily search | 1,000/month, no card |
| System 3 end to end | $0 |
| Instant Data Scraper | $0 |
| Google Sheets output | $0 |

## Realistic totals

| Scenario | Cost |
|---|---|
| First test — 5 Maps businesses | **~$0.02** |
| 25-lead System 1 test with research | **~$0.50** |
| 100 local businesses with emails | **~$2–4** |
| 200 B2B leads, researched, written | **~$5–8** |
| 1,000 leads end to end | **~$30–50** |
| Any amount via System 3 | **$0** |

## Keeping it down

1. **Always test 25 first.** The most expensive run is the one aimed at the wrong list.
2. **Leave the add-ons off** until you know the base results are right.
3. **`--mode short`** unless you actually need emails now.
4. **`--limit` on every command.** It's a spending cap.
5. **`--resume` after a crash** so you don't re-pay for work already done.
6. **`--dry-run` on outreach** — one lead, printed, before you write 500.
