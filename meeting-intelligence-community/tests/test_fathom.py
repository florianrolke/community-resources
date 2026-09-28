import json
from pathlib import Path

from meeting_intelligence.core.fathom import date_labels, format_transcript, recording_id


def sample_payload():
    return json.loads(Path("examples/sample_fathom_payload.json").read_text(encoding="utf-8"))


def test_recording_id_from_payload():
    assert recording_id(sample_payload()) == "sample-001"


def test_format_transcript_preserves_speakers():
    text = format_transcript(sample_payload())
    assert "Your Name:" in text
    assert "Alex Example:" in text
    assert "LinkedIn outreach copy" in text


def test_date_labels():
    full, short = date_labels(sample_payload())
    assert full == "June 02, 2026"
    assert short == "06/02"
