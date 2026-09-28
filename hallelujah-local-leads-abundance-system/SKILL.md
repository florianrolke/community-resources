# Hallelujah Local Leads Abundance System

> Turn any US city into a lead pipeline in 30 minutes.

Built from **40,000+ real businesses** scraped across **16 clients in 12 markets** (US, UK, Australia). This is not a prototype — it's the production system that generates **100+ qualified prospects per week** for local service businesses.

Tell Claude a city name and an industry. It will:
1. Find every chamber of commerce in the metro area
2. Scrape their member directories across 6+ platform types
3. Scrape BNI chapters for high-intent business networkers
4. Scrape City Lifestyle magazine issues for advertisers already spending on marketing
5. Enrich every lead with LinkedIn, email, business context, and ICP tier scoring
6. Generate a luxury website redesign as a lead magnet — deployed to a live preview URL

Every gotcha from 3 months of production is baked in: LinkedIn pollution filtering, Cloudflare workarounds, referral URL decoding, Issuu chrome removal, BNI portal pagination across 11 regional sites.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           HALLELUJAH LOCAL LEADS ABUNDANCE SYSTEM        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ CHAMBER  │  │   BNI    │  │ MAGAZINE │  │ WEBSITE  │  │
│  │ SCRAPER  │  │ SCRAPER  │  │ SCRAPER  │  │ REDESIGN │  │
│  │Playwright│  │Playwright│  │Firecrawl │  │Claude+46 │  │
│  │6 platfrms│  │11 portals│  │Vision AI │  │components│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │             │              │        │
│       └──────┬───────┴─────────────┴──────────────┘        │
│                      ▼                                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │         WATERFALL ENRICHMENT ENGINE              │    │
│  │                                                   │    │
│  │  Exa ──→ Tavily ──→ Perplexity                   │    │
│  │  (LinkedIn/website)  (fallback)  (deep research)  │    │
│  │                                                   │    │
│  │  + API key rotation (6 keys per service)          │    │
│  │  + Checkpoint/resume every 5 leads                │    │
│  │  + Automatic fallback on rate limits              │    │
│  └─────────────────────┬───────────────────────────┘    │
│                        ▼                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │          PRIORITIZED LEAD DATABASE               │    │
│  │                                                   │    │
│  │  Tier A: High-Value (consulting, finance, tech)   │    │
│  │  Tier B: Professional (legal, medical)            │    │
│  │  Tier C: Local Trades (roofing, HVAC)             │    │
│  │  Tier D: Other                                    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Setup
```bash
cd hallelujah-local-leads-abundance-system
cp .env.template .env
# Edit .env — add at minimum one EXA_API_KEY

pip install -r requirements.txt
pip install -e .
playwright install chromium
```

### 2. Scrape a Chamber of Commerce (Free — no API keys needed)
```bash
cd chambers
python -X utf8 scrape_directory.py --config data/example_chambers.json --all
# Output: leads/chamber_directory_members.json
```

### 3. Scrape BNI Chapters (Free)
```bash
cd bni
python -X utf8 scrape_chapters.py --config data/example_chapters.json --all
# Output: leads/bni_all_members.json
```

### 4. Enrich with LinkedIn + Website (Needs Exa key)
```bash
cd enrichment
python -X utf8 enrich_batch.py --input ../chambers/leads/chamber_directory_members.json --tier "A,B"
# Output: chamber_directory_members_enriched.json
```

### 5. Process a Magazine Issue (Needs Firecrawl + Anthropic keys)
```bash
cd magazine
python -X utf8 process_issue.py --edition johnsoncounty --year 2026 --month 3
# Output: leads/magazine_report_johnsoncounty_march_2026.html
```

---

## The 6 Pillars

| Pillar | What It Does | Cost | SKILL.md |
|--------|-------------|------|----------|
| **Chambers** | Scrape member directories from 6+ platform types | Free | `chambers/SKILL.md` |
| **BNI** | Scrape chapter members with 92% LinkedIn hit rate | Free | `bni/SKILL.md` |
| **Magazine** | Detect advertisers via AI vision, enrich owners | ~$0.50/issue | `magazine/SKILL.md` |
| **Enrichment** | Waterfall: Exa → Tavily → Perplexity | ~$0.15/lead | `enrichment/SKILL.md` |
| **Website** | Luxury redesign with 46 components + cinematic animations | ~$0.05/site | `website/SKILL.md` |
| **Outreach** | Auto-fill contact forms with Playwright + CAPTCHA solving | ~$0.002/form | `outreach/SKILL.md` |

---

## Production Stats

| Metric | Value |
|--------|-------|
| Businesses scraped | 40,000+ |
| LinkedIn profiles found | 5,000+ |
| Clients deployed | 16 |
| Markets covered | US (10 states), UK, Australia |
| Chamber platforms supported | 6+ |
| BNI portals supported | 11 |
| LinkedIn hit rate (BNI) | 92% |
| LinkedIn hit rate (Chambers) | 30-66% |
| Monthly cost (all pillars) | $16-35 |
| Scripts consolidated | 80+ → ~20 |

---

## API Keys Required

| Key | Required For | Free Tier |
|-----|-------------|-----------|
| **None** | Chamber + BNI scraping | Always free |
| `EXA_API_KEY` | Enrichment (LinkedIn/website) | 1,000/mo per key |
| `TAVILY_API_KEY` | Enrichment fallback | 1,000/mo per key |
| `PERPLEXITY_API_KEY` | Deep research + BNI discovery | Pay-per-query |
| `FIRECRAWL_API_KEY` | Magazine screenshots | 500 credits/mo |
| `ANTHROPIC_API_KEY` | Magazine ad detection (Haiku) | Pay-per-token |
| `OPENROUTER_API_KEY` | Vision fallback when Anthropic exhausted | Pay-per-token |
| `CAPSOLVER_API_KEY` | Outreach CAPTCHA solving | ~$0.002/solve |

**Minimum viable setup:** Playwright (free) for scraping + 1 Exa key for enrichment.

---

## File Structure

```
hallelujah-local-leads-abundance-system/
├── SKILL.md              ← You are here
├── chambers/             ← Pillar 1: Chamber of Commerce scraper
├── bni/                  ← Pillar 2: BNI chapter scraper
├── magazine/             ← Pillar 3: Magazine advertiser pipeline
├── enrichment/           ← Pillar 4: Waterfall enrichment engine
├── website/              ← Pillar 5: Website redesign engine (46 components + 6 palettes)
├── outreach/             ← Pillar 6: Contact form outreach (Playwright + CapSolver)
├── lib/                  ← Shared utilities (key rotation, checkpoint, etc.)
├── samples/              ← Sample output data for reference
└── docs/                 ← PLATFORM_GUIDE, GOTCHAS, API_BUDGET
```

---

## How to Use for a New City

1. **Research chambers**: Use Perplexity to find all chambers in the metro area
2. **Create `chambers.json`**: Add each chamber with its directory URL and platform type
3. **Run `platform_detector.py`** on each URL to auto-detect the platform
4. **Run `scrape_directory.py --all`** to scrape all chambers
5. **Run `scrape_detail_pages.py`** overnight for LinkedIn/social extraction
6. **Run `enrich_batch.py --tier A,B`** to enrich top prospects
7. **Generate redesign** for top prospects: `python website/full_pipeline.py --url "https://prospect.com" --slug prospect --effect cinematic-full`
8. **Auto-submit outreach** via contact forms: `python outreach/chamber_form_outreach.py --leads chambers/leads/chamber_directory_members.json`
9. **Export** to CSV or push to your CRM

Total time: ~30 minutes of setup + 3-4 hours of automated scraping.
