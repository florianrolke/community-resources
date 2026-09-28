#!/usr/bin/env python3
"""Run website outreach batches continuously.

This script wraps the existing Playwright submission agent. It does not change
submission behavior; it prepares the next unprocessed website batches, runs the
agent, exports auditable result CSVs/screenshots, updates tracking CSVs, and
keeps going.
"""

from __future__ import annotations

import csv
import argparse
import json
import shutil
import subprocess
import sys
import time
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
DEFAULT_RUN_NAME = "website-outreach"
DEFAULT_DATE_TAG = datetime.now().strftime("%Y%m%d")

AGENT = PROJECT_DIR / "execution" / "plumbing_website_submission_agent.py"
TRACKING = PROJECT_DIR / "execution" / "update_outreach_tracking_csv.py"

REACHED_STATUSES = {"confirmed", "submitted", "submitted_enter", "submitted_unconfirmed"}
SCREENSHOT_STATUSES = {
    "confirmed",
    "submitted_unconfirmed",
    "submitted",
    "submitted_enter",
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


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.append(key)
        fieldnames = seen
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_log() -> list[dict[str, object]]:
    if not LOG_FILE.exists():
        return []
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        time.sleep(2)
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))


def batch_path(run_name: str, date_tag: str, batch_num: int) -> Path:
    return DATA_DIR / f"{run_name}-next-100-batch-{batch_num}-{date_tag}.csv"


def results_path(run_name: str, date_tag: str, batch_num: int) -> Path:
    return DATA_DIR / f"{run_name}-next-100-batch-{batch_num}-results-{date_tag}.csv"


def tracking_path(run_name: str, date_tag: str, batch_num: int) -> Path:
    return DATA_DIR / f"{run_name}-next-100-batch-{batch_num}-tracking-{date_tag}.csv"


def combined_batch_path(run_name: str, date_tag: str, total: int) -> Path:
    return DATA_DIR / f"{run_name}-first-{total}-batches-{date_tag}.csv"


def combined_tracking_path(run_name: str, date_tag: str, total: int) -> Path:
    return DATA_DIR / f"{run_name}-first-{total}-tracking-{date_tag}.csv"


def processed_domains_through(run_name: str, date_tag: str, batch_num: int) -> set[str]:
    domains: set[str] = set()
    combined = combined_batch_path(run_name, date_tag, batch_num * 100)
    if combined.exists():
        for row in read_csv(combined):
            domain = normalize_domain(row.get("website") or row.get("url"))
            if domain:
                domains.add(domain)
    for path in DATA_DIR.glob(f"{run_name}-next-100-batch-*-{date_tag}.csv"):
        stem = path.stem
        marker = "batch-"
        if marker not in stem or "-results-" in stem or "-tracking-" in stem or "-resume-" in stem:
            continue
        try:
            this_num = int(stem.split(marker, 1)[1].split("-", 1)[0])
        except ValueError:
            continue
        if this_num > batch_num:
            continue
        for row in read_csv(path):
            domain = normalize_domain(row.get("website") or row.get("url"))
            if domain:
                domains.add(domain)
    return domains


def make_next_batch(source_csv: Path, run_name: str, date_tag: str, batch_num: int, prior_domains: set[str], limit: int = 100) -> Path | None:
    if not source_csv.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_csv}")
    existing = batch_path(run_name, date_tag, batch_num)
    if existing.exists():
        return existing

    source_rows = read_csv(source_csv)
    picked: list[dict[str, str]] = []
    seen = set(prior_domains)
    for row in source_rows:
        domain = normalize_domain(row.get("website") or row.get("url"))
        if not domain or domain in seen:
            continue
        seen.add(domain)
        picked.append(row)
        if len(picked) >= limit:
            break

    if not picked:
        return None
    with source_csv.open("r", encoding="utf-8-sig", newline="") as f:
        fieldnames = csv.DictReader(f).fieldnames or list(picked[0].keys())
    write_csv(existing, picked, fieldnames)
    return existing


