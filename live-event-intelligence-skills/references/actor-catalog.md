# Actor Catalog

Primary low-cost sources:
- `scraperlink/google-search-results-serp-scraper`: Google SERP lookup for profiles, Facebook, websites, and event pages.
- `apify/google-search-scraper`: Google search results for focused event/contact queries. **Also the free-tier fallback — see Free-Tier Fallback section below.**
- `zen-studio/10times-events-scraper`: conferences, trade shows, expos, exhibitions. Strong signal in a medical-tourism run.
- `santamaria-automations/eventbrite-scraper`: tightly scoped Eventbrite events.
- `powerai/eventbrite-events-scraper`: alternate Eventbrite search URL actor.

Secondary sources:
- `easyapi/meetup-events-scraper`: use only with specific professional groups or strong niche queries.
- `easyapi/ticketmaster-events-scraper`: ticketed expos, conventions, and venue-based events.
- `apify/facebook-events-scraper`: Facebook event search when local/community pages matter.
- `crawlerbros/facebook-events-scraper`: known Facebook event URLs or page event listings.

Avoid by default:
- `techforce.global/all-events-scraper`: Test cost $4 for 10 noisy results due to actor-start/memory billing.

Approval required:
- LinkedIn participant scraping actors.
- Authenticated LinkedIn automation.
- Full Instagram follower scrapes.
- Any paid actor run above the configured cap.

## Free-Tier Fallback (No Paid Subscription Required)

**When to use:** The actors above (`zen-studio`, `santamaria-automations`, `scraperlink`, `easyapi`) require an **Apify paid subscription** — they return 403 on free-tier accounts even with available credits. If the account is on a free plan, use this fallback instead.

**Script:** `scripts/run_apify_google_serp.py`

This script uses `apify/google-search-scraper` (official Apify actor, available on free tier) to run multiple targeted Google searches and extract `organicResults`. It produces a CSV in the same format as `discover_events_serp.py`, compatible with `normalize_events.py` → `dedupe_events.py` → `rank_opportunities.py`.

**Usage:**
```powershell
python -m scripts.run_apify_google_serp `
  --queries "BNI chapter Augusta GA 2026 networking
Augusta Metro Chamber events 2026
business networking events Augusta Georgia 2026" `
  --output data/google-serp-results.csv `
  --results-per-page 10
```

**Cost:** ~$0.02 per 5-query run (Augusta GA run: $0.023, 49 results). Token key: `APIFY_API_TOKEN` — the script rotates through `_7`, `_6`, `_5`, `_4`, `_3`, `_2`, base in that order.

**Quality:** Returns the same organic Google results a browser would see. Validated in Augusta GA run — 39 unique events after dedupe, including BNI chapter details, chamber event registrations, and local networking events not surfaced by Tavily.