# Mobile Home Cloud Submission Agent

This folder packages the existing website submission agent for cloud execution
on Modal. It reuses:

- `website-submission-agent/execution/plumbing_website_submission_agent.py`
- `--exact-mobile-home-template`
- Playwright Chromium in headless mode
- CapSolver via environment secret
- persistent result storage via Modal Volume

## Why This Exists

The local mobile-home process worked, but it requires the operator's machine to stay
open. This Modal wrapper lets the same process run from the cloud on demand from
n8n, Make, curl, or a scheduled Modal function.

## Current Mobile Home Inputs

Primary source queue:

`website-submission-agent/data/mobile-home-strict-form-submission-queue.csv`

Latest local restore note:

`website-submission-agent/docs/mobile-home-progress-restore-20260613.md`

Latest learnings:

`website-submission-agent/docs/mobile-home-icp-retry-learnings-20260613.md`

## Sender / Template

The cloud runner accepts sender values from the POST payload or Modal secret env
vars:

- `MOBILE_HOME_SENDER_NAME`
- `MOBILE_HOME_SENDER_EMAIL`
- `MOBILE_HOME_SENDER_PHONE`
- Address fallback: `1455 Clearview Drive, McKinney, TX 75072`
- Subject: `Michigan mobile home case study`
- Template flag: `--exact-mobile-home-template`

Exact message rule:

```text
Hello [name],

We just finished a case study about a client in Michigan, a pre-owned manufactured home dealer and reseller. 

So I wanted to greet you. 

They had a record February with us and the best March since 2014 - I can send you their case study if you'd like.

Blessings,  
[Sender]
```

Only `[name]` changes when an owner/contact first name is available.

## Modal Setup

Install/login locally if needed:

```powershell
pip install modal
modal setup
```

Create the Modal secret:

```powershell
modal secret create mobile-home-submission-agent-secrets `
  CAPSOLVER_API_KEY=... `
  MOBILE_HOME_AGENT_AUTH_TOKEN=... `
  MOBILE_HOME_SENDER_NAME=... `
  MOBILE_HOME_SENDER_EMAIL=... `
  MOBILE_HOME_SENDER_PHONE=...
```

The auth token is your private bearer token for calling the endpoint. It can be
any strong random string.

Deploy:

```powershell
modal deploy website-submission-agent/cloud/mobile-home/modal_mobile_home_submission_agent.py
```

## Run A Batch

Example POST body:

```json
{
  "source_csv": "data/mobile-home-strict-form-submission-queue.csv",
  "limit": 25,
  "offset": 0,
  "name": "Sender Name",
  "email": "sender@example.com",
  "phone": "555 555 5555",
  "dry_run": false,
  "review_before_submit": false,
  "delay": 3
}
```

Headers:

```text
Authorization: Bearer YOUR_MOBILE_HOME_AGENT_AUTH_TOKEN
Content-Type: application/json
```

The endpoint response returns:

- `run_id`
- `input_count`
- `logged_count`
- `status_counts`
- `volume_run_dir`
- `result_csv`

Outputs are stored in the Modal volume:

`mobile-home-submission-runs`

Each run stores:

- `input.csv`
- `results.csv`
- `stdout.log`
- `stderr.log`
- `plumbing_website_submission_log.json`
- `screenshots/`

## Resume / Avoid Duplicates

Use `offset` for simple sequential batches, or pass `skip_domains` for precise
dedupe:

```json
{
  "source_csv": "data/mobile-home-strict-form-submission-queue.csv",
  "limit": 100,
  "offset": 100,
  "skip_domains": ["example.com", "already-submitted.com"]
}
```

For production, keep a Google Sheet or CSV with:

- domain
- attempted_at
- status
- result_csv
- screenshot path
- contact details
- calendar links

Then pass already-attempted domains into `skip_domains`.

## Important Guardrails

- Do not run this against factory sellers or domain-sale/checkout pages.
- Keep screenshots/results for proof.
- Use dry-run or `review_before_submit` for a small test batch after deployment.
- The cloud runner uses Chromium, not local Chrome.
- Public lead scraping and form submission should remain separate stages:
  first build/clean the queue, then submit.

## Coolify / Hostinger Overnight Worker

If Modal deploy is blocked from the local agent environment, use the Docker
worker in this folder. This is often the simplest overnight setup because
Coolify owns the runtime and the local machine can sleep.

Files:

- `cloud/mobile-home/Dockerfile`
- `cloud/mobile-home/docker-compose.yml`
- `cloud/mobile-home/run_cloud_worker.py`

### Coolify Setup

1. Create a new Coolify project from the GitHub repo:

   `https://github.com/Florian1995-ai/website-submission-agent`

2. Use Docker Compose mode and point to:

   `cloud/mobile-home/docker-compose.yml`

3. Add persistent storage mounted at:

   `/data`

4. Provide the queue CSV in one of three ways:

   - upload it into persistent storage at `/data/input/mobile-home-strict-form-submission-queue.csv`
   - set `QUEUE_CSV_B64` to a base64-encoded CSV
   - set `QUEUE_CSV_URL` to a direct-download CSV URL

   The mounted file is best for long overnight runs. `QUEUE_CSV_B64` is easiest
   for a one-row cloud smoke test.

5. Add environment variables in Coolify:

```text
RUN_MODE=loop
BATCH_LIMIT=25
LOOP_SLEEP_SECONDS=300
SOURCE_CSV=/data/input/mobile-home-strict-form-submission-queue.csv
QUEUE_CSV_B64=
QUEUE_CSV_URL=
RESULTS_ROOT=/data/runs
STATE_FILE=/data/state/mobile-home-worker-state.json
SENDER_NAME=...
SENDER_EMAIL=...
SENDER_PHONE=...
SENDER_ADDRESS=1455 Clearview Drive
SENDER_CITY=McKinney
SENDER_STATE=TX
SENDER_POSTAL_CODE=75072
SUBJECT=Michigan mobile home case study
CAPSOLVER_API_KEY=...
DRY_RUN=true
REVIEW_BEFORE_SUBMIT=true
```

6. First deploy/test with:

```text
BATCH_LIMIT=1
DRY_RUN=true
REVIEW_BEFORE_SUBMIT=true
```

7. After the first screenshot/result appears under `/data/runs`, switch to:

```text
BATCH_LIMIT=25
DRY_RUN=false
REVIEW_BEFORE_SUBMIT=false
RUN_MODE=loop
```

### Worker Behavior

Each loop:

- reads the queue CSV
- skips domains already in `/data/state/mobile-home-worker-state.json`
- writes the current batch to `/data/runs/<run_id>/input.csv`
- runs the Playwright form-submission agent headlessly
- writes `/data/runs/<run_id>/results.csv`
- copies screenshots/logs into `/data/runs/<run_id>/`
- updates state so the next loop continues where it left off

## Reusable Single-Config Coolify Setup

For new client campaigns, the Docker worker no longer needs a long manual env-var setup. Use one campaign JSON file instead:

- Example config: `cloud/mobile-home/config-examples/generic-client-campaign.json`
- Encode helper: `python cloud/mobile-home/encode_campaign_config.py <campaign.json>`
- Coolify env: set `CAMPAIGN_CONFIG_B64` to the printed value, or mount the JSON at `/data/config/campaign.json`

The worker still supports the original env variables for the current mobile-home service. It now also writes persistent observability files under `/data/state/`:

- `latest-summary.json`
- `latest-worker-status.json`
- `worker-events.jsonl`

See `docs/reusable-website-form-submission-agent-setup.md` for the full reusable setup flow.