def latest_results_for_batch(batch_csv: Path) -> list[dict[str, object]]:
    batch_domains = {
        normalize_domain(row.get("website") or row.get("url"))
        for row in read_csv(batch_csv)
        if normalize_domain(row.get("website") or row.get("url"))
    }
    latest: dict[str, dict[str, object]] = {}
    for row in read_log():
        url = str(row.get("url") or row.get("website") or row.get("contact_url") or "")
        domain = normalize_domain(url)
        if domain and domain in batch_domains:
            latest[domain] = row
    return list(latest.values())


def missing_rows_for_batch(batch_csv: Path) -> list[dict[str, str]]:
    logged_domains = {
        normalize_domain(str(row.get("url") or row.get("website") or row.get("contact_url") or ""))
        for row in latest_results_for_batch(batch_csv)
    }
    return [
        row for row in read_csv(batch_csv)
        if normalize_domain(row.get("website") or row.get("url")) not in logged_domains
    ]


def write_resume_batch(run_name: str, date_tag: str, batch_num: int, missing_rows: list[dict[str, str]]) -> Path:
    path = DATA_DIR / f"{run_name}-next-100-batch-{batch_num}-resume-{len(missing_rows)}-{date_tag}.csv"
    with batch_path(run_name, date_tag, batch_num).open("r", encoding="utf-8-sig", newline="") as f:
        fieldnames = csv.DictReader(f).fieldnames or list(missing_rows[0].keys())
    write_csv(path, missing_rows, fieldnames)
    return path


def active_agent_process(run_name: str, date_tag: str, batch_num: int) -> bool:
    profile = f"{run_name}_batch{batch_num}_{date_tag}"
    command = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.Name -like 'python*' -and $_.CommandLine -like '*plumbing_website_submission_agent.py*' -and $_.CommandLine -like '*{profile}*' }} | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=15,
        )
        return bool(proc.stdout.strip())
    except Exception:
        return False


def export_results(run_name: str, date_tag: str, batch_num: int, batch_csv: Path) -> tuple[Path, Counter]:
    rows = latest_results_for_batch(batch_csv)
    out = results_path(run_name, date_tag, batch_num)
    write_csv(out, rows)
    counts = Counter(str(row.get("status") or "") for row in rows)
    copy_success_screenshots(run_name, date_tag, batch_num, rows)
    return out, counts


def copy_success_screenshots(run_name: str, date_tag: str, batch_num: int, rows: list[dict[str, object]]) -> None:
    confirmed_dir = RESULTS_DIR / f"{run_name}-batch{batch_num}-confirmed-{date_tag}"
    unconfirmed_dir = RESULTS_DIR / f"{run_name}-batch{batch_num}-unconfirmed-{date_tag}"
    confirmed_dir.mkdir(parents=True, exist_ok=True)
    unconfirmed_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        status = str(row.get("status") or "")
        if status not in SCREENSHOT_STATUSES:
            continue
        target_dir = confirmed_dir if status == "confirmed" else unconfirmed_dir
        for key in ("screenshot_before", "screenshot_after"):
            src = str(row.get(key) or "")
            if not src:
                continue
            src_path = Path(src)
            if src_path.exists():
                shutil.copy2(src_path, target_dir / src_path.name)


