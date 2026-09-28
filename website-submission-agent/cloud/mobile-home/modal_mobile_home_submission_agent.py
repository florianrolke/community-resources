"""Modal cloud runner for the mobile-home website submission agent.

Deploy from the repository root:

    modal deploy website-submission-agent/cloud/mobile-home/modal_mobile_home_submission_agent.py

This wraps the existing Playwright/CapSolver agent without changing its logic.
It is designed for batch execution from n8n, Make, cron, or a manual HTTP call.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import modal
from fastapi import Header, HTTPException


APP_ROOT = Path("/app")
AGENT_ROOT = APP_ROOT / "website-submission-agent"
AGENT_SCRIPT = AGENT_ROOT / "execution" / "plumbing_website_submission_agent.py"
PERSIST_ROOT = Path("/persist")

LOCAL_AGENT_DIR = Path(__file__).resolve().parents[2]
LOCAL_AGENT_SCRIPT = LOCAL_AGENT_DIR / "execution" / "plumbing_website_submission_agent.py"

app = modal.App("mobile-home-submission-agent")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "ca-certificates",
        "fonts-liberation",
        "libasound2",
        "libatk-bridge2.0-0",
        "libatk1.0-0",
        "libatspi2.0-0",
        "libcairo2",
        "libcups2",
        "libdbus-1-3",
        "libdrm2",
        "libgbm1",
        "libglib2.0-0",
        "libgtk-3-0",
        "libnspr4",
        "libnss3",
        "libpango-1.0-0",
        "libx11-6",
        "libxcb1",
        "libxcomposite1",
        "libxdamage1",
        "libxext6",
        "libxfixes3",
        "libxkbcommon0",
        "libxrandr2",
        "wget",
        "xvfb",
    )
    .pip_install("fastapi", "python-dotenv>=1.0.0", "playwright>=1.49.0", "capsolver>=1.0.7")
    .run_commands("python -m playwright install chromium")
    .add_local_file(str(LOCAL_AGENT_SCRIPT), remote_path=str(AGENT_SCRIPT))
)

volume = modal.Volume.from_name("mobile-home-submission-runs", create_if_missing=True)


def _authorize(authorization: str | None) -> None:
    expected = os.environ.get("MOBILE_HOME_AGENT_AUTH_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="Missing MOBILE_HOME_AGENT_AUTH_TOKEN secret")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if authorization.replace("Bearer ", "", 1).strip() != expected:
        raise HTTPException(status_code=403, detail="Invalid bearer token")


def _normalize_domain(url: str | None) -> str:
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


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("No rows provided")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _slice_source(source_csv: Path, run_csv: Path, offset: int, limit: int, skip_domains: set[str]) -> list[dict[str, str]]:
    source_rows = _read_rows(source_csv)
    picked: list[dict[str, str]] = []
    seen = set(skip_domains)
    for row in source_rows[offset:]:
        domain = _normalize_domain(row.get("website") or row.get("url"))
        if not domain or domain in seen:
            continue
        seen.add(domain)
        picked.append(row)
        if len(picked) >= limit:
            break
    _write_rows(run_csv, picked)
    return picked


def _write_payload_rows(run_csv: Path, rows: list[dict[str, str]], limit: int, skip_domains: set[str]) -> list[dict[str, str]]:
    picked: list[dict[str, str]] = []
    seen = set(skip_domains)
    for row in rows:
        domain = _normalize_domain(row.get("website") or row.get("url"))
        if domain and domain in seen:
            continue
        if domain:
            seen.add(domain)
        picked.append({str(k): "" if v is None else str(v) for k, v in row.items()})
        if len(picked) >= limit:
            break
    _write_rows(run_csv, picked)
    return picked


def _latest_results_for_domains(domains: set[str]) -> list[dict[str, object]]:
    log_path = AGENT_ROOT / ".tmp" / "plumbing_website_submission_log.json"
    if not log_path.exists():
        return []
    try:
        rows = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        domain = _normalize_domain(str(row.get("url") or row.get("website") or row.get("contact_url") or ""))
        if domain and domain in domains:
            latest[domain] = row
    return list(latest.values())


def _copy_artifacts(run_dir: Path, result_rows: list[dict[str, object]], stdout_path: Path, stderr_path: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = AGENT_ROOT / ".tmp"
    log_path = tmp_dir / "plumbing_website_submission_log.json"
    if log_path.exists():
        shutil.copy2(log_path, run_dir / "plumbing_website_submission_log.json")
    shutil.copy2(stdout_path, run_dir / "stdout.log")
    shutil.copy2(stderr_path, run_dir / "stderr.log")

    screenshots_dir = run_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    for row in result_rows:
        for key in ("screenshot_before", "screenshot_after", "review_screenshot"):
            value = str(row.get(key) or "")
            if not value:
                continue
            src = Path(value)
            if src.exists():
                shutil.copy2(src, screenshots_dir / src.name)


def _write_result_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    if not fieldnames:
        fieldnames = ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("mobile-home-submission-agent-secrets"),
    ],
    volumes={"/persist": volume},
    timeout=60 * 60 * 6,
)
@modal.fastapi_endpoint(method="POST")
def run_mobile_home_batch(data: dict, authorization: str = Header(None)) -> dict:
    """Run one mobile-home website-submission batch in the cloud.

    Accepted payload:

    {
      "source_csv": "data/mobile-home-strict-form-submission-queue.csv",
      "volume_source_csv": "queues/mobile-home-strict-form-submission-queue.csv",
      "rows": [{"company": "...", "website": "..."}],
      "limit": 100,
      "offset": 0,
      "dry_run": false,
      "review_before_submit": false,
      "stop_after_successes": null,
      "skip_domains": ["alreadydone.com"]
    }

    `rows` is the safest mode for tests. `volume_source_csv` can be used after
    a queue CSV is placed into the Modal volume. `source_csv` is only for
    explicitly bundled non-sensitive test files.
    """

    _authorize(authorization)

    run_id = data.get("run_id") or f"mh-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    limit = int(data.get("limit") or 100)
    offset = int(data.get("offset") or 0)
    skip_domains = {_normalize_domain(domain) for domain in data.get("skip_domains", []) if domain}
    run_dir = PERSIST_ROOT / "runs" / run_id
    run_csv = run_dir / "input.csv"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"

    if data.get("rows"):
        picked = _write_payload_rows(run_csv, data["rows"], limit, skip_domains)
    elif data.get("volume_source_csv"):
        source_csv = PERSIST_ROOT / str(data["volume_source_csv"]).replace("\\", "/")
        if not source_csv.exists():
            raise HTTPException(status_code=400, detail=f"volume_source_csv not found: {data['volume_source_csv']}")
        picked = _slice_source(source_csv, run_csv, offset, limit, skip_domains)
    else:
        source_csv_value = data.get("source_csv")
        if not source_csv_value:
            raise HTTPException(status_code=400, detail="Provide rows, volume_source_csv, or an explicitly bundled source_csv")
        source_csv = AGENT_ROOT / str(source_csv_value).replace("\\", "/")
        if not source_csv.exists():
            raise HTTPException(status_code=400, detail=f"source_csv not found: {source_csv_value}")
        picked = _slice_source(source_csv, run_csv, offset, limit, skip_domains)

    domains = {
        _normalize_domain(row.get("website") or row.get("url"))
        for row in picked
        if _normalize_domain(row.get("website") or row.get("url"))
    }

    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(AGENT_SCRIPT),
        "--batch",
        str(run_csv),
        "--limit",
        str(limit),
        "--browser-channel",
        "chromium",
        "--headless",
        "--profile-suffix",
        run_id,
        "--name",
        data.get("name") or os.environ.get("MOBILE_HOME_SENDER_NAME", "Sender Name"),
        "--email",
        data.get("email") or os.environ.get("MOBILE_HOME_SENDER_EMAIL", "sender@example.com"),
        "--phone",
        data.get("phone") or os.environ.get("MOBILE_HOME_SENDER_PHONE", ""),
        "--sender-address",
        data.get("sender_address") or "1455 Clearview Drive",
        "--sender-city",
        data.get("sender_city") or "McKinney",
        "--sender-state",
        data.get("sender_state") or "TX",
        "--sender-postal-code",
        data.get("sender_postal_code") or "75072",
        "--subject",
        data.get("subject") or "Michigan mobile home case study",
        "--exact-mobile-home-template",
        "--delay",
        str(data.get("delay") or 3),
    ]

    if data.get("dry_run"):
        cmd.append("--dry-run")
    if data.get("review_before_submit"):
        cmd.append("--review-before-submit")
    if data.get("stop_after_successes"):
        cmd.extend(["--stop-after-successes", str(data["stop_after_successes"])])

    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(cmd, cwd=AGENT_ROOT, stdout=stdout, stderr=stderr, text=True)

    result_rows = _latest_results_for_domains(domains)
    result_csv = run_dir / "results.csv"
    _write_result_csv(result_csv, result_rows)
    counts = Counter(str(row.get("status") or "") for row in result_rows)
    _copy_artifacts(run_dir, result_rows, stdout_path, stderr_path)
    volume.commit()

    return {
        "run_id": run_id,
        "returncode": proc.returncode,
        "input_count": len(picked),
        "logged_count": len(result_rows),
        "status_counts": dict(counts),
        "duration_seconds": round(time.time() - started, 1),
        "volume_run_dir": str(run_dir),
        "result_csv": str(result_csv),
        "note": "Use Modal volume mobile-home-submission-runs to download screenshots/results.",
    }
