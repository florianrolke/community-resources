# Cost Controls

Default behavior:
- Dry-run paid actors first.
- Cap first paid validation at 25 results per source unless the user explicitly approves more.
- Print estimated payload, actor ID, and max results before running.
- Store raw paid outputs under `data/` or `.tmp/` and keep normalized reports separate.

Lessons from prior runs:
- 10times produced high-value event data cheaply in the medical-tourism run.
- Eventbrite can produce useful local networking results when scoped tightly.
- Meetup was noisy for broad networking scans.
- AllEvents cost more than expected and was noisy; avoid broad scans.
- LinkedIn participant scraping requires cookies/account side effects and must be approval-gated.
## May 30, 2026 Cape Coral validation
- Scoped Apify Google Search actor run used `apify/google-search-scraper` with 5 focused local-event queries and `maxPagesPerQuery: 1`.
- Actual latest run metadata: status `SUCCEEDED`, usageTotalUsd `$0.0235`, 5 SERP dataset items.
- On Windows, run repo scripts as modules when imports reference `scripts.*`: `python -m scripts.run_apify_event_actor ...`.
- PowerShell 5 `Set-Content -Encoding UTF8` can write a UTF-8 BOM; JSON payloads should be written without BOM or `read_json` should be updated to support `utf-8-sig`.

## June 20, 2026 Augusta GA validation — Free-Tier Fallback
- `zen-studio/10times-events-scraper`, `santamaria-automations/eventbrite-scraper`, and `scraperlink/google-search-results-serp-scraper` all return **403 Forbidden on Apify free-tier accounts** — they require a paid subscription regardless of available credits.
- `apify/google-search-scraper` (official Apify actor) **works on free-tier accounts** and returns full `organicResults` arrays.
- The `run_apify_event_actor.py` script passes the raw JSON response which wraps results in a page object. Use `run_apify_google_serp.py` instead — it correctly extracts `organicResults` from each page object.
- Augusta GA run: 5 queries × 10 results = 49 raw rows → 39 unique after dedupe. Cost: ~$0.02.
- Dry-run first using `--dry-run` flag to verify payload format before spending credits.
- Free-tier accounts identified by `plan.id == "FREE"` in `/v2/users/me` response. Check before running paid actors to avoid wasted 403 errors.
