# Reusable Website Form Submission Agent Setup

This is the reusable setup path for new client website form-submission campaigns.
It avoids manually creating a long list of Coolify environment variables for each client.

## One-Config Model

The worker still supports the old env variables, but new campaigns should use one of these config inputs:

1. Preferred for long-running jobs: mount a JSON file at `/data/config/campaign.json`.
2. Preferred for quick setup: set one Coolify env var, `CAMPAIGN_CONFIG_B64`, generated from a campaign JSON file.
3. Preferred when the queue/config lives in Drive or another controlled host: set `CAMPAIGN_CONFIG_URL` to a direct JSON URL.

The campaign JSON can define:

- campaign name and run ID prefix
- queue source path, direct URL, base64 CSV, or text CSV
- sender name, email, phone, and fallback address
- subject and approved message
- exact template flag, or `none` for a generic approved message
- batch size, loop mode, delays, dry-run/review flags
- result/state/summary paths
- optional status server settings

Examples:

- `cloud/mobile-home/config-examples/generic-client-campaign.json`
- `cloud/mobile-home/config-examples/mobile-home-campaign.json`

## Encode A Config For Coolify

From the repo root:

```powershell
python cloud/mobile-home/encode_campaign_config.py cloud/mobile-home/config-examples/generic-client-campaign.json
```

Paste the printed value into Coolify as:

```text
CAMPAIGN_CONFIG_B64=<printed value>
```

For better secret hygiene, keep `CAPSOLVER_API_KEY` as a separate Coolify secret/env var. The worker also supports `capsolver_api_key` inside the JSON when a truly single-value setup is preferred.

## Minimal Coolify Setup For A New Client

1. Create a new Coolify service from the same GitHub repo.
2. Use Docker Compose mode with `cloud/mobile-home/docker-compose.yml`.
3. Add persistent storage mounted at `/data`.
4. Set either `CAMPAIGN_CONFIG_B64`, `CAMPAIGN_CONFIG_URL`, or upload `/data/config/campaign.json`.
5. Provide the lead queue with either:
   - `/data/input/<client-queue>.csv`
   - `queue.url` in the campaign config
   - `queue_csv_b64` or `queue_csv_text` in the campaign config
6. Start with `dry_run: true` and `review_before_submit: true` in the config.
7. After screenshots/results look clean, set those two flags to false and redeploy/restart.

## Observability

Every loop still prints JSON logs, including `aggregate_summary`, but the worker now also writes these persistent files:

- `/data/state/latest-summary.json`
- `/data/state/latest-worker-status.json`
- `/data/state/worker-events.jsonl`

`latest-summary.json` contains:

- total result rows
- likely successful submissions
- success rate
- status counts
- rows with screenshots
- rows with contact details
- latest run directory

If the optional status server is enabled in the campaign config, it serves:

- `/health`
- `/summary`
- `/status`
- `/events`

Only expose the status server publicly when `status.auth_token` is set and Coolify routing is intentionally configured.

## Template Options

Use a locked template flag only when the campaign has one built into the agent:

- `--exact-mobile-home-template`
- `--exact-charley-hayden-template`

For a new client without a hardcoded template, use:

```json
"template_flag": "none",
"message": "Approved outreach message here"
```

The message should be approved before live submission.

## Fast Intake Helper

For the dream workflow - "this message, this sender, this phone, this list" - use:

`execution/setup_website_submission_campaign.py`

It creates a complete package under `.tmp/campaign-setups/` with `campaign.json`, `CAMPAIGN_CONFIG_B64.txt`, `coolify-env.txt`, the copied queue CSV, and a setup README. See:

`docs/new-website-submission-campaign-intake.md`
