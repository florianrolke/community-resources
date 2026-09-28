#!/usr/bin/env python3
"""Run retry batches for website outreach rows marked needs_retry."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
TMP_DIR = PROJECT_DIR / ".tmp"
RESULTS_DIR = PROJECT_DIR / "submission-results"
LOG_FILE = TMP_DIR / "plumbing_website_submission_log.json"
AGENT = PROJECT_DIR / "execution" / "plumbing_website_submission_agent.py"
TRACKING = PROJECT_DIR / "execution" / "update_outreach_tracking_csv.py"
DATE_TAG = "20260617"

REACHED_STATUSES = {"confirmed", "submitted", "submitted_enter", "submitted_unconfirmed"}
RETRY_PRIORITY = {
    "missing_required": 0,
    "no_fillable_fields": 1,
    "failed_validation": 2,
    "load_error": 3,
    "captcha_failed": 4,
}


def normalize_domain(url: str | None) -> str:
    if not url:
        return ""
    raw = str(url).strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        return urlparse(raw).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def csv_fieldnames(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return csv.DictReader(f).fieldnames or []


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_log() -> list[dict[str, object]]:
    if not LOG_FILE.exists():
        return []
    return json.loads(LOG_FILE.read_text(encoding="utf-8"))


def retry_batch_path(run_name: str, batch_num: int) -> Path:
    return DATA_DIR / f"{run_name}-batch-{batch_num}-{DATE_TAG}.csv"


def retry_results_path(run_name: str, batch_num: int) -> Path:
    return DATA_DIR / f"{run_name}-batch-{batch_num}-results-{DATE_TAG}.csv"


def retry_tracking_path(run_name: str, batch_num: int) -> Path:
    return DATA_DIR / f"{run_name}-batch-{batch_num}-tracking-{DATE_TAG}.csv"


def order_retry_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    candidates = [row for row in rows if row.get("needs_retry") == "TRUE"]
    return sorted(
        candidates,
        key=lambda row: (
            RETRY_PRIORITY.get((row.get("outreach_status") or "").strip(), 99),
            row.get("outreach_status") or "",
            normalize_domain(row.get("website") or row.get("url")),
        ),
    )


def latest_results_for_batch(batch_csv: Path) -> list[dict[str, object]]:
    domains = {
        normalize_domain(row.get("website") or row.get("url"))
        for row in read_csv(batch_csv)
        if normalize_domain(row.get("website") or row.get("url"))
    }
    latest: dict[str, dict[str, object]] = {}
    for row in read_log():
        domain = normalize_domain(str(row.get("url") or row.get("website") or row.get("contact_url") or ""))
        if domain in domains:
            latest[domain] = row
    return list(latest.values())


def copy_success_screenshots(run_name: str, batch_num: int, rows: list[dict[str, object]]) -> None:
    confirmed = RESULTS_DIR / f"{run_name}-batch{batch_num}-confirmed-{DATE_TAG}"
    unconfirmed = RESULTS_DIR / f"{run_name}-batch{batch_num}-unconfirmed-{DATE_TAG}"
    confirmed.mkdir(parents=True, exist_ok=True)
    unconfirmed.mkdir(parents=True, exist_ok=True)
    for row in rows:
        status = str(row.get("status") or "")
        if status not in REACHED_STATUSES:
            continue
        target = confirmed if status == "confirmed" else unconfirmed
        for key in ("screenshot_before", "screenshot_after"):
            src = str(row.get(key) or "")
            if not src:
                continue
            src_path = Path(src)
            if src_path.exists():
                shutil.copy2(src_path, target / src_path.name)


def run_agent(batch_csv: Path, args: argparse.Namespace, batch_num: int) -> None:
    stdout_path = TMP_DIR / f"{args.run_name}_batch{batch_num}_stdout.log"
    stderr_path = TMP_DIR / f"{args.run_name}_batch{batch_num}_stderr.log"
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(AGENT),
        "--batch",
        str(batch_csv),
        "--limit",
        "100",
        "--browser-channel",
        "chrome",
        "--headless",
        "--profile-suffix",
        f"{args.run_name}_batch{batch_num}_{DATE_TAG}",
        "--name",
        args.name,
        "--email",
        args.email,
        "--phone",
        args.phone,
        "--sender-address",
        args.sender_address,
        "--sender-city",
        args.sender_city,
        "--sender-state",
        args.sender_state,
        "--sender-postal-code",
        args.sender_postal_code,
        "--subject",
        args.subject,
        "--delay",
        str(args.delay),
    ]
    if args.exact_charley_hayden_template:
        cmd.append("--exact-charley-hayden-template")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(cmd, cwd=ROOT_DIR, stdout=stdout, stderr=stderr, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Retry batch {batch_num} failed; see {stdout_path} and {stderr_path}")


def run_tracking(source_csv: Path, result_csvs: list[Path], output_csv: Path) -> None:
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(TRACKING),
        "--source-csv",
        str(source_csv),
        "--results-csv",
        *[str(path) for path in result_csvs],
        "--output-csv",
        str(output_csv),
    ]
    proc = subprocess.run(cmd, cwd=ROOT_DIR, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)


def append_worklog(text: str) -> None:
    with (ROOT_DIR / "WORKLOG.md").open("a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry Charley outreach rows marked needs_retry")
    parser.add_argument("--tracking-csv", required=True)
    parser.add_argument("--run-name", default="website-outreach-retry-backlog")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=6)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", default="")
    parser.add_argument("--sender-address", default="")
    parser.add_argument("--sender-city", default="")
    parser.add_argument("--sender-state", default="")
    parser.add_argument("--sender-postal-code", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--exact-charley-hayden-template", action="store_true")
    args = parser.parse_args()

    tracking_csv = Path(args.tracking_csv)
    rows = order_retry_rows(read_csv(tracking_csv))
    fieldnames = csv_fieldnames(tracking_csv)
    result_paths: list[Path] = []

    for index in range(args.max_batches):
        start = index * args.batch_size
        chunk = rows[start:start + args.batch_size]
        if not chunk:
            break
        batch_num = index + 1
        batch_csv = retry_batch_path(args.run_name, batch_num)
        write_csv(batch_csv, chunk, fieldnames)
        run_agent(batch_csv, args, batch_num)

        result_rows = latest_results_for_batch(batch_csv)
        result_csv = retry_results_path(args.run_name, batch_num)
        write_csv(result_csv, result_rows)
        copy_success_screenshots(args.run_name, batch_num, result_rows)
        result_paths.append(result_csv)

        batch_tracking = retry_tracking_path(args.run_name, batch_num)
        run_tracking(batch_csv, [result_csv], batch_tracking)

        counts = Counter(str(row.get("status") or "") for row in result_rows)
        reached = sum(counts.get(status, 0) for status in REACHED_STATUSES)
        append_worklog(f"""
## {datetime.now().strftime('%Y-%m-%d %H:%M')} - Charley Retry Backlog Batch {batch_num}

- Retry batch file: `{batch_csv.as_posix()}`.
- Retry result CSV: `{result_csv.as_posix()}`.
- Retry tracking CSV: `{batch_tracking.as_posix()}`.
- Recovered reached-out count: {reached}/{len(chunk)}.
- Status mix: {", ".join(f"{status or 'blank'}: {count}" for status, count in counts.most_common())}.
""")

    if result_paths:
        combined_retry_tracking = DATA_DIR / f"{args.run_name}-combined-tracking-{DATE_TAG}.csv"
        run_tracking(tracking_csv, result_paths, combined_retry_tracking)
        append_worklog(f"""
## {datetime.now().strftime('%Y-%m-%d %H:%M')} - Charley Retry Backlog Combined

- Combined retry tracking output: `{combined_retry_tracking.as_posix()}`.
- Retry result files merged: {len(result_paths)}.
""")


if __name__ == "__main__":
    main()
