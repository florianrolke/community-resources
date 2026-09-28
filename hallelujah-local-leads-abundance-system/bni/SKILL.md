# Skill: BNI Chapter Member Scraper

## Purpose

Scrape BNI (Business Network International) chapter member lists via Playwright, classify by industry, and enrich with LinkedIn + websites. BNI members are high-quality leads — they're vetted business owners who actively network, resulting in a **92% LinkedIn hit rate**.

## Why BNI Members Are High-Quality Leads

- **Vetted**: Each member passed an application process
- **Active networkers**: They maintain LinkedIn profiles and business websites
- **Consistent data**: Structured name + company pairings (easy to enrich)
- **One per category**: Only one member per industry per chapter (exclusive)
- **Decision makers**: Almost always the business owner or partner

## Quick Start

```bash
# 1. Discover chapters near a city (needs Perplexity key)
python -X utf8 discover_chapters.py --city "Charlotte" --state "NC" --radius 50

# 2. Scrape all chapters in config
python -X utf8 scrape_chapters.py --config data/example_chapters.json --all

# 3. Scrape a single chapter
python -X utf8 scrape_chapters.py --config data/example_chapters.json --chapter "Power Players"

# 4. Enrich with LinkedIn + websites
python -X utf8 enrich_members.py --input leads/bni_all_members.json

# 5. Export to CSV
python -X utf8 export_csv.py --input leads/bni_enriched.json --output leads/bni_leads.csv
```

## Hit Rates (Production — NYC, 537 leads)

| Group | Leads | LinkedIn | Websites |
|-------|-------|----------|----------|
| Title Services | 46 | 41 (89%) | 46 (100%) |
| Movers | 26 | 22 (85%) | 25 (96%) |
| Trades | 200 | 175 (88%) | 199 (99.5%) |
| Real Estate | 265 | 256 (97%) | 265 (100%) |
| **Total** | **537** | **494 (92%)** | **535 (99.6%)** |

## Supported BNI Portals

| Portal | Region | URL |
|--------|--------|-----|
| manhattanbni.com | NYC Manhattan | https://manhattanbni.com |
| bni-newyork.com | NYC Metro | https://bni-newyork.com |
| bni-nc.com | North Carolina | https://bni-nc.com |
| bni-mi.com | Michigan | https://bni-mi.com |
| bni-az.com | Arizona | https://bni-az.com |
| bni-ga.com | Georgia | https://bni-ga.com |
| bni-nj.com | New Jersey | https://bni-nj.com |
| bni-kc.com | Kansas City | https://bni-kc.com |
| bnisoutheast.com | Southeast US | https://bnisoutheast.com |
| bniperth.com.au | Perth, Australia | https://bniperth.com.au |

## Step-by-Step: New Region

1. **Discover chapters**: `python discover_chapters.py --city "Austin" --state "TX"`
2. **Build `chapters.json`**: Add each chapter with its detail URL
3. **Run scraper**: `python scrape_chapters.py --all`
4. **Adjust ICP keywords** in config if needed (default works for most industries)
5. **Run enrichment**: `python enrich_members.py --input leads/bni_all_members.json`
6. **Export CSV**: `python export_csv.py --input leads/bni_enriched.json`

## Data Fields

| Field | Source | Coverage |
|-------|--------|----------|
| Name | BNI page | 100% |
| Company | BNI page | 100% |
| Category | BNI page | 100% |
| Phone | BNI page | ~80% |
| Website | BNI page + enrichment | 99.6% |
| LinkedIn | Enrichment (Exa/Tavily) | 92% |
| ICP Tier | Keyword classification | 100% |

## LinkedIn Search Query

```
"{name}" "{company}" site:linkedin.com/in
```

Validated by checking name tokens appear in the LinkedIn slug.

## Gotchas

1. **Portal login walls**: Some portals (e.g., bnisoutheast.com) don't expose member lists publicly
2. **Pagination at 50 members**: Always click through Next buttons
3. **Count validation**: Compare scraped count vs header "Member Count: N" — if mismatch, pagination failed
4. **Different HTML per portal**: Each regional site has slightly different table structures

## API Budget per 500 Leads

~500 Exa calls (LinkedIn) + ~500 Exa calls (website) + Exa fallback
= Roughly 2 Exa keys (1,000/mo each) + 1 Tavily key as backup

## Scripts

| Script | Purpose |
|--------|---------|
| `discover_chapters.py` | Find BNI chapters near a city (Perplexity) |
| `scrape_chapters.py` | Universal BNI member scraper (Playwright) |
| `enrich_members.py` | LinkedIn + website enrichment |
| `export_csv.py` | CSV export with ICP tiers |
