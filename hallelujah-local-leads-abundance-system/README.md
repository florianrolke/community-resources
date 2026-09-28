# Hallelujah Local Leads Abundance System

**Automated Local Business Intelligence Engine — Turn any US city into a lead pipeline in 30 minutes.**

> Built from 40,000+ real businesses scraped across 16 clients in 12 markets. Production-tested, not a prototype.

---

## What This Does

Point it at any US city. It finds every local business through 3 trusted sources, enriches each with LinkedIn + email + company intel, and produces a prioritized lead database sorted by industry fit.

### The 6 Pillars

| # | Pillar | Source | What You Get |
|---|--------|--------|-------------|
| 1 | **Chamber Scraper** | Chamber of Commerce directories | Company, phone, website, category, contacts, ICP tier |
| 2 | **BNI Scraper** | BNI chapter member lists | Name, company, category + 92% LinkedIn hit rate |
| 3 | **Magazine Scraper** | City Lifestyle magazine ads | Business name, owner, ad frequency, spending signal |
| 4 | **Enrichment Engine** | Exa, Tavily, Perplexity APIs | LinkedIn, email (SMTP verified), company research |
| 5 | **Website Redesign** | 46-component luxury design library | Cinematic redesign + live preview URL as lead magnet |
| 6 | **Outreach Automation** | Playwright + CapSolver | Auto-fill chamber/website contact forms with CAPTCHA solving |

### Production Numbers

- **40,000+** businesses scraped
- **5,000+** LinkedIn profiles discovered
- **16 clients** across US, UK, Australia
- **6+ chamber platforms** auto-detected (GrowthZone, ChamberMaster, Atlas, WordPress, Locable, Wix)
- **92%** LinkedIn hit rate on BNI members
- **$16-35/month** total cost for all pillars

---

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/your-repo/hallelujah-local-leads-abundance-system.git
cd hallelujah-local-leads-abundance-system
cp .env.template .env          # Add your API keys
pip install -r requirements.txt
pip install -e .
playwright install chromium

# 2. Scrape a chamber of commerce (FREE — no API keys needed)
cd chambers
python -X utf8 scrape_directory.py --config data/example_chambers.json --all

# 3. Enrich top leads with LinkedIn + website
cd ../enrichment
python -X utf8 enrich_batch.py --input ../chambers/leads/chamber_directory_members.json --tier "A,B"
```

---

## Architecture

```
City Name + Industry
       │
       ├── Chamber Scraper ──── 6+ platforms auto-detected
       ├── BNI Scraper ──────── 11 regional portals
       └── Magazine Scraper ─── AI vision ad detection
              │
              ▼
       Waterfall Enrichment
       Exa → Tavily → Perplexity
       (6 keys each, auto-rotation)
              │
              ▼
       Prioritized Lead Database
       Tier A > B > C > D
       + LinkedIn, email, company research
```

---

## Why This Wins

1. **Multi-source**: Chambers + BNI + magazines = comprehensive local coverage
2. **Battle-tested**: 40+ production gotchas baked in (see `docs/GOTCHAS.md`)
3. **Resilient**: API key rotation, checkpoint/resume, graceful shutdown
4. **Smart**: ICP classification auto-prioritizes high-value leads
5. **Cheap**: Chamber + BNI scraping is free. Full enrichment ~$0.15/lead
6. **Fast**: 30 min setup → first leads. 3-4 hours for a full metro area

---

## Documentation

| Doc | What It Covers |
|-----|----------------|
| `SKILL.md` | Master guide — start here |
| `chambers/SKILL.md` | Chamber scraper deep-dive |
| `bni/SKILL.md` | BNI scraper deep-dive |
| `magazine/SKILL.md` | Magazine pipeline deep-dive |
| `enrichment/SKILL.md` | Enrichment engine deep-dive |
| `website/SKILL.md` | Website redesign engine deep-dive |
| `outreach/SKILL.md` | Contact form outreach automation |
| `docs/PLATFORM_GUIDE.md` | How to identify chamber platforms |
| `docs/GOTCHAS.md` | 40+ lessons learned the hard way |
| `docs/API_BUDGET.md` | Cost calculator per pillar |
| `samples/` | Real (anonymized) output data |

---

## Requirements

- Python 3.10+
- Playwright + Chromium (free)
- API keys: Exa (free tier), Tavily (free tier), Perplexity (optional), Firecrawl + Anthropic (magazine + website)

---

## License

MIT

---

*Built with Claude Code. 80+ scripts consolidated into a production-ready system.*
