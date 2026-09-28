from scripts.common import read_csv
from scripts.dedupe_events import dedupe_events
from scripts.normalize_events import normalize_events


def test_dedupe_by_url_first():
    rows = normalize_events(read_csv("tests/fixtures/mhi_events_raw.csv"))
    deduped = dedupe_events(rows)
    names = [r["event_name"] for r in deduped]
    assert names.count("MHI 2026 Congress & Expo") == 1
    assert len(deduped) == 3