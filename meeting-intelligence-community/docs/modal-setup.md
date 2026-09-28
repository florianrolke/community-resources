# Modal Setup

Modal is optional. Use it when you want serverless endpoints, schedules, secrets, and volumes.

## What Modal Runs

- Fathom webhook endpoint.
- Scheduled Fathom poller.
- Background job processor.
- Volume-backed storage for jobs, transcripts, summaries, contacts, and processed IDs.

## Commands

```bash
pip install ".[modal]"
modal setup
modal volume create meeting-intelligence-data
modal secret create meeting-intelligence-secrets \
  FATHOM_API_KEY=... \
  GOOGLE_API_KEY=... \
  OPENAI_API_KEY=... \
  NEO4J_URI=... \
  NEO4J_USER=neo4j \
  NEO4J_PASSWORD=...
modal deploy deploy/modal/modal_app.py
```

Neo4j must be reachable from Modal. Neo4j Aura is the simplest option.
