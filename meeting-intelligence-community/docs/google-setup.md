# Google Integration Setup

Google features are optional. Enable only what you need.

## APIs to Enable

In Google Cloud Console:

1. Create or select a project.
2. Go to APIs & Services > Library.
3. Enable:
   - Google Docs API
   - Google Drive API
   - Gmail API
   - Google Calendar API, only if you want Calendar title resolution or Calendar-to-Zoom sync.

## OAuth Consent Screen

1. Go to APIs & Services > OAuth consent screen.
2. Choose External for personal/community use, or Internal for Workspace.
3. Add yourself as a test user while in testing mode.
4. Add scopes only for enabled features.

## OAuth Client

1. Go to APIs & Services > Credentials.
2. Create OAuth client ID.
3. Choose Desktop app for local setup.
4. Download the JSON to `credentials/google_oauth_client.json`.

## Generate Token JSON

Run these locally:

```bash
python scripts/auth_google.py --client-secret credentials/google_oauth_client.json --target docs --output token_docs.json
python scripts/auth_google.py --client-secret credentials/google_oauth_client.json --target gmail --output token_gmail.json
python scripts/auth_google.py --client-secret credentials/google_oauth_client.json --target calendar --output token_calendar.json
```

Paste the full JSON contents into `.env`:

```env
GOOGLE_DOCS_ENABLED=true
GOOGLE_DOCS_TOKEN_JSON={"token":"..."}

GMAIL_DRAFTS_ENABLED=true
GOOGLE_GMAIL_TOKEN_JSON={"token":"..."}

GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_TOKEN_JSON={"token":"..."}
```

## Scopes

- Docs + Drive: create and update meeting summary documents.
- Gmail compose: create drafts only, not send emails.
- Calendar readonly: read calendar events for title resolution.

## Google Doc Template

The minimal implementation creates a new plain Google Doc. To adapt it to a template, set:

```env
GOOGLE_DOCS_TEMPLATE_ID=your-template-doc-id
GOOGLE_DRIVE_FOLDER_ID=optional-folder-id
```

The document ID is the part between `/d/` and `/edit` in a Google Docs URL.

## Sharing Permissions

The default code tries to set `anyone with link` to `commenter`. If your Workspace admin blocks public sharing, the document will still be created, but sharing may fail silently. Adjust sharing in `packages/meeting_intelligence/core/google_integration.py` if your organization requires restricted permissions.
