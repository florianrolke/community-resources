from scripts.common import read_csv
from scripts.dedupe_events import dedupe_events
from scripts.find_linkedin_profiles import match_rows
from scripts.generate_event_report import generate_report
from scripts.normalize_events import normalize_events


def test_offline_report_pipeline():
    events = dedupe_events(normalize_events(read_csv("tests/fixtures/mhi_events_raw.csv")))
    contacts = match_rows(read_csv("tests/fixtures/mhi_contacts.csv"))
    report = generate_report(events, contacts, "MHI Fixture Report")
    assert "# MHI Fixture Report" in report
    assert "MHI 2026 Congress & Expo" in report
    assert "Nikki Greenberg" in report
    assert "Thomas Casparian" in report