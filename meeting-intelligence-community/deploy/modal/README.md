# Modal Deployment

Modal is optional. The default package is Docker/Coolify self-hosted.

## Modal Use Cases

- Public webhook endpoint that accepts Fathom payloads.
- Scheduled Fathom poller every 15 minutes.
- Background job processor.
- Modal Volume for contacts, config, transcripts, summaries, and processed IDs.
- Modal Secrets for Fathom, Google, OpenAI/Gemini, and Neo4j credentials.

## Setup

```bash
pip install modal
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

On Windows, if the Modal CLI prints a `charmap` encoding error, run:

```powershell
$env:PYTHONIOENCODING='utf-8'; modal deploy deploy/modal/modal_app.py
```

The Modal profile expects Neo4j to be reachable from Modal. Use Neo4j Aura or expose a secured self-hosted Neo4j endpoint.
