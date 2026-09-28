# Production Batch Runbook

This runbook shows how to run the website submission agent in repeatable,
auditable batches.

## Before Running

Confirm:

- the sender name, email, phone, and address are approved
- the outreach message is approved
- the lead source CSV has a `website` column
- the run has a legitimate business purpose
- `.env` contains optional CAPTCHA solver keys if needed
- Chrome or Chromium is installed for Playwright

Keep generated data out of git. The repo ignores `.tmp`, `data/*` except the
sample CSV, `submission-results`, and review screenshots.

## Single Batch

Dry run:

```powershell
python -X utf8 execution\plumbing_website_submission_agent.py `
  --batch data\sample-plumbing-companies.csv `
  --limit 5 `
  --browser-channel chrome `
  --headless `
  --name "Sender Name" `
  --email "sender@example.com" `
  --phone "555-555-5555" `
  --subject "Partnership inquiry" `
  --dry-run
```

Live run:

```powershell
python -X utf8 execution\plumbing_website_submission_agent.py `
  --batch data\approved-batch.csv `
  --limit 100 `
  --browser-channel chrome `
  --headless `
  --profile-suffix production_batch_1 `
  --name "Sender Name" `
  --email "sender@example.com" `
  --phone "555-555-5555" `
  --sender-address "123 Main St" `
  --sender-city "Houston" `
  --sender-state "Texas" `
  --sender-postal-code "77002" `
  --subject "Partnership inquiry" `
  --delay 3
```

Use a campaign-specific exact-template flag only when the campaign copy has
been approved and locked.

## Update Tracking CSV

After a run, merge result statuses back to the source file:

```powershell
python -X utf8 execution\update_outreach_tracking_csv.py `
  --source-csv data\approved-batch.csv `
  --results-csv data\approved-batch-results.csv `
  --output-csv data\approved-batch-tracking.csv
```

The tracking output adds:

- `outreach_status`
- `reached_out`
- `needs_retry`
- `retry_reason`
- `last_contact_url`
- `last_submission_timestamp`
- `last_screenshot_before`
- `last_screenshot_after`
- `extracted_emails`
- `extracted_phones`
- `extracted_notes`
- `calendar_links`

## Continuous Fresh Batches

Use the continuous runner when you have a larger source CSV and want to process
unique website domains in 100-row batches.

```powershell
python -X utf8 execution\run_charley_overnight_batches.py `
  --source-csv data\approved-source.csv `
  --run-name campaign-name `
  --date-tag 20260617 `
  --start-batch 1 `
  --end-batch 20 `
  --name "Sender Name" `
  --email "sender@example.com" `
  --phone "555-555-5555" `
  --sender-address "123 Main St" `
  --sender-city "Houston" `
  --sender-state "Texas" `
  --sender-postal-code "77002" `
  --subject "Partnership inquiry" `
  --delay 3
```

What it does:

- creates the next 100-domain batch
- skips domains already included in prior combined batches
- runs the submission agent
- exports result CSVs
- copies successful screenshots into separate folders
- writes batch tracking CSVs
- builds combined first-N tracking files
- writes evaluation checkpoints every two batches
- resumes missing rows if the watched batch exits early

## Retry Backlog

Use retry backlog after the first pass has produced a tracking CSV.

```powershell
python -X utf8 execution\run_charley_retry_backlog.py `
  --tracking-csv data\campaign-first-1500-tracking.csv `
  --run-name campaign-retry-backlog `
  --batch-size 100 `
  --max-batches 6 `
  --name "Sender Name" `
  --email "sender@example.com" `
  --phone "555-555-5555" `
  --sender-address "123 Main St" `
  --sender-city "Houston" `
  --sender-state "Texas" `
  --sender-postal-code "77002" `
  --subject "Partnership inquiry" `
  --delay 3
```

Retry order:

1. `missing_required`
2. `no_fillable_fields`
3. `failed_validation`
4. `load_error`
5. `captcha_failed`

This order tends to recover the most submissions per unit of time and CAPTCHA
spend.

## Review Results

After each batch, check:

- confirmed count
- submitted-unconfirmed count
- failed-validation count
- CAPTCHA failures
- contact details extracted from non-form pages
- screenshots for the confirmed folder
- tracking CSV rows marked `needs_retry`

Treat `submitted_unconfirmed` as reached out for campaign accounting, but keep
it separate from `confirmed` because the page did not provide reliable success
text.

## When To Stop Automatically

Stop or switch to manual review when most remaining rows are:

- `no_contact_page`
- `no_form`
- `mailto_only`
- `checkout_or_payment_page`
- repeated `captcha_failed`
- repeated `failed_validation` after broad prefill, typed email/phone fallback,
  dropdown placeholder filtering, and three validation-repair attempts

Those rows usually need another channel, a new lead source, or a human decision
rather than more blind retries.

For the June 17 plumbing/HVAC retry test, the useful automatic recovery ended
after the third focused retry pass: the first recovery passes lifted a hard
100-row retry batch from 11 reached out to 26, while a final 20-row targeted
retry produced 0 additional submissions. Treat that pattern as the signal to
move remaining rows into manual review or another outreach channel.
