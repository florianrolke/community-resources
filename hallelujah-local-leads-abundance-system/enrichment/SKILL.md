# Skill: Waterfall Lead Enrichment Engine

## Purpose

Enrich any lead with LinkedIn profile, business website, company research, and verified email — using a multi-source waterfall that never stops at the first failure.

## How It Works

```
Lead (company name + optional person name)
    │
    ├── find_website.py ─── Exa → Tavily → filters aggregator sites
    │
    ├── find_linkedin.py ── Exa (site:linkedin.com) → Tavily → validates name in slug
    │
    ├── research_company.py ── Perplexity Sonar → structured JSON
    │
    └── find_email.py ──── website scrape → pattern generation → SMTP verify (Reacher)
```

## Quick Start

```bash
cd enrichment

# Single company lookup
python -X utf8 find_website.py --company "Acme Corp" --city "Austin"
python -X utf8 find_linkedin.py --name "John Smith" --company "Acme Corp"

# Batch enrichment (reads any JSON with leads)
python -X utf8 enrich_batch.py --input ../chambers/leads/chamber_directory_members.json --output enriched.json

# Resume interrupted batch
python -X utf8 enrich_batch.py --input leads.json --resume

# Only enrich Tier A and B leads
python -X utf8 enrich_batch.py --input leads.json --tier "A,B"

# Skip exhausted API keys (start with key index 3)
python -X utf8 enrich_batch.py --input leads.json --exa-start 3
```

## API Key Rotation

The engine rotates across multiple API keys per service:

| Service | Env Variables | Monthly Quota |
|---------|--------------|---------------|
| Exa | `EXA_API_KEY` through `EXA_API_KEY_6` | 1,000/key = 6,000 total |
| Tavily | `TAVILY_API_KEY` through `TAVILY_API_KEY_6` | 1,000/key = 6,000 total |
| Perplexity | `PERPLEXITY_API_KEY` | Pay-per-query |

When a key hits rate limit (429/432), it's automatically marked exhausted and the next key is used. When all keys for a service are exhausted, the engine falls back to the next service in the waterfall.

## Checkpoint/Resume

Every 5 enriched leads, progress is saved to `.tmp/checkpoint_enrich_*.json`. If the script is interrupted (Ctrl+C, crash, API exhaustion), re-run with `--resume` to continue exactly where you left off.

## Hit Rates (Production)

| Source | LinkedIn | Website | Research |
|--------|----------|---------|----------|
| BNI members | 92% | 99% | N/A |
| Chamber members | 30-66% | 70% | 85% |
| Magazine advertisers | 60% | 90% | 80% |

## LinkedIn Validation

Every LinkedIn URL found is validated before being saved:
1. Extract the slug from the URL
2. Check that person's name tokens appear in the slug
3. Filter out generic slugs ("example", "profile", etc.)
4. Filter out company pages when looking for personal profiles

This prevents false positives where search APIs return unrelated profiles.

## Email Discovery Pipeline

1. **Website scraping**: Find mailto links and email patterns on the business website
2. **Pattern generation**: Try `first@domain`, `first.last@domain`, `info@domain`
3. **SMTP verification**: Self-hosted Reacher confirms the email is deliverable (~30s per check)

## Scripts

| Script | Purpose | Required Keys |
|--------|---------|---------------|
| `enrich_batch.py` | Full batch enrichment with checkpoint | Exa or Tavily |
| `find_linkedin.py` | LinkedIn profile discovery | Exa or Tavily |
| `find_email.py` | Email discovery + SMTP verify | None (Reacher optional) |
| `find_website.py` | Website discovery | Exa or Tavily |
| `research_company.py` | Deep company research | Perplexity |

## Cost Per 1,000 Leads

| Operation | API Calls | Cost |
|-----------|-----------|------|
| Website discovery | ~1,000 Exa | ~1 key month |
| LinkedIn discovery | ~1,000 Exa | ~1 key month |
| Company research | ~1,000 Perplexity | ~$5-10 |
| Email verification | ~500 Reacher | Free (self-hosted) |
| **Total** | | **~2 API keys + $5-10** |

## Input Format

`enrich_batch.py` accepts multiple JSON formats:
- **Array of leads**: `[{"company": "...", "name": "..."}, ...]`
- **Chamber format**: `[{"slug": "...", "members": [...]}]`
- **BNI format**: `{"chapters": [{"members": [...]}]}`

Any field named `company`, `business_name`, `name`, or `contact` is auto-detected.
