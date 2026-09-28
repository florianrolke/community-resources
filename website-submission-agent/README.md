# Website Submission Agent

Playwright-based website form submission agent for legitimate B2B outreach.

The agent opens a prospect website, finds likely contact/request/quote pages,
detects form fields, fills sender and message data, optionally solves supported
CAPTCHAs with CapSolver, and records local logs/screenshots for review.

## Features

- Single-site or CSV/JSON batch mode
- Contact-page discovery from nav, footer, and common contact URLs
- Dynamic mapping for name, email, phone, company, subject, address, selects,
  textareas, and submit buttons
- Dry-run mode that fills forms without submitting
- Review mode that saves a filled screenshot before submit
- Optional CapSolver support through `CAPSOLVER_API_KEY`
- Local-only logs and screenshots under `.tmp/`

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

On macOS/Linux, activate with:

```bash
source .venv/bin/activate
```

## Configure

Copy `.env.example` to `.env` and add your own sender details:

```bash
WEBSITE_SUBMISSION_SENDER_NAME=
WEBSITE_SUBMISSION_SENDER_EMAIL=
WEBSITE_SUBMISSION_SENDER_PHONE=
CAPSOLVER_API_KEY=
```

`WEBSITE_SUBMISSION_SENDER_NAME` and `WEBSITE_SUBMISSION_SENDER_EMAIL` are
required unless passed with `--name` and `--email`. Phone is optional, but many
business forms require it.

## Run

Dry run from the included sample CSV:

```bash
python -X utf8 execution/plumbing_website_submission_agent.py --batch data/sample-plumbing-companies.csv --limit 3 --dry-run
```

Single-site dry run:

```bash
python -X utf8 execution/plumbing_website_submission_agent.py --url "https://example.com/" --target-company "Example Company" --location "Austin, TX" --niche "home services" --dry-run
```

Review before live submit:

```bash
python -X utf8 execution/plumbing_website_submission_agent.py --batch data/sample-plumbing-companies.csv --limit 3 --review-before-submit
```

Live run:

```bash
python -X utf8 execution/plumbing_website_submission_agent.py --batch data/sample-plumbing-companies.csv --limit 3
```

For production batches and retry runs, see:

- `docs/submission-acceptance-playbook.md`
- `docs/production-batch-runbook.md`

## Input Format

CSV and JSON records can include:

- `name` or `company_name`
- `website`
- `city`
- `state`
- `location`
- `categoryName`
- `categories`
- `niche`
- `phone`
- `email`
- `notes`
- `message` optional override

If `message` is blank, the agent generates a simple partnership-style message
from the company, location, niche, and notes.

## Output

Generated artifacts are intentionally ignored by git:

- `.tmp/plumbing_website_submission_log.json`
- `.tmp/plumbing_website_submission_screenshots/`
- `review-screenshots/`
- `submission-results/`

## Safety Notes

Use dry-run or review mode first. Make sure every live submission has a
legitimate business purpose and complies with the website's terms and applicable
anti-spam laws.

Never complete checkout, purchase, credit-card, subscription, or domain-buying
flows. Mark those pages for manual review instead.
