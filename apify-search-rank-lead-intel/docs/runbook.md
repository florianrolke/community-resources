# Search Rank Lead Intelligence Runbook

Use this package when the value is not just "find businesses," but "which companies rank for which searches in which locations."

## Flow

1. Configure search terms and include/exclude logic.
2. Build a city/county/state location grid.
3. Run one checkpointed Apify Maps ranking batch.
4. Inspect parsed ranks and confidence flags.
5. Roll up companies by `place_id`.
6. Enrich accepted rows with website/contact/email verification tooling.

## Spend Controls

- Use `--dry-run`.
- Run `--max-batches 1` before overnight.
- Keep `max_results_per_query` low until quality is proven.
- Preserve raw JSON for recovery and reparse.
- Never pay for enrichment on `reject` rows.

