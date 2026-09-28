# Outreach Campaign Start Readiness - 2026-06-20

This note is the short control panel for future chats. Work from:

`C:\Users\flori\OneDrive\Dokumente\Agentic Workflows\Agentic Workflows-Nick Saraev\Heros Arc PROJECTS\website-submission-agent`

Do not clean up the Charley/Vincent files or mobile-home files. Both campaigns are active in this repo.

## Mobile Homes

Production cloud target:

- Coolify service: `mobile-home-submission-agent`
- UUID: `hx2lzotl6i8khhbwhvin83cm`
- Server: `Hostinger New / 2.24.108.202`
- Status seen on 2026-06-20: `running:unknown:excluded`
- Old service to ignore: `OLD-DO-NOT-USE-mobile-home-submission-agent`
- GitHub `main` on 2026-06-20: `809b7a36028aa10c4a98349860638102db14f58b`
- Latest commit purpose: `Log aggregate cloud submission results`

Cloud worker:

`cloud/mobile-home/run_cloud_worker.py`

Expected Coolify env keys are present:

- `SOURCE_CSV`
- `QUEUE_CSV_URL`
- `CAPSOLVER_API_KEY`
- `SENDER_NAME`
- `SENDER_EMAIL`
- `SENDER_PHONE`
- `RUN_MODE`
- `BATCH_LIMIT`
- `LOOP_SLEEP_SECONDS`
- `RESULTS_ROOT`
- `STATE_FILE`
- `REVIEW_BEFORE_SUBMIT`

Coolify masks env values through the API, so do not claim values are verified from API output unless checked in the UI or from runtime logs.

Persistent storage is mounted at `/data`. The worker writes:

- `/data/runs/<run_id>/input.csv`
- `/data/runs/<run_id>/results.csv`
- `/data/runs/<run_id>/stdout.log`
- `/data/runs/<run_id>/stderr.log`
- `/data/runs/<run_id>/screenshots/`
- `/data/state/mobile-home-worker-state.json` or the configured state file

The local source queue is:

`data/mobile-home-strict-form-submission-queue.csv`

Current local queue count:

- 10,909 rows
- 7,243 unique domains

When the user says "start mobile homes":

1. Check `git status --short` and confirm deployment-critical files are committed/pushed.
2. Check Coolify service status through `/api/v1/services/hx2lzotl6i8khhbwhvin83cm`.
3. If code changed, deploy/restart the Coolify service.
4. If code did not change and service is already running, leave it running and monitor logs.
5. Watch Coolify Logs for `"event": "aggregate_summary"`.
6. Report `total_result_rows`, `likely_successful_submissions`, `likely_success_rate_percent`, `status_counts`, `rows_with_after_screenshot`, `rows_with_contact_details`, and `last_run_dir`.

Known limitation:

- Coolify public API exposes service status/env/storage, but no documented service container log endpoint. Use the Coolify Logs UI for `aggregate_summary`, or add a deliberate inspection mechanism before relying on API-only log collection.

## Charley / Vincent

Primary historical tracking file:

`data/vincent-charley-first-1500-tracking-20260616.csv`

Historical baseline:

- 1,436 processed domains
- 443 reached out
- 276 confirmed
- 167 submitted unconfirmed

Latest retry-backlog final tracking:

`data/vincent-charley-retry-backlog-batch-1-final-tracking-20260617.csv`

Retry-backlog outcome:

- 100 retried
- 26 reached out after recovery passes
- Final targeted retry produced no new submissions, so do not blindly rerun this without a new strategy.

Best immediate fresh queue:

`data/charley-houston-final-additional-drive-plus-existing-queue-20260617.csv`

Current count:

- 28 rows
- 28 unique domains

Other staged Charley queues:

- `data/charley-houston-additional-strict-queue-20260617.csv` - 29 unique domains
- `data/charley-houston-additional-high-confidence-queue-20260617.csv` - 38 unique domains
- `data/charley-download-drive-export-strict-new-queue-20260617.csv` - 28 unique domains

Canonical Charley sender/template:

- Name: `Charley Hayden`
- Email: `you@example.com`
- Phone: `346-385-3496`
- Address: `2429 Park Ave, Pearland, Texas, 77581`
- Subject: `Mitigation partnership inquiry`
- Required flag: `--exact-charley-hayden-template`

When the user says "start Charley":

1. Ask only if the intended mode is ambiguous:
   - fresh additional Houston queue
   - retry backlog with a new strategy
   - export/report/manual-review work
2. For the immediate fresh queue, run the main agent against the 28-row final queue.
3. For larger fresh sources, use `execution/run_charley_overnight_batches.py`.
4. For retries, use `execution/run_charley_retry_backlog.py`, but only after naming the new retry strategy.

Immediate fresh-queue command shape:

```powershell
python -X utf8 execution\plumbing_website_submission_agent.py `
  --batch data\charley-houston-final-additional-drive-plus-existing-queue-20260617.csv `
  --limit 28 `
  --browser-channel chrome `
  --headless `
  --profile-suffix charley_additional_20260620 `
  --name "Charley Hayden" `
  --email "you@example.com" `
  --phone "346-385-3496" `
  --sender-address "2429 Park Ave" `
  --sender-city "Pearland" `
  --sender-state "Texas" `
  --sender-postal-code "77581" `
  --subject "Mitigation partnership inquiry" `
  --exact-charley-hayden-template `
  --delay 3
```

Larger fresh-batch runner shape:

```powershell
python -X utf8 execution\run_charley_overnight_batches.py `
  --source-csv data\<approved-source>.csv `
  --run-name vincent-charley-next `
  --date-tag 20260620 `
  --start-batch 1 `
  --end-batch 1 `
  --name "Charley Hayden" `
  --email "you@example.com" `
  --phone "346-385-3496" `
  --sender-address "2429 Park Ave" `
  --sender-city "Pearland" `
  --sender-state "Texas" `
  --sender-postal-code "77581" `
  --subject "Mitigation partnership inquiry" `
  --exact-charley-hayden-template `
  --delay 3
```

Retry-backlog runner shape:

```powershell
python -X utf8 execution\run_charley_retry_backlog.py `
  --tracking-csv data\vincent-charley-retry-backlog-batch-1-final-tracking-20260617.csv `
  --run-name vincent-charley-retry-backlog-next-strategy `
  --batch-size 100 `
  --max-batches 1 `
  --name "Charley Hayden" `
  --email "you@example.com" `
  --phone "346-385-3496" `
  --sender-address "2429 Park Ave" `
  --sender-city "Pearland" `
  --sender-state "Texas" `
  --sender-postal-code "77581" `
  --subject "Mitigation partnership inquiry" `
  --exact-charley-hayden-template `
  --delay 3
```

## Verified On 2026-06-20

These scripts compile without syntax errors:

- `cloud/mobile-home/run_cloud_worker.py`
- `execution/plumbing_website_submission_agent.py`
- `execution/run_charley_overnight_batches.py`
- `execution/run_charley_retry_backlog.py`
- `execution/run_exact_charley_batch.py`

These important flags exist:

- `--exact-mobile-home-template`
- `--exact-charley-hayden-template`
- `--headless`
- `--profile-suffix`
- `--stop-after-successes`

The agent reads either `CAPSOLVER_API_KEY` or `Capsolver_API_KEY`.

## Reusable New-Client Setup Added - 2026-06-20

The Coolify worker now supports one-file campaign config for future clients:

- `CAMPAIGN_CONFIG_PATH=/data/config/campaign.json`
- `CAMPAIGN_CONFIG_JSON`
- `CAMPAIGN_CONFIG_B64`
- `CAMPAIGN_CONFIG_URL`

Use `cloud/mobile-home/config-examples/generic-client-campaign.json` as the starter config and encode it with:

```powershell
python cloud/mobile-home/encode_campaign_config.py cloud/mobile-home/config-examples/generic-client-campaign.json
```

The worker also persists summary/status outside Coolify logs:

- `/data/state/latest-summary.json`
- `/data/state/latest-worker-status.json`
- `/data/state/worker-events.jsonl`

Optional status HTTP server endpoints are available when enabled:

- `/health`
- `/summary`
- `/status`
- `/events`

Only expose those endpoints publicly with an auth token.
