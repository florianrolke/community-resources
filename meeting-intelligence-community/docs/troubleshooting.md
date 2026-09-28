# Troubleshooting

## Google OAuth Invalid Grant

- Regenerate the token with `scripts/auth_google.py`.
- Make sure your OAuth consent screen includes your Google account as a test user.
- Confirm the correct scopes were used for the target token.

## Google Scope Errors

- Docs creation needs Docs + Drive scopes.
- Gmail drafts need Gmail compose scope.
- Calendar lookup needs Calendar readonly scope.

## Fathom Missing Transcripts

- Confirm webhook event includes transcript data.
- Use the poller as backup with `FATHOM_API_KEY`.
- Check `data/jobs` for queued payloads and `data/summaries` for outputs.

## Duplicate Meetings

The system tracks processed IDs in:

```text
data/state/processed_meetings.json
```

Delete an ID from that file only if you intentionally want to reprocess a meeting.

## Neo4j Connection Errors

- Confirm Neo4j is healthy: `docker compose -f deploy/docker-compose.yml ps`.
- Confirm `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`.
- Run `python scripts/init_neo4j.py`.

## Vector Search Returns Weak Results

- Use real OpenAI embeddings for production.
- The deterministic fallback is only for local tests and demos.
- Increase chunk size if context is too fragmented.

## Modal Windows UTF-8 Error

Use:

```powershell
$env:PYTHONIOENCODING='utf-8'; modal deploy deploy/modal/modal_app.py
```
