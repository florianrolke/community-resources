# Optional research setup

The builder does not need API keys or network access. For paid research, copy `.env.example` to `.env` in this folder and enter your own provider keys. This kit loads only its local `.env`; it does not look in a parent project for someone else's credentials.

`discover_topics.py` uses the seed queries, language, and country in `site.config.json`. Its default run prints a plan. `--live` calls Apify's Google Search Scraper and consumes your allowance or credits. Start with a small seed list and check the provider's current pricing and actor input schema.

`enrich_faqs.py --all --dry-run` performs no paid requests. For a live run, install `execution/requirements-research.txt`, configure Apify plus either Anthropic or OpenRouter, and set `FAQ_MODEL` to an available model. `--live` researches questions and stages suggested FAQs for inspection. It does not make those answers true. Review the staged files and use `--apply` only after checking them; back up or commit your source first. Existing progress files make research resumable. Do not include private recordings or client data without permission.

Reddit scraping is off by default. Only enable it with `ENABLE_REDDIT=1` and configured `subreddits` after reviewing the current actor, costs, and source terms. The original actor can be unreliable. PAA questions can be used independently.

`analyze_competitor.py` reads requested public URLs and supports an optional `--firecrawl` provider. Run it only against domains you intentionally choose. Firecrawl requests may incur charges. Its output is a research note, not a verified claim about why a competitor ranks.
