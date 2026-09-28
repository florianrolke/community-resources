"""Optional Google Docs, Drive, Gmail, and Calendar integrations."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from email.mime.text import MIMEText


DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _write_token(token_json: str, filename: str) -> str:
    if not token_json:
        raise ValueError(f"Missing token JSON for {filename}")
    path = os.path.join(tempfile.gettempdir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(token_json)
    return path


def _creds_from_json(token_json: str, filename: str, scopes: list[str]):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    path = _write_token(token_json, filename)
    token_data = json.loads(open(path, encoding="utf-8").read())
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes") or scopes,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def create_google_doc(settings, payload: dict, summary: dict, transcript_text: str) -> dict:
    if not settings.google_docs_enabled:
        return {"enabled": False, "doc_url": ""}

    from googleapiclient.discovery import build

    creds = _creds_from_json(settings.google_docs_token_json, "token_docs.json", DOCS_SCOPES)
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    title = f"Meeting Summary - {payload['participant_name']} - {payload['meeting_date']}"
    if settings.google_docs_template_id:
        copied = drive.files().copy(fileId=settings.google_docs_template_id, body={"name": title}).execute()
        doc_id = copied["id"]
        doc = docs.documents().get(documentId=doc_id).execute()
        content = doc.get("body", {}).get("content", [])
        if len(content) > 1:
            end_index = content[-1].get("endIndex", 1) - 1
            if end_index > 1:
                docs.documents().batchUpdate(
                    documentId=doc_id,
                    body={"requests": [{"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}}]},
                ).execute()
    else:
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

    if settings.google_drive_folder_id:
        file_info = drive.files().get(fileId=doc_id, fields="parents").execute()
        previous = ",".join(file_info.get("parents", []))
        drive.files().update(
            fileId=doc_id,
            addParents=settings.google_drive_folder_id,
            removeParents=previous,
            fields="id, parents",
        ).execute()

    text = build_document_text(payload, summary, transcript_text)
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": text}}]},
    ).execute()

    try:
        drive.permissions().create(
            fileId=doc_id,
            body={"role": "commenter", "type": "anyone"},
        ).execute()
    except Exception:
        pass

    return {"enabled": True, "doc_id": doc_id, "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit"}


def build_document_text(payload: dict, summary: dict, transcript_text: str) -> str:
    parts = [
        f"Meeting Summary - {payload['participant_name']} - {payload['meeting_date']}",
        "",
        "Action Items",
    ]
    parts.extend(summary.get("action_items") or ["No action items identified."])
    parts.extend(["", "Main Talking Points"])
    parts.extend(summary.get("meeting_summary") or ["No discussion points recorded."])
    parts.extend(["", "Epiphanies"])
    parts.extend(summary.get("epiphanies") or ["No epiphanies recorded."])
    parts.extend(["", "Transcript", transcript_text])
    return "\n".join(parts)


def create_gmail_draft(settings, recipient: str, subject: str, body_html: str) -> dict:
    if not settings.gmail_drafts_enabled or not recipient:
        return {"enabled": False, "draft_id": ""}

    from googleapiclient.discovery import build

    creds = _creds_from_json(settings.google_gmail_token_json, "token_gmail.json", GMAIL_SCOPES)
    service = build("gmail", "v1", credentials=creds)
    message = MIMEText(body_html, "html")
    message["To"] = recipient
    message["From"] = "me"
    message["Subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"enabled": True, "draft_id": draft.get("id", "")}
