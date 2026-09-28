import json
from pathlib import Path

from meeting_intelligence.core.participants import canonical_by_email, normalize_display_name, resolve_participant


def test_canonical_by_email_prefers_full_name():
    contacts = {
        "alex": "alex@example.com",
        "Alex Example": {"email": "alex@example.com"},
    }
    assert canonical_by_email("alex@example.com", contacts) == "Alex Example"


def test_normalize_display_name_capitalizes_first_name():
    assert normalize_display_name("alex") == "Alex"


def test_resolve_participant_from_invitee_and_contacts():
    payload = json.loads(Path("examples/sample_fathom_payload.json").read_text(encoding="utf-8"))
    contacts = {"Alex Example": "alex@example.com"}
    participant = resolve_participant(payload, contacts, "you@example.com", "Your Name")
    assert participant["name"] == "Alex Example"
    assert participant["email"] == "alex@example.com"
    assert participant["first_name"] == "Alex"
