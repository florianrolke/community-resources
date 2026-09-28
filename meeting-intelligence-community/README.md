# Meeting Intelligence Community

Self-hosted meeting transcript intelligence for Fathom users.

This package receives Fathom meeting transcripts, creates structured summaries, optionally creates Google Docs and Gmail drafts, stores transcript artifacts, and vectorizes the transcript history into Neo4j so you can search and query meeting memory over time.

It is built as a community-ready template: no private contacts, no private prompts, no tokens, and no transcript data are included.

## What It Does

```text
Fathom meeting ends
        |
        v
FastAPI webhook returns 202 immediately
        |
        v
Worker resolves participant + formats transcript
        |
        v
LLM creates structured meeting summary
        |
        +--> optional Google Doc
        +--> optional Gmail draft
        +--> local transcript + summary artifacts
        |
        v
Neo4j graph + vector indexes
        |
        v
Semantic search, person history, topic recall, action item recall
```

## Accounts and APIs

Required:

| Service | Purpose |
| --- | --- |
| Fathom | Meeting transcripts and webhook/poller source |
| Neo4j | Graph database and vector search |
| OpenAI or Gemini | Summary generation; OpenAI also provides default embeddings |

Optional:

| Service | Purpose |
| --- | --- |
| Google Docs API | Create meeting summary documents |
| Google Drive API | Move/share meeting docs |
| Gmail API | Create draft emails with doc links |
| Google Calendar API | Resolve calendar context and future Calendar-to-Zoom sync |
| Modal | Optional serverless deployment profile |

## Quick Start With Docker Compose

1. Clone or copy this repo.

2. Create your env file:

```bash
cp .env.example .env
```

3. Copy example config files:

```bash
mkdir -p data/config
cp examples/contacts.example.json data/config/contacts.json
cp examples/email_style_policy.example.json data/config/email_style_policy.json
cp examples/google_doc_config.example.json data/config/google_doc_config.json
```

4. Edit `.env`.

Minimum local test:

```env
HOST_NAME=Your Name
HOST_EMAIL=you@example.com
LLM_PROVIDER=fallback
GOOGLE_DOCS_ENABLED=false
GMAIL_DRAFTS_ENABLED=false
NEO4J_ENABLED=true
EMBEDDING_PROVIDER=local
NEO4J_PASSWORD=meeting-intelligence-password
```

Production summary + vectorization:

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
EMBEDDING_PROVIDER=openai
```

5. Start the stack:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

6. Initialize Neo4j indexes:

```bash
docker compose -f deploy/docker-compose.yml exec api python scripts/init_neo4j.py
```

7. Send the sample Fathom payload:

```bash
curl -X POST http://localhost:8080/webhook/fathom \
  -H "Content-Type: application/json" \
  --data-binary @examples/sample_fathom_payload.json
```

8. Confirm output:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/meetings/sample-001
curl "http://localhost:8080/search?q=outreach%20copy"
```

Neo4j Browser:

