# Chamber of Commerce Platform Identification Guide

> How to identify which platform a chamber uses, so you know which scraper to run.

---

## The 6 Platforms

### 1. GrowthZone (~40% of US chambers)

**URL patterns:**
- `*growthzoneapp.com/memberdirectory`
- `*growthzoneapp.com/directory`
- `business.{chamber}.org/directory`
- `gz.{chamber}.org/directory`

**HTML signatures:**
- CSS classes: `gz-results-card`, `gz-directory-card`, `gz-card-title`, `gz-card-address`
- A-Z navigation: links containing `FindStartsWith?term=`
- Result count: `.gz-results-count` element

**Scraper:** `scrape_directory.py` (auto-detects FindStartsWith pattern)

---

### 2. ChamberMaster (~35% of US chambers)

**URL patterns:**
- `business.{chamber}.org/list`
- `{slug}.chambermaster.com/list`
- `members.{chamber}.org/list`
- `cm.{chamber}.org/list`

**HTML signatures:**
- SAME `gz-*` CSS classes as GrowthZone (they're the same platform!)
- A-Z navigation: links containing `searchalpha/`
- Legacy variant: `/prod/allcategories` (requires deep scraper)

**Scraper:** `scrape_directory.py` (auto-detects searchalpha pattern)

**Important:** GrowthZone and ChamberMaster are the SAME platform under the hood. The difference is URL convention: `/list` vs `/directory` or `/memberdirectory`.

---

### 3. Atlas / WebLink Connect (~10% of US chambers)

**URL patterns:**
- `web.{chamber}.com/atlas/directory`
- `atlas.{chamber}.com/directory`
- Contains `weblinkconnect.com` in API calls

**HTML signatures:**
- Angular SPA (heavy JavaScript rendering)
- `h2.mb-15` elements for company names
- Social links in sibling `div.ml-27`
- No traditional HTML tables — all JS-rendered

**Scraper:** `scrape_atlas_api.py` (REST API approach) or `scrape_directory.py` (DOM extraction fallback)

**Key detail:** Atlas requires a JWT token obtained via Playwright. The token comes from the `Tenant/Current` API endpoint. Each chamber has a unique `x-tenant` header value (e.g., "CaryNCCOC").

---

### 4. WordPress (~5% of chambers)

**URL patterns:**
- Various — no standard pattern
- Often `/member-directory/` or `/our-members/`

**HTML signatures:**
- `wp-content` in page source
- WordPress generator meta tag
- Typical layouts: cards, tables, or plain lists

**Scraper:** `scrape_directory.py --generic` (tries 10+ CSS selectors)

**Warning:** Some WordPress chambers have 2-3 level navigation (categories → subcategories → members). If the generic scraper returns 0 members, use `scrape_deep.py`.

---

### 5. Locable (~3% of chambers)

**URL patterns:**
- Various `/directory` endpoints

**HTML signatures:**
- "Powered by Locable" in footer
- `.locable-business` CSS class

**Scraper:** `scrape_directory.py --generic`

---

### 6. Wix (~2% of chambers)

**URL patterns:**
- Various

**HTML signatures:**
- `wix.com` in page source
- `_wix_browser_sess` cookie

**Scraper:** `scrape_directory.py --generic`

---

## Quick Detection Checklist

When you encounter a new chamber directory:

1. **Check the URL** — Does it contain `growthzoneapp.com`, `chambermaster.com`, `/atlas/`, `/list`?
2. **View page source** (Ctrl+U) — Search for `gz-`, `growthzone`, `chambermaster`, `wp-content`, `wix.com`, `locable`
3. **Check for subdomains** — The directory is often on `business.{domain}`, `members.{domain}`, or `web.{domain}`
4. **Run `platform_detector.py`** — `python platform_detector.py "https://business.opchamber.org/list"`

## Platform Distribution (from 100+ chambers scraped)

| Platform | % of Chambers | LinkedIn from Detail Pages | Members per Chamber |
|----------|--------------|---------------------------|---------------------|
| GrowthZone | 40% | 56-100% | 200-2,000 |
| ChamberMaster | 35% | 56-100% | 100-1,500 |
| Atlas | 10% | 95%+ (via API) | 200-1,500 |
| WordPress | 5% | 0% (no detail pages) | 50-500 |
| Locable | 5% | 0% | 50-300 |
| Wix/Custom | 5% | 0% | 20-200 |

GrowthZone and ChamberMaster detail pages have the highest LinkedIn extraction rates because they use standardized `gz-social-linkedin` CSS classes for member social links.
