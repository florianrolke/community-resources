# Generic Maps Lead Enrichment Runbook

This package discovers local businesses for any industry, enriches contact fields, verifies emails, and exports checkpointed artifacts that can be resumed after failures.

## Flow

1. Create a location grid in `locations.csv`.
2. Define industry search terms and filters in `config/example_industry.json`.
3. Run Maps discovery in small batches.
4. Enrich only rows with websites.
5. Verify only candidate emails that passed syntax and junk filtering.
6. Export send-first, call-first, and review queues in your own CRM format.

## Spend Controls

- Start with `--dry-run`.
- Run one batch first with `--max-batches 1`.
- Keep `--timeout-minutes` low enough that stuck Apify runs are aborted.
- Check `outputs/*/checkpoint.json` before resuming.
- Never delete raw outputs; reparse them if merge logic changes.

