# Charley Website Submission Resume - 2026-06-17

This note preserves the current website form submission state so the campaign
can resume without relying on chat history.

## Restore Package

Short-path backup:

`C:\tmp\charley-website-submission-resume-20260617`

Contents:

- `data/` - 98 Charley/Vincent CSV batch, result, and tracking files
- `logs/` - global submission JSON log plus 51 runner/stdout/stderr logs
- `charley-reached-manifest-20260617.csv` - reached-out rows with contact URLs,
  extracted contact details, calendar links, and screenshot paths

A partial duplicate also exists inside this repo at:

`progress-backups/charley-website-submission-resume-20260617`

Use the `C:\tmp` package as the safer restore source because OneDrive path
length blocked at least one long filename in the in-repo copy.

## Latest Master State

Primary tracking file:

`data/vincent-charley-first-1500-tracking-20260616.csv`

Rows processed: 1,436

Reached out: 443

Not reached: 993

Top statuses:

- confirmed: 276
- submitted_unconfirmed: 167
- failed_validation: 291
- no_contact_page: 313
- captcha_failed: 91
- load_error: 79
- no_form: 76
- mailto_only: 67
- no_fillable_fields: 38

## Retry Batch 1 Final State

Final tracking file:

`data/vincent-charley-retry-backlog-batch-1-final-tracking-20260617.csv`

Rows retried: 100

Reached out after all recovery passes: 26

Not reached after all recovery passes: 74

Top final statuses:

- confirmed: 12
- submitted_unconfirmed: 14
- failed_validation: 34
- no_fillable_fields: 13
- no_form: 12
- mailto_only: 7
- captcha_failed: 6

## Resume Guidance

For fresh unique websites, continue from the source list only if additional
unique Houston plumbing/HVAC websites exist outside the first 1,436 processed
domains.

For retry work, use:

`data/vincent-charley-retry-backlog-batch-1-final-tracking-20260617.csv`

Prioritize remaining `failed_validation`, `no_fillable_fields`, `load_error`,
and selected `captcha_failed` rows only if there is a new strategy. The final
v4 targeted retry added 0 submissions, which means the remaining hard failures
should mostly move to manual review or another channel.

Use the exact Charley Hayden template and sender data already approved in the
agent runbook when resuming.
