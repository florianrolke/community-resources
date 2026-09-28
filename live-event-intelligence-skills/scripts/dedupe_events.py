from __future__ import annotations

import argparse
from scripts.common import EVENT_FIELDS, ascii_norm, first_value, read_csv, write_csv


def event_key(row: dict) -> tuple[str, ...]:
    url = ascii_norm(first_value(row, "event_url", "url"))
    if url:
        return ("url", url)
    return (
        "fallback",
        ascii_norm(first_value(row, "event_name", "name", "title")),
        ascii_norm(first_value(row, "date_start", "date")),
        ascii_norm(first_value(row, "venue", "location")),
    )


def dedupe_events(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        key = event_key(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main():
    parser = argparse.ArgumentParser(description="Deduplicate normalized events by URL, then name/date/venue.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_csv(args.output, dedupe_events(read_csv(args.input)), EVENT_FIELDS)


if __name__ == "__main__":
    main()