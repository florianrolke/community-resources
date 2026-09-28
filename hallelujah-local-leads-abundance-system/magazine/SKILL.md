# Skill: City Lifestyle Magazine Advertiser Pipeline

## Purpose

Scrape City Lifestyle magazine issues from Issuu, detect advertisers via Claude Haiku vision AI, enrich each with business data (owner, LinkedIn, email, website), and generate per-issue HTML reports with NEW/SEEN flagging across issues.

Advertisers in lifestyle magazines are high-quality leads — they're businesses already spending money on marketing to local audiences.

## Pipeline

```
Issuu Slug Discovery
    → Firecrawl Screenshots (1920x1080)
        → crop_issuu_chrome() (brightness analysis)
            → Claude Haiku Vision (ad detection per page)
                → Exa Enrichment (owner, LinkedIn, industry)
                    → Meta Description Scraping
                        → SMTP Verification (Reacher)
                            → HTML Report Generation
                                → Dedup + NEW/SEEN Flagging
```

## Quick Start

```bash
cd magazine

# Process one issue
python -X utf8 process_issue.py --edition johnsoncounty --year 2026 --month 3

# Skip enrichment (just detect ads)
python -X utf8 process_issue.py --edition johnsoncounty --year 2026 --month 3 --skip-enrich

# Resume interrupted processing
python -X utf8 process_issue.py --edition johnsoncounty --year 2026 --month 2 --resume

# Rebuild flagged reports across all issues
python -X utf8 rebuild_flagged.py --edition johnsoncounty --leads-dir leads/
```

## Configuration

Add editions to `data/editions.json`:
```json
{
  "editions": [
    {
      "slug": "johnsoncounty",
      "name": "Johnson County",
      "issuu_name": "johnson_county",
      "state": "KS",
      "slug_pattern": "{edition}_{state}_{month}_{year}",
      "months_available": [8, 9, 10, 11, 12, 1, 2, 3]
    }
  ]
}
```

Issuu slug format: `{edition}_{state}_{month}_{year}` (e.g., `johnson_county_ks_march_2026`)

Verify slug works at: `https://e.issuu.com/embed.html?d={slug}`

## Key Technical Details

### Issuu Chrome Removal
The `crop_issuu_chrome()` function removes Issuu UI elements via brightness analysis:
- Scans rows for dark→bright transition (`dark_thresh=130`)
- Bottom = top + 59% of height
- Removes zoom controls, "Create a flipbook" text, dark sidebars

### Blank Page Detection
Pages with file size < 55KB are blank. Pages 62+ in Johnson County issues are consistently blank. The pipeline auto-skips these.

### Ad Detection Prompt
Claude Haiku receives each page image and returns:
```json
[{"business_name": "Smith Dental", "ad_type": "half_page"}]
```
Ad types: `full_page`, `half_page`, `quarter_page`, `strip`, `logo_only`

### NEW/SEEN Flagging
- Processes newest-first (March 2026 → August 2025)
- NEW leads: green badge, full opacity, displayed at top
- SEEN leads: gray badge with "ALREADY IN: {month} {year}", 45% opacity
- Name normalization: lowercase, strip punctuation, strip "llc"/"inc" suffixes

## Proven Results (Johnson County KS, 8 issues)

| Metric | Value |
|--------|-------|
| Issues processed | 8 (Aug 2025 - Mar 2026) |
| Raw leads detected | 504 |
| Unique after dedup | 253 |
| LinkedIn profiles | 227 (90%) |
| Emails found | 83 (33%) |
| Owners identified | 200 (79%) |
| Repeat advertisers (4+ issues) | 40 |

## Cost Per Issue

| Resource | Usage | Cost |
|----------|-------|------|
| Firecrawl screenshots | ~60 pages | ~50-100 credits |
| Claude Haiku vision | ~60 calls | ~$0.10-0.20 |
| Exa enrichment | ~15-20 searches | 15-20 of 1000/mo |
| Reacher SMTP | ~10-15 emails | Free (self-hosted) |
| **Total** | | **~$0.50 + API credits** |

## API Keys Required

| Key | Purpose | Required? |
|-----|---------|-----------|
| `FIRECRAWL_API_KEY` | Page screenshots | Yes |
| `ANTHROPIC_API_KEY` | Haiku vision ad detection | Yes |
| `EXA_API_KEY` | Enrichment | For enrichment step |
| `REACHER_API_URL` | Email verification | Optional |

## Scripts

| Script | Purpose |
|--------|---------|
| `process_issue.py` | Full pipeline orchestrator |
| `scrape_pages.py` | Firecrawl screenshots + chrome removal |
| `detect_ads.py` | Claude Haiku vision ad detection |
| `enrich_advertisers.py` | Exa enrichment + meta scraping |
| `build_report.py` | HTML report generator |
| `rebuild_flagged.py` | NEW/SEEN flagging across issues |

## Gotchas

1. **Issuu URL format**: Use `e.issuu.com/embed.html?d=SLUG`, NOT `issuu.com/lifestylepubs/docs/SLUG`
2. **Firecrawl v2**: Use `"formats": ["screenshot"]` only — don't pass screenshot options
3. **Pages 62+ are blank**: Save API credits by stopping early
4. **Dedup needs merge groups**: "Haley Epps Realtor" / "Haley Epp Realtor" won't match automatically
5. **Exa keys 1-3 may be exhausted**: Start with key 4 (`--exa-start 3`)
