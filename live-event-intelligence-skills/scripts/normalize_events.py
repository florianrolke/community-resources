from __future__ import annotations

import argparse
from scripts.common import EVENT_FIELDS, compact_text, first_value, read_csv, write_csv


def normalize_event_row(row: dict) -> dict:
    event_name = first_value(row, "event_name", "name", "title", "Event", "Event Name")
    date_start = first_value(row, "date_start", "start_date", "date", "Date", "startDate")
    event_url = first_value(row, "event_url", "url", "website", "Website", "eventUrl")
    evidence = first_value(row, "evidence", "source_url", "source", "snippet", "description")
    confidence = first_value(row, "confidence") or ("confirmed" if event_url and event_name else "needs-manual-verification")
    return {
        "event_name": event_name,
        "date_start": date_start,
        "date_end": first_value(row, "date_end", "end_date", "endDate"),
        "venue": first_value(row, "venue", "location", "Venue"),
        "city": first_value(row, "city", "City"),
        "state": first_value(row, "state", "State"),
        "country": first_value(row, "country", "Country"),
        "category": first_value(row, "category", "type", "segment", "Category"),
        "source": first_value(row, "source", "Source") or "manual",
        "event_url": event_url,
        "organizer": first_value(row, "organizer", "host", "organization"),
        "organizer_url": first_value(row, "organizer_url", "organizerWebsite"),
        "cost": first_value(row, "cost", "price"),
        "tags": first_value(row, "tags", "keywords"),
        "description": compact_text(first_value(row, "description", "snippet", "summary"), 500),
        "confidence": confidence,
        "evidence": compact_text(evidence, 500),
    }


def normalize_events(rows: list[dict]) -> list[dict]:
    return [normalize_event_row(row) for row in rows if any(row.values())]


def main():
    parser = argparse.ArgumentParser(description="Normalize raw event CSV rows to the live event schema.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_csv(args.output, normalize_events(read_csv(args.input)), EVENT_FIELDS)


if __name__ == "__main__":
    main()