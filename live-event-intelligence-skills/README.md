# Live Event Intelligence Skills

Reusable Codex skills and deterministic scripts for finding local or niche live events, mapping conference relationships, and producing outreach-ready event prospect reports.

The workflow is based on proven client runs across manufactured housing, family law, medical tourism and local networking niches: start with a client/niche/location, generate layered deep-research queries, identify conferences and association events, extract visible speakers/exhibitors/sponsors/attendees, find LinkedIn profiles/pages, and export clean CSV/Markdown deliverables.

## Quick Start

```powershell
python scripts/generate_event_queries.py --niche "manufactured housing" --city "Las Vegas" --year 2026 --event-name "MHI 2026 Congress & Expo" --companies "EXO Edge" "21st Mortgage Corporation" --people "Nikki Greenberg|Futurist" "Laura Eldredge|EXO Edge"
python scripts/find_linkedin_profiles.py --input tests/fixtures/mhi_contacts.csv --output reports/mhi-linkedin-matches.csv
python scripts/normalize_events.py --input tests/fixtures/mhi_events_raw.csv --output reports/mhi-events-normalized.csv
python scripts/generate_event_report.py --events reports/mhi-events-normalized.csv --contacts reports/mhi-linkedin-matches.csv --output reports/mhi-event-report.md
```

## The conference pipeline (new)

Finding an event is half the job. These three turn a named event into a client-ready deliverable:

```bash
# 1. Read the conference's own site. Free.
python -X utf8 -m scripts.scrape_conference_roster     --url https://example.com/2026/speakers     --event-name "Example Conference 2026" --output data/speakers.csv

# 2. Match LinkedIn profiles for people you already have names for. Free.
python -X utf8 -m scripts.enrich_conference_companies     --input data/speakers.csv --output data/speakers-li.csv --linkedin-only

# 3. Build the client-facing binder. Free.
python -X utf8 -m scripts.build_event_binder     --config data/binder.json --outdir dist/example
```

Verified end to end against Behavioral Health Tech 2026 (Nashville, Sept 22-24):
100 speakers with title and company, 186 sponsor companies read off the logo
wall, 22 LinkedIn profiles verified on both first and last name. 311 records,
about two minutes, $0.00.

Sponsor and exhibitor lists are usually a **logo wall** — images, not text —
which is why the roster scraper drives a real browser instead of fetching HTML.

## Core Outputs

- Google Sheets-ready event CSVs
- Contact and LinkedIn match CSVs
- Association/event-calendar CSVs
- Concise Markdown reports with evidence and next actions

## Source Policy

Prefer official pages, Google SERP, professional association pages, 10times, and tightly scoped Eventbrite. Avoid broad AllEvents scans by default. Require explicit approval for authenticated LinkedIn automation, LinkedIn participant scraping, full Instagram follower scrapes, or paid runs above the configured cap.
## 2026 Outcome-First Layer

This repo now includes an outcome-first ranking layer for turning messy deep-research outputs into action maps. Treat Perplexity/Genspark reports as lead lists, not evidence. Verify important claims, rank opportunities, and produce action-ready outputs.

New references:
- `references/outcome-first-opportunity-mapping.md`
- `references/niche-playbooks.md`

New deterministic script:

```powershell
python scripts/rank_opportunities.py --input reports/events-normalized.csv --output reports/events-ranked.csv
```

The ranker supports manufactured housing, AI/VapiCon-style startup conferences, CPA/CPE, exit planning, HVAC/plumbing, and local business networking patterns by scoring ICP fit, access quality, timeliness, commercial intent, relationship leverage, and source confidence.