```text
http://localhost:7474
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `APP_NAME` | No | Display name for the app. |
| `HOST_NAME` | Yes | Your name for email signoff and host filtering. |
| `HOST_EMAIL` | Yes | Your email; used to avoid treating you as the participant. |
| `PUBLIC_BASE_URL` | No | Public API URL used when Google Docs are disabled. |
| `DATA_DIR` | No | Local artifact directory. Default: `data`. |
| `FATHOM_API_KEY` | Poller | Fathom API key for scheduled polling. |
| `FATHOM_WEBHOOK_SECRET` | Webhook signing | Optional webhook signing secret. |
| `FATHOM_POLL_MINUTES` | No | Poll interval. Default: `15`. |
| `LLM_PROVIDER` | No | `gemini`, `openai`, or `fallback`. |
| `GOOGLE_API_KEY` | Gemini | Gemini API key for summaries. |
| `GEMINI_SUMMARY_MODEL` | No | Gemini model. Default: `gemini-1.5-flash`. |
| `OPENAI_API_KEY` | OpenAI/embeddings | OpenAI key for summaries or embeddings. |
| `OPENAI_SUMMARY_MODEL` | No | OpenAI summary model. Default: `gpt-4o-mini`. |
| `GOOGLE_DOCS_ENABLED` | No | `true` to create Google Docs. |
| `GMAIL_DRAFTS_ENABLED` | No | `true` to create Gmail drafts. |
| `GOOGLE_CALENDAR_ENABLED` | No | Reserved for Calendar title resolution/sync. |
| `GOOGLE_DOCS_TOKEN_JSON` | Docs | OAuth token JSON for Docs/Drive. |
| `GOOGLE_GMAIL_TOKEN_JSON` | Gmail | OAuth token JSON for Gmail compose. |
| `GOOGLE_CALENDAR_TOKEN_JSON` | Calendar | OAuth token JSON for Calendar readonly. |
| `GOOGLE_DOCS_TEMPLATE_ID` | No | Optional Google Doc template ID. |
| `GOOGLE_DRIVE_FOLDER_ID` | No | Optional Drive folder for created docs. |
| `NEO4J_ENABLED` | No | `true` to vectorize into Neo4j. |
| `NEO4J_URI` | Neo4j | Bolt URI. Docker default: `bolt://neo4j:7687`. |
| `NEO4J_USER` | Neo4j | Neo4j username. |
| `NEO4J_PASSWORD` | Neo4j | Neo4j password. |
| `EMBEDDING_PROVIDER` | No | `openai` for production, `local` for tests. |
| `EMBEDDING_MODEL` | No | Default: `text-embedding-3-small`. |
| `EMBEDDING_DIMENSION` | No | Default: `1536`. |
| `CHUNK_WORDS` | No | Transcript chunk size. Default: `420`. |
| `CHUNK_OVERLAP_WORDS` | No | Chunk overlap. Default: `60`. |
| `CONTACTS_PATH` | No | Contacts JSON path. |
| `STYLE_POLICY_PATH` | No | Email style policy path. |
| `NEXT_MEETING_DAYS` | No | Default next meeting offset. |

## Fathom Setup

Webhook path:

1. Deploy the API publicly.
2. In Fathom, create a webhook pointing to:

```text
https://your-domain.com/webhook/fathom
```

3. Select the transcript/recording-completed event that includes transcript data.
4. Add a signing secret if available and set `FATHOM_WEBHOOK_SECRET`.

Poller path:

1. Set `FATHOM_API_KEY`.
2. Keep the scheduler service running.
3. The scheduler checks for new transcript-bearing meetings every 15 minutes.

The webhook path is real time. The poller is a backup.

## Google Integration Setup

Google features are optional. You can run the whole summary + Neo4j workflow without them.

### 1. Create or Select a Google Cloud Project

Open Google Cloud Console, create a project, or choose an existing one.

### 2. Enable APIs

Enable:

- Google Docs API
- Google Drive API
- Gmail API
- Google Calendar API, only if you want Calendar features

### 3. Configure OAuth Consent

1. Go to APIs & Services > OAuth consent screen.
2. Choose External or Internal.
3. Add your email as a test user while the app is in testing mode.
4. Save.

### 4. Create OAuth Credentials

1. Go to APIs & Services > Credentials.
2. Create OAuth client ID.
3. Choose Desktop app.
4. Download the JSON as `credentials/google_oauth_client.json`.

### 5. Generate Token JSON

Install locally:

```bash
pip install -r requirements.txt
```

Generate tokens:

```bash
python scripts/auth_google.py --client-secret credentials/google_oauth_client.json --target docs --output token_docs.json
python scripts/auth_google.py --client-secret credentials/google_oauth_client.json --target gmail --output token_gmail.json
python scripts/auth_google.py --client-secret credentials/google_oauth_client.json --target calendar --output token_calendar.json
```

Paste each token JSON into `.env` as a single-line value:

```env
GOOGLE_DOCS_ENABLED=true
GOOGLE_DOCS_TOKEN_JSON={"token":"...","refresh_token":"..."}

GMAIL_DRAFTS_ENABLED=true
GOOGLE_GMAIL_TOKEN_JSON={"token":"...","refresh_token":"..."}

GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_TOKEN_JSON={"token":"...","refresh_token":"..."}
```

### Required Scopes

- Docs/Drive: `documents`, `drive`
- Gmail: `gmail.compose`
- Calendar: `calendar.readonly`

The Gmail scope creates drafts only. It does not send emails.

### Google Doc Template

Set:

