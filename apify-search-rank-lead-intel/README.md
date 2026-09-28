# Apify Search Rank Lead Intel

Generic, industry-agnostic workflow for reverse-engineering which companies show up in local search rankings, preserving query/rank metadata, and turning the ranked companies into enrichment queues.

This was extracted from a Texas mobile home reseller discovery project, but it is not limited to mobile homes. Use it for any niche where search visibility matters: dealers, clinics, contractors, franchisees, resellers, specialty services, or local B2B operators.

## What Makes It Different

Normal scraping gives you a list. This preserves ranking intelligence:

- the exact input query
- location searched
- result rank
- top 3/top 10/top 20 bucket
- Google category
- company rollup across searches

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Dry-run:

```bash
python src/rank_discovery.py --config config/example_rank_intel.json --locations examples/locations.csv --dry-run
```

Run one batch:

```bash
python src/rank_discovery.py --config config/example_rank_intel.json --locations examples/locations.csv --max-batches 1
```

Roll up accepted companies:

```bash
python src/rollup_rankings.py --input-dir outputs/rank_discovery
```

## Mobile Home Reseller Use

See `docs/mobile-home-reseller-plan.md` for the focused MHP/reseller implementation plan.

## Public Repo Safety

This repo excludes real lead data, raw client outputs, `.env` files, API tokens, and private enrichment results.

