# New Website Submission Campaign Intake

Use this when the user says something like:

> I want this message with this email and this phone number to this list. Please set this up.

## What To Ask For

Ask for only the fields that are missing:

- Campaign/client name
- Lead CSV path or direct-download CSV URL
- Sender name
- Sender email
- Sender phone
- Sender address/city/state/ZIP if forms may require address
- Subject line
- Approved message body
- Whether to start in dry-run/review mode or live mode

Default to dry-run plus review mode unless the user explicitly says live submissions are approved.

## Deterministic Setup Command

```powershell
python -X utf8 execution\setup_website_submission_campaign.py `
  --campaign-name "Client Campaign" `
  --queue-csv data\client-leads.csv `
  --sender-name "Sender Name" `
  --sender-email "sender@example.com" `
  --sender-phone "555-555-5555" `
  --sender-address "123 Main St" `
  --sender-city "Houston" `
  --sender-state "TX" `
  --sender-postal-code "77002" `
  --subject "Partnership inquiry" `
  --message-file .tmp\client-message.txt
```

The script creates a package under:

`.tmp/campaign-setups/<timestamp>-<campaign-slug>/`

Package contents:

- `campaign.json`
- copied queue CSV
- `CAMPAIGN_CONFIG_B64.txt`
- `coolify-env.txt`
- `message.txt`
- `setup-summary.json`
- `README.md`

## Queue Modes

Default `--queue-mode auto`:

- Embeds the queue inside `CAMPAIGN_CONFIG_B64` when the CSV is small enough.
- Uses mounted queue mode when the CSV is large.
- Uses URL mode when `--queue-url` is provided.

For large mounted queues, upload the copied CSV from the package to the path shown in the generated README, usually:

`/data/input/<campaign-slug>-queue.csv`

## Coolify Setup

For a new client service:

1. Create a Coolify service from this repo.
2. Use Docker Compose file `cloud/mobile-home/docker-compose.yml`.
3. Mount persistent storage at `/data`.
4. Add `CAMPAIGN_CONFIG_B64` from the generated `coolify-env.txt`.
5. Keep `CAPSOLVER_API_KEY` as a separate secret/env var.
6. Deploy.
7. Check `/data/state/latest-summary.json` and `/data/runs/` after the first batch.

For an existing generic service, update only `CAMPAIGN_CONFIG_B64`, restart/redeploy, and make sure state/results paths are campaign-specific if campaigns should not share state.

## Live Mode Rule

Do not use `--live` unless the user clearly approved live submissions for that exact message, sender, and list.
