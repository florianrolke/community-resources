"""End-to-end meeting processing pipeline."""

from __future__ import annotations

from pathlib import Path

from .config import load_json
from .email_style import DEFAULT_POLICY, generate_email_body, validate_first_paragraph
from .fathom import date_labels, extract_fathom_summary, format_transcript, meeting_title, recording_id
from .google_integration import create_gmail_draft, create_google_doc
from .participants import resolve_participant
from .storage import mark_processed, move_job_to_processed, read_json, write_json
from .summary import generate_summary


def process_payload(settings, payload: dict) -> dict:
    source_id = recording_id(payload)
    contacts = load_json(settings.contacts_path, {})
    policy = {**DEFAULT_POLICY, **load_json(settings.style_policy_path, {})}
    participant = resolve_participant(payload, contacts, settings.host_email, settings.host_name)
    meeting_date, date_short = date_labels(payload)
    transcript_text = format_transcript(payload)
    summary = generate_summary(
        settings,
        transcript_text,
        participant["name"],
        extract_fathom_summary(payload),
        payload.get("action_items") or [],
    )

    doc_payload = {
        "source_id": source_id,
        "title": meeting_title(payload),
        "participant_name": participant["name"],
        "participant_email": participant["email"],
        "meeting_date": meeting_date,
        "date_short": date_short,
    }

    doc_result = create_google_doc(settings, doc_payload, summary, transcript_text)
    doc_url = doc_result.get("doc_url") or f"{settings.public_base_url}/local-docs/{source_id}"
    email_body = generate_email_body(participant["name"], doc_url, summary.get("main_points", ""), meeting_date, policy)
    errors, warnings = validate_first_paragraph(email_body, policy)
    if errors:
        raise ValueError(f"Email validation failed: {errors}")

    subject = f"Meeting Summary - {date_short} - {participant['name']}"
    draft_result = create_gmail_draft(settings, participant["email"], subject, email_body)

    artifact = {
        "source_id": source_id,
        "title": meeting_title(payload),
        "participant": participant,
        "meeting_date": meeting_date,
        "summary": summary,
        "transcript_text": transcript_text,
        "doc": doc_result,
        "gmail": draft_result,
        "email": {"subject": subject, "body_html": email_body, "warnings": warnings},
    }

    write_json(settings.summaries_dir / f"{source_id}.json", artifact)
    transcript_path = settings.transcripts_dir / f"{source_id}.txt"
    transcript_path.write_text(transcript_text, encoding="utf-8")

    if settings.neo4j_enabled:
        from meeting_intelligence.vectorizer.neo4j_store import vectorize_meeting_artifact

        vectorize_meeting_artifact(settings, artifact)

    mark_processed(settings, source_id)
    return artifact


def process_job_file(settings, job_path: Path) -> dict:
    payload = read_json(job_path, {})
    artifact = process_payload(settings, payload)
    move_job_to_processed(settings, job_path)
    return artifact