def run_tracking(source_csv: Path, result_csvs: list[Path], output_csv: Path) -> str:
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(TRACKING),
        "--source-csv",
        str(source_csv),
        "--results-csv",
        *[str(p) for p in result_csvs],
        "--output-csv",
        str(output_csv),
    ]
    proc = subprocess.run(cmd, cwd=ROOT_DIR, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def combine_tracking_from_previous(run_name: str, date_tag: str, total: int, batch_tracking: Path) -> Path | None:
    previous = combined_tracking_path(run_name, date_tag, total - 100)
    if not previous.exists() or not batch_tracking.exists():
        return None
    rows = read_csv(previous) + read_csv(batch_tracking)
    fieldnames: list[str] = []
    for path in (previous, batch_tracking):
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for name in csv.DictReader(f).fieldnames or []:
                if name not in fieldnames:
                    fieldnames.append(name)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    out = combined_tracking_path(run_name, date_tag, total)
    write_csv(out, rows, fieldnames)
    return out


def run_agent(args: argparse.Namespace, batch_num: int, batch_csv: Path) -> None:
    profile_suffix = f"{args.run_name}_batch{batch_num}_{args.date_tag}"
    stdout_path = TMP_DIR / f"{profile_suffix}_stdout.log"
    stderr_path = TMP_DIR / f"{profile_suffix}_stderr.log"
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
        profile_suffix,
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
        raise RuntimeError(f"Batch {batch_num} agent failed; see {stdout_path} and {stderr_path}")


def combine_batches(run_name: str, date_tag: str, last_batch_num: int, total: int) -> Path:
    previous = combined_batch_path(run_name, date_tag, total - 100)
    current = batch_path(run_name, date_tag, last_batch_num)
    if previous.exists() and current.exists():
        rows = read_csv(previous) + read_csv(current)
        fieldnames: list[str] | None = None
        with previous.open("r", encoding="utf-8-sig", newline="") as f:
            fieldnames = csv.DictReader(f).fieldnames or []
        with current.open("r", encoding="utf-8-sig", newline="") as f:
            for name in csv.DictReader(f).fieldnames or []:
                if name not in fieldnames:
                    fieldnames.append(name)
    else:
        rows = []
        fieldnames = None
        for num in range(1, last_batch_num + 1):
            path = batch_path(run_name, date_tag, num)
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if fieldnames is None:
                    fieldnames = reader.fieldnames or []
                rows.extend(reader)
    out = combined_batch_path(run_name, date_tag, total)
    write_csv(out, rows, fieldnames)
    return out


def available_result_csvs(run_name: str, date_tag: str, last_batch_num: int) -> list[Path]:
    paths: list[Path] = []
    for num in range(1, last_batch_num + 1):
        path = results_path(run_name, date_tag, num)
        if path.exists():
            paths.append(path)
    return paths


def append_worklog(text: str) -> None:
    worklog = ROOT_DIR / "WORKLOG.md"
    with worklog.open("a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


def summarize_counts(counts: Counter) -> str:
    return ", ".join(f"{status or 'blank'}: {count}" for status, count in counts.most_common())


def reached_count(counts: Counter) -> int:
    return sum(counts.get(status, 0) for status in REACHED_STATUSES)


def write_evaluation_checkpoint(run_name: str, date_tag: str, batch_nums: list[int]) -> None:
    rows: list[dict[str, object]] = []
    counts = Counter()
    for num in batch_nums:
        path = results_path(run_name, date_tag, num)
        if not path.exists():
            continue
        batch_rows = read_csv(path)
        rows.extend(batch_rows)
        counts.update(row.get("status") or "" for row in batch_rows)
    if not rows:
        return
    review_path = DATA_DIR / f"{run_name}-batches-{batch_nums[0]}-{batch_nums[-1]}-evaluation-{date_tag}.csv"
    write_csv(review_path, rows)
    reached = reached_count(counts)
    text = f"""
## {datetime.now().strftime('%Y-%m-%d %H:%M')} - Outreach Evaluation Batches {batch_nums[0]}-{batch_nums[-1]}

- Evaluation file: `{review_path.as_posix()}`.
- Reached-out count: {reached}/{len(rows)}.
- Status mix: {summarize_counts(counts)}.
- Runner note: continued automatically after checkpoint; no blocking code change was required inside this checkpoint.
"""
    append_worklog(text)


def package_batch(args: argparse.Namespace, batch_num: int, batch_csv: Path) -> None:
    result_csv, counts = export_results(args.run_name, args.date_tag, batch_num, batch_csv)
    track_csv = tracking_path(args.run_name, args.date_tag, batch_num)
    run_tracking(batch_csv, [result_csv], track_csv)

    total = batch_num * 100
    combined_batch = combine_batches(args.run_name, args.date_tag, batch_num, total)
    combined_tracking = combine_tracking_from_previous(args.run_name, args.date_tag, total, track_csv)
    if combined_tracking is None:
        combined_tracking = combined_tracking_path(args.run_name, args.date_tag, total)
        all_results = available_result_csvs(args.run_name, args.date_tag, batch_num)
        run_tracking(combined_batch, all_results, combined_tracking)

    reached = reached_count(counts)
    text = f"""
## {datetime.now().strftime('%Y-%m-%d %H:%M')} - Outreach Batch {batch_num}

- Batch file: `{batch_csv.as_posix()}`.
- Result CSV: `{result_csv.as_posix()}`.
- Tracking CSV: `{track_csv.as_posix()}`.
- Combined first-{total} batch file: `{combined_batch.as_posix()}`.
- Combined first-{total} tracking output: `{combined_tracking.as_posix()}`.
- Batch {batch_num} reached-out count: {reached}/100.
- Batch {batch_num} status mix: {summarize_counts(counts)}.
"""
    append_worklog(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run website form outreach batches continuously")
    parser.add_argument("--source-csv", required=True, help="CSV containing website leads")
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME, help="Prefix for generated batch/result files")
    parser.add_argument("--date-tag", default=DEFAULT_DATE_TAG, help="Date tag for generated files")
    parser.add_argument("--start-batch", type=int, default=13)
    parser.add_argument("--end-batch", type=int, default=30)
    parser.add_argument("--already-running-start-batch", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
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

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    completed_since_eval: list[int] = []
    source_csv = Path(args.source_csv)
    prior_domains = processed_domains_through(args.run_name, args.date_tag, args.start_batch - 1)

    for batch_num in range(args.start_batch, args.end_batch + 1):
        batch_csv = make_next_batch(source_csv, args.run_name, args.date_tag, batch_num, prior_domains)
        if batch_csv is None:
            append_worklog(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} - Outreach Runner Exhausted List\n\n- No additional unique website rows were available for batch {batch_num}.\n")
            return

        if batch_num == args.start_batch and args.already_running_start_batch:
            stagnant_polls = 0
            previous_processed = -1
            while len(latest_results_for_batch(batch_csv)) < len(read_csv(batch_csv)):
                processed = len(latest_results_for_batch(batch_csv))
                print(f"Batch {batch_num} still running elsewhere: {processed}/{len(read_csv(batch_csv))}", flush=True)
                if processed == previous_processed:
                    stagnant_polls += 1
                else:
                    stagnant_polls = 0
                    previous_processed = processed
                if stagnant_polls >= 5 and not active_agent_process(args.run_name, args.date_tag, batch_num):
                    missing = missing_rows_for_batch(batch_csv)
                    if not missing:
                        break
                    resume_csv = write_resume_batch(args.run_name, args.date_tag, batch_num, missing)
                    print(f"Batch {batch_num} original process ended early; resuming {len(missing)} missing rows from {resume_csv}", flush=True)
                    run_agent(args, batch_num, resume_csv)
                    stagnant_polls = 0
                    previous_processed = len(latest_results_for_batch(batch_csv))
                time.sleep(args.poll_seconds)
        elif not results_path(args.run_name, args.date_tag, batch_num).exists():
            print(f"Running batch {batch_num}: {batch_csv}", flush=True)
            run_agent(args, batch_num, batch_csv)

        package_batch(args, batch_num, batch_csv)
        for row in read_csv(batch_csv):
            domain = normalize_domain(row.get("website") or row.get("url"))
            if domain:
                prior_domains.add(domain)

        completed_since_eval.append(batch_num)
        if len(completed_since_eval) >= 2:
            write_evaluation_checkpoint(args.run_name, args.date_tag, completed_since_eval[-2:])
            completed_since_eval.clear()


if __name__ == "__main__":
    main()
