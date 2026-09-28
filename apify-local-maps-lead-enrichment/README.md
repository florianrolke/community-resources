# Apify Local Maps Lead Enrichment

Reusable, industry-agnostic workflow for building local business lead lists from Google Maps data and enriching them into outreach-ready records.

It was extracted from a large mobile home park project, but the package is not MHP-specific. Swap the config terms and location grid to target any local industry: dentists, roofers, med spas, HVAC contractors, specialty retailers, operators, resellers, or niche B2B service providers.

## What It Does

- Builds Google Maps search queries from industry terms and locations.
- Runs Apify in checkpointed batches.
- Saves raw JSON and parsed CSV after every paid batch.
- Enriches known websites for emails, phones, social links, and named contacts.
- Verifies candidate emails in separate checkpointed batches.
- Avoids all-or-nothing overnight runs.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Add your Apify token to `.env`, then dry-run:

```bash
python src/maps_discovery.py --config config/example_industry.json --locations examples/locations.csv --dry-run
```

Run the first paid batch:

```bash
python src/maps_discovery.py --config config/example_industry.json --locations examples/locations.csv --max-batches 1
```

## Enrichment

Create a CSV queue with `website` or `input_url`, then run:

```bash
python src/contact_enrichment.py --queue outputs/maps_discovery/parsed_batch_00000.csv --max-batches 1
```

Create an email queue with an `email` column, then verify:

```bash
python src/email_verify.py --queue examples/email_queue.csv --max-batches 1
```

## Public Repo Safety

This repo intentionally excludes real lead data, raw client outputs, `.env` files, API tokens, and private enrichment results.

