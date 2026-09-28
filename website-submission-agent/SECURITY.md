# Security

## Secrets

Do not commit `.env`, browser profiles, screenshots, logs, or live lead data.
The repository intentionally ships only `.env.example` with empty placeholders.

The agent reads environment variables from `website-submission-agent/.env` only:

- `WEBSITE_SUBMISSION_SENDER_NAME`
- `WEBSITE_SUBMISSION_SENDER_EMAIL`
- `WEBSITE_SUBMISSION_SENDER_PHONE`
- `CAPSOLVER_API_KEY` optional

Sender name and email are required at runtime and can also be passed with
`--name` and `--email`.

## Responsible Use

Use dry-run or review mode before live submissions. Only submit forms where you
have a legitimate business reason to contact the company, and respect website
terms, anti-spam rules, and local laws.