```env
GOOGLE_DOCS_TEMPLATE_ID=your-template-id
GOOGLE_DRIVE_FOLDER_ID=optional-folder-id
```

The template ID is the string between `/d/` and `/edit` in the Google Doc URL.

The default integration creates a plain Google Doc if no template is configured. It tries to set anyone-with-link commenter permissions. Workspace policies may block public sharing; document creation can still succeed.

## Neo4j Setup

Docker Compose starts Neo4j automatically.

Run:

```bash
docker compose -f deploy/docker-compose.yml exec api python scripts/init_neo4j.py
```

Verification in Neo4j Browser:

```cypher
MATCH (n) RETURN labels(n), count(n);
SHOW VECTOR INDEXES;
MATCH (m:Meeting)-[:HAS_CHUNK]->(c:TranscriptChunk)
RETURN m.title, c.chunk_index, left(c.text, 120)
LIMIT 5;
```

External Neo4j or Aura:

```env
NEO4J_URI=neo4j+s://your-aura-host.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

## Deployment Options

### Docker/Coolify

Recommended for self-hosting.

1. Push this package to GitHub.
2. Create a Coolify Docker Compose app.
3. Use `deploy/docker-compose.yml`.
4. Add `.env` values in Coolify.
5. Point your domain to the API service on port `8080`.

### Modal

Optional serverless route.

```bash
pip install ".[modal]"
modal setup
modal volume create meeting-intelligence-data
modal secret create meeting-intelligence-secrets FATHOM_API_KEY=... OPENAI_API_KEY=... NEO4J_URI=...
modal deploy deploy/modal/modal_app.py
```

On Windows:

```powershell
$env:PYTHONIOENCODING='utf-8'; modal deploy deploy/modal/modal_app.py
```

Modal is useful for:

- Webhook endpoint
- Background processing
- 15-minute Fathom poller
- Secrets
- Volumes
- Manual logs and health checks

Neo4j must be reachable from Modal, usually via Neo4j Aura or a secured public Neo4j endpoint.

## Testing

Unit tests:

```bash
pip install -e ".[dev]"
pytest
```

Manual smoke test:

```bash
docker compose -f deploy/docker-compose.yml up --build
curl -X POST http://localhost:8080/webhook/fathom \
  -H "Content-Type: application/json" \
  --data-binary @examples/sample_fathom_payload.json
curl http://localhost:8080/meetings/sample-001
curl "http://localhost:8080/search?q=onboarding%20checklist"
```

Expected artifacts:

- `data/jobs` briefly contains the queued job.
- `data/processed` contains the processed raw payload.
- `data/transcripts/sample-001.txt` contains readable transcript text.
- `data/summaries/sample-001.json` contains summary, doc info, email draft info, and transcript.
- Neo4j contains `Meeting`, `Person`, and `TranscriptChunk` nodes.

## Troubleshooting

### Google OAuth invalid grant

Regenerate token JSON with `scripts/auth_google.py`, confirm your user is on the OAuth test-user list, and confirm scopes match the target.

### Fathom missing transcripts

Use the Fathom poller backup and confirm the selected webhook event includes transcript data.

### Impromptu Zoom names

The package includes participant resolution from invitees, matched speakers, transcript speakers, and contacts. Calendar-to-Zoom sync is provided as an extension point and Modal use case.

### Neo4j connection/index errors

Confirm Neo4j is healthy, credentials match `.env`, and run `scripts/init_neo4j.py`.

### Duplicate processing

Processed source IDs are stored in:

```text
data/state/processed_meetings.json
```

Remove an ID only when intentionally reprocessing.

### Weak vector search

Use OpenAI embeddings for production. The local deterministic embedding fallback is only for tests.

## Privacy and Security

- Never commit `.env`, token JSON files, contact files, or transcript data.
- Self-hosting keeps transcript artifacts under your control.
- Gmail drafts are drafts only; the system does not send email.
- Google features can be disabled.
- Neo4j can run locally, on a VPS, or in Aura.

## Repository Philosophy

This package intentionally separates the system into small pieces:

- API receives work.
- Worker performs work.
- Scheduler catches missed work.
- Core package owns deterministic parsing, templates, and integrations.
- Vectorizer package owns Neo4j graph and vector memory.

That keeps the public template understandable and easy for community members to adapt.
