# Skill: Chamber of Commerce Directory Scraper

## Purpose

Scrape business member directories from any US Chamber of Commerce website. Auto-detects the platform type and uses the right scraping strategy. Handles 6+ platform types covering ~95% of US chambers.

## Supported Platforms

| Platform | % of Chambers | Scraper | Technique |
|----------|--------------|---------|-----------|
| **GrowthZone** | ~40% | `scrape_directory.py` | A-Z `FindStartsWith?term=` |
| **ChamberMaster** | ~35% | `scrape_directory.py` | A-Z `searchalpha/{letter}` |
| **Atlas (WebLink)** | ~10% | `scrape_atlas_api.py` | REST API + Playwright JWT |
| **WordPress** | ~5% | `scrape_directory.py --generic` | Multi-selector fallback |
| **Locable** | ~5% | `scrape_directory.py --generic` | Multi-selector fallback |
| **Wix/Custom** | ~5% | `scrape_directory.py --generic` | Multi-selector fallback |

**Key insight:** GrowthZone and ChamberMaster are the SAME platform under the hood (same `gz-*` CSS classes). The only difference is URL pattern.

## Quick Start

```bash
# 1. Detect what platform a chamber uses
python -X utf8 platform_detector.py "https://business.opchamber.org/list"

# 2. Scrape all chambers in config
python -X utf8 scrape_directory.py --config data/example_chambers.json --all

# 3. Scrape a single chamber
python -X utf8 scrape_directory.py --config data/chambers.json --chamber olathe

# 4. Scrape Atlas SPA chambers (requires tenant ID)
python -X utf8 scrape_atlas_api.py --url "https://web.carychamber.com/atlas/directory" --tenant CaryNCCOC

# 5. Scrape multi-level WordPress directories
python -X utf8 scrape_deep.py --url "https://chamber.example.org/members"

# 6. Extract LinkedIn/social from detail pages (overnight job)
python -X utf8 scrape_detail_pages.py --config data/chambers.json

# 7. Resume interrupted detail scraping
python -X utf8 scrape_detail_pages.py --config data/chambers.json --resume
```

## Step-by-Step: New City

### Phase 1: Research (~15 min)
1. Use Perplexity: "List all chambers of commerce in [Metro Area] with their websites and member directory URLs"
2. Visit each directory URL and note the platform type
3. Run `platform_detector.py` to auto-detect

### Phase 2: Configure (~10 min)
Create `data/chambers.json`:
```json
{
  "chambers": [
    {
      "slug": "kc-metro",
      "name": "Greater Kansas City Chamber",
      "city": "Kansas City",
      "state": "MO",
      "directory_url": "https://...growthzoneapp.com/memberdirectory",
      "platform": "GrowthZone",
      "public_directory": true
    }
  ]
}
```

### Phase 3: Scrape (~1-2 hours)
```bash
python -X utf8 scrape_directory.py --config data/chambers.json --all
```

### Phase 4: Detail Enrichment (~3 hours, run overnight)
```bash
python -X utf8 scrape_detail_pages.py --config data/chambers.json
```

## Data Fields Extracted

**From directory listing:**
- Company name, address, phone, website
- Category (used for ICP classification)
- Detail page URL
- ICP tier (A/B/C/D)

**From detail pages (GrowthZone/ChamberMaster):**
- LinkedIn (company + personal profiles)
- Facebook, Twitter, Instagram, YouTube
- Contact persons (name, title, phone, email)
- Business description

## ICP Classification

| Tier | Label | Example Keywords |
|------|-------|-----------------|
| A | High-Value Services | consulting, financial, marketing, technology, insurance |
| B | Professional Services | attorney, medical, dental, architecture, engineering |
| C | Local Trades | roofing, plumbing, HVAC, contractor, landscaping |
| D | Other | restaurant, retail, nonprofit, church |

Customizable via `lib/icp_classifier.py` or passing your own keyword dict.

## Critical Gotchas

1. **LinkedIn Pollution**: Chamber's own LinkedIn appears on every member detail page. Filter via `CHAMBER_SOCIAL_PATTERNS`. Check header/footer BEFORE scraping.

2. **Share Buttons**: Look like social links. Filter `shareArticle`, `sharer.php`, `intent/tweet`.

3. **Cloudflare Blocking**: Try `{slug}.chambermaster.com/list` instead of chamber's own domain.

4. **Multi-level Directories**: If scraper returns 0 members, the directory has category navigation. Use `scrape_deep.py`.

5. **Subdomain Directories**: Check `business.`, `members.`, `web.` subdomains — often that's where the directory lives.

6. **OneDrive Write Conflicts**: Use direct `open(path, 'w')` instead of atomic rename. `lib/safe_io.py` handles this.

7. **ChamberMaster Referral URLs**: Social links use `referral.aspx?URL=` redirect. Decode the parameter.

See `docs/GOTCHAS.md` for all 44 lessons learned.

## Expected Results

| Metric | Typical Value |
|--------|--------------|
| Members per chamber | 100-2,000 |
| Chambers per metro | 10-25 |
| Tier A leads | 15% of members |
| LinkedIn from detail pages | 56-100% (GZ/CM) |
| Time: directory scrape | ~1.5 hours |
| Time: detail enrichment | ~3 hours |

## Scripts

| Script | Purpose |
|--------|---------|
| `platform_detector.py` | Auto-detect chamber platform type |
| `scrape_directory.py` | Universal GZ/CM + generic scraper |
| `scrape_atlas_api.py` | Atlas SPA via REST API |
| `scrape_deep.py` | Multi-level WordPress/legacy directories |
| `scrape_detail_pages.py` | LinkedIn/social extraction from detail pages |
| `enrich_detail_safe.py` | Safe per-chamber detail enrichment with checkpoint |
