"""Worker process for pending meeting jobs."""

from __future__ import annotations

import argparse
import time
import traceback

from meeting_intelligence.core.config import settings
from meeting_intelligence.core.pipeline import process_job_file
from meeting_intelligence.core.storage import pending_jobs


def process_once() -> int:
    cfg = settings()
    count = 0
    for job_path in pending_jobs(cfg):
        try:
            artifact = process_job_file(cfg, job_path)
            print(f"processed {artifact['source_id']}")
            count += 1
        except Exception:
            print(f"failed {job_path}")
            traceback.print_exc()
    return count


def run_loop(interval_seconds: int) -> None:
    while True:
        process_once()
        time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Meeting Intelligence worker")
    parser.add_argument("--once", action="store_true", help="Process pending jobs once and exit")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval for worker loop")
    args = parser.parse_args()
    if args.once:
        process_once()
    else:
        run_loop(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
