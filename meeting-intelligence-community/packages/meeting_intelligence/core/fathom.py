"""Fathom payload parsing, transcript formatting, and webhook verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any


def verify_webhook_signature(secret: str, headers: dict[str, str], raw_body: bytes) -> bool:
    """Verify a Fathom/Svix-style HMAC webhook signature when a secret is configured.

    If no secret is configured, returns True so community users can start locally.
    """
    if not secret:
        return True

    normalized = {k.lower(): v for k, v in headers.items()}
    webhook_id = normalized.get("webhook-id", "")
    webhook_timestamp = normalized.get("webhook-timestamp", "")
    signature_header = normalized.get("webhook-signature", "")
    if not webhook_id or not webhook_timestamp or not signature_header:
        return False

    try:
        timestamp = int(webhook_timestamp)
    except ValueError:
        return False

    now = int(datetime.now(tz=timezone.utc).timestamp())
    if abs(now - timestamp) > 300:
        return False

    signed_content = f"{webhook_id}.{webhook_timestamp}.{raw_body.decode('utf-8')}"
    secret_part = secret.split("_", 1)[1] if "_" in secret else secret
    try:
        key = base64.b64decode(secret_part)
    except Exception:
        key = secret_part.encode("utf-8")

    expected = base64.b64encode(
        hmac.new(key, signed_content.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    signatures = [part.split(",", 1)[-1].strip() for part in signature_header.split(" ")]
    return any(hmac.compare_digest(expected, sig) for sig in signatures if sig)


def recording_id(payload: dict[str, Any]) -> str:
    for key in ("recording_id", "id", "meeting_id", "recordingId"):
        value = payload.get(key)
        if value:
            return str(value)
    title = payload.get("title") or payload.get("meeting_title") or "meeting"
    started = payload.get("recording_start_time") or payload.get("started_at") or ""
    digest = hashlib.sha1(f"{title}|{started}".encode("utf-8")).hexdigest()[:16]
    return f"generated-{digest}"


def meeting_title(payload: dict[str, Any]) -> str:
    return payload.get("title") or payload.get("meeting_title") or "Untitled Meeting"


def started_at(payload: dict[str, Any]) -> str:
    return payload.get("recording_start_time") or payload.get("started_at") or payload.get("scheduled_start_time") or ""


def parse_meeting_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(tz=timezone.utc)


def date_labels(payload: dict[str, Any]) -> tuple[str, str]:
    dt = parse_meeting_datetime(started_at(payload))
    return dt.strftime("%B %d, %Y"), dt.strftime("%m/%d")


def extract_fathom_summary(payload: dict[str, Any]) -> str:
    default_summary = payload.get("default_summary", {})
    if isinstance(default_summary, dict):
        return default_summary.get("markdown_formatted") or default_summary.get("text") or ""
    return payload.get("summary") or ""


def transcript_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    transcript = payload.get("transcript") or []
    return transcript if isinstance(transcript, list) else []


def format_transcript(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for entry in transcript_entries(payload):
        speaker = entry.get("speaker", {})
        speaker_name = speaker.get("display_name") if isinstance(speaker, dict) else ""
        speaker_name = speaker_name or entry.get("speaker_name") or "Unknown"
        text = (entry.get("text") or "").strip()
        if text:
            lines.append(f"{speaker_name}: {text}")
    return "\n\n".join(lines)


def speaker_names(payload: dict[str, Any]) -> set[str]:
    names = set()
    for entry in transcript_entries(payload):
        speaker = entry.get("speaker", {})
        name = speaker.get("display_name") if isinstance(speaker, dict) else ""
        if name:
            names.add(name)
    return names


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return slug or "meeting"


def parse_payload_bytes(raw_body: bytes) -> dict[str, Any]:
    return json.loads(raw_body.decode("utf-8"))
