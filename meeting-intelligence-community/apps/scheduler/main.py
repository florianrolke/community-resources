"""Simple scheduler for Fathom polling and optional calendar/Zoom sync hooks."""

from __future__ import annotations

import argparse
import time

from meeting_intelligence.core.config import settings
from meeting_intelligence.core.storage import enqueue_payload, processed_ids


def poll_fathom_once() -> int:
    cfg = settings()
    if not cfg.fathom_api_key:
        print("FATHOM_API_KEY not set; skipping poll")
        return 0

    import requests

    response = requests.get(
        "https://api.fathom.ai/external/v1/recordings",
        headers={"X-Api-Key": cfg.fathom_api_key},
        params={"include_transcript": "true", "limit": 10},
        timeout=30,
    )
    response.raise_for_status()
    meetings = response.json().get("items") or response.json().get("recordings") or []
    seen = processed_ids(cfg)
    enqueued = 0
    for meeting in meetings:
        source_id = str(meeting.get("recording_id") or meeting.get("id") or "")
        if not source_id or source_id in seen or not meeting.get("transcript"):
            continue
        enqueue_payload(cfg, meeting)
        enqueued += 1
    print(f"enqueued {enqueued} Fathom meetings")
    return enqueued


def calendar_zoom_sync_once() -> int:
    print("Calendar-to-Zoom sync is included as an extension point. See docs/google-setup.md and deploy/modal.")
    return 0


def run_loop() -> None:
    cfg = settings()
    while True:
        poll_fathom_once()
        calendar_zoom_sync_once()
        time.sleep(cfg.fathom_poll_minutes * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Meeting Intelligence scheduler")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        poll_fathom_once()
        calendar_zoom_sync_once()
    else:
        run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
