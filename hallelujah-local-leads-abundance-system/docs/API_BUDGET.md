# API Budget Calculator

> How much does it cost to process leads at various scales?

---

## Cost Per Pillar

### Chamber of Commerce Scraping
| Resource | Cost |
|----------|------|
| Playwright + Chromium | **Free** (open source) |
| Detail page scraping | **Free** (direct HTTP) |
| **Total per chamber** | **$0** |

Chambers are 100% free to scrape. No API keys needed for the scraping itself. You only need API keys for enrichment (Pillar 4).

### BNI Chapter Scraping
| Resource | Cost |
|----------|------|
| Playwright + Chromium | **Free** |
| Chapter discovery (Perplexity) | ~$0.01 per query |
| **Total per region** | **~$0.10-0.50** |

BNI scraping is nearly free. Perplexity is only used for chapter discovery (one query per city), not per-member.

### Magazine Advertiser Pipeline
| Resource | Usage per Issue | Cost |
|----------|-----------------|------|
| Firecrawl screenshots | ~60 pages | ~50-100 credits |
| Claude Haiku vision | ~60 API calls | ~$0.10-0.20 |
| Exa enrichment | ~15-20 searches | 15-20 of 1000/mo |
| Reacher SMTP verify | ~10-15 emails | Free (self-hosted) |
| **Total per issue** | | **~$0.50 + API credits** |

### Enrichment Engine
| Operation | API Calls per Lead | Cost per 100 Leads |
|-----------|-------------------|-------------------|
| Website discovery (Exa) | 1 | 100 of 1000/mo per key |
| LinkedIn discovery (Exa) | 1 | 100 of 1000/mo per key |
| Company research (Perplexity) | 1 | ~$0.50-1.00 |
| Email verification (Reacher) | 0.5 | Free (self-hosted) |
| **Total per 100 leads** | ~2.5 | **~200 API credits + $0.50-1.00** |

---

## Scaling Guide

### With 1 Key Per Service (Minimum Setup)
- 1 Exa key = 1,000 searches/month
- Enough for: ~500 leads enriched (website + LinkedIn)
- Plus: unlimited chamber + BNI scraping

### With 6 Keys Per Service (Recommended)
- 6 Exa keys = 6,000 searches/month
- 6 Tavily keys = 6,000 searches/month (fallback)
- Enough for: ~3,000-6,000 leads enriched per month
- Plus: unlimited chamber + BNI scraping

### Monthly Budget for Full Operation
| Item | Cost | Notes |
|------|------|-------|
| Exa (6 keys) | Free tier | 1,000 free searches per key per month |
| Tavily (6 keys) | Free tier | 1,000 free searches per key per month |
| Perplexity | ~$5-20 | Pay-per-query, optional |
| Firecrawl | ~$10 | 500 credits/month, magazines only |
| Claude Haiku | ~$1-5 | Vision API for magazine ads |
| Reacher | Free | Self-hosted on your server |
| **Total** | **~$16-35/month** | For full 4-pillar operation |

---

## Key Rotation Strategy

When keys get exhausted:

1. **Exa**: Keys 1 → 2 → 3 → 4 → 5 → 6 (rotate all)
2. **Tavily**: Start with key 5 → 6 → 1 → 2 → 3 (skip pre-exhausted)
3. **Perplexity**: Single key, use sparingly (deep research only)

The `lib/api_key_rotation.py` handles this automatically. When a key returns HTTP 429 (rate limit) or 432 (quota exceeded), it's marked exhausted and the next key is used.

---

## Free Tier Maximization

To maximize free API usage:
1. **Sign up for 6 Exa accounts** — Each gets 1,000 free searches/month
2. **Sign up for 6 Tavily accounts** — Each gets 1,000 free searches/month
3. **Use Perplexity only for chapter discovery + deep research** — Not for bulk search
4. **Self-host Reacher for email verification** — No per-email cost
5. **Prioritize enrichment by ICP tier** — Only enrich Tier A and B leads first
