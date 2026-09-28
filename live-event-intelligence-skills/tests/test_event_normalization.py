from scripts.common import read_csv
from scripts.normalize_events import normalize_events


def test_event_normalization_schema_fields():
    rows = normalize_events(read_csv("tests/fixtures/mhi_events_raw.csv"))
    first = rows[0]
    assert first["event_name"] == "MHI 2026 Congress & Expo"
    assert first["date_start"] == "2026-04-07"
    assert first["event_url"].startswith("https://")
    assert first["confidence"] == "confirmed"