#!/usr/bin/env python3
"""Coolify/Hostinger worker for website form submissions.

The worker reads a campaign queue CSV from persistent storage or config, selects
unattempted domains, invokes the existing Playwright submission agent, writes
results/screenshots/logs back to the volume, updates state, and optionally loops.

It remains backward compatible with the original mobile-home environment
variables, but it can also be configured from one campaign JSON file/env value
for new client deployments.
"""

from __future__ import annotations

import base64
import csv
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlsplit
from urllib.request import Request, urlopen


APP_ROOT = Path("/app")
AGENT = APP_ROOT / "execution" / "plumbing_website_submission_agent.py"
AGENT_LOG = APP_ROOT / ".tmp" / "plumbing_website_submission_log.json"

SENSITIVE_CONFIG_KEYS = {
    "CAPSOLVER_API_KEY",
    "SENDER_EMAIL",
    "SENDER_PHONE",
    "STATUS_AUTH_TOKEN",
}

CONFIG_ENV_MAP = {
    "campaign_name": "CAMPAIGN_NAME",
    "run_id_prefix": "RUN_ID_PREFIX",
    "source_csv": "SOURCE_CSV",
    "queue_csv_b64": "QUEUE_CSV_B64",
    "queue_csv_text": "QUEUE_CSV_TEXT",
    "queue_csv_url": "QUEUE_CSV_URL",
    "queue_skip_rows": "QUEUE_SKIP_ROWS",
    "results_root": "RESULTS_ROOT",
    "state_file": "STATE_FILE",
    "run_mode": "RUN_MODE",
    "batch_limit": "BATCH_LIMIT",
    "loop_sleep_seconds": "LOOP_SLEEP_SECONDS",
    "agent_timeout_seconds": "AGENT_TIMEOUT_SECONDS",
    "browser_channel": "BROWSER_CHANNEL",
    "headless": "HEADLESS",
    "delay_seconds": "DELAY_SECONDS",
    "dry_run": "DRY_RUN",
    "review_before_submit": "REVIEW_BEFORE_SUBMIT",
    "stop_after_successes": "STOP_AFTER_SUCCESSES",
    "sender_name": "SENDER_NAME",
    "sender_email": "SENDER_EMAIL",
    "sender_phone": "SENDER_PHONE",
    "sender_address": "SENDER_ADDRESS",
    "sender_city": "SENDER_CITY",
    "sender_state": "SENDER_STATE",
    "sender_postal_code": "SENDER_POSTAL_CODE",
    "subject": "SUBJECT",
    "message": "MESSAGE",
    "template_flag": "TEMPLATE_FLAG",
    "capsolver_api_key": "CAPSOLVER_API_KEY",
    "summary_file": "SUMMARY_FILE",
    "worker_events_file": "WORKER_EVENTS_FILE",
    "worker_status_file": "WORKER_STATUS_FILE",
    "status_server_enabled": "STATUS_SERVER_ENABLED",
    "status_host": "STATUS_HOST",
    "status_port": "STATUS_PORT",
    "status_auth_token": "STATUS_AUTH_TOKEN",
}


def log_event(event: str, **fields: object) -> None:
    payload = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=True), flush=True)
    events_file = os.environ.get("WORKER_EVENTS_FILE", "/data/state/worker-events.jsonl").strip()
    if not events_file:
        return
    try:
        path = Path(events_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        # Logging must never break the outreach run.
        pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


def read_json_from_url(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "website-submission-agent/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def load_campaign_config() -> dict[str, object]:
    """Load optional campaign config from /data, env JSON, env base64, or URL."""
    config_path = Path(os.environ.get("CAMPAIGN_CONFIG_PATH", "/data/config/campaign.json"))
    config_json = os.environ.get("CAMPAIGN_CONFIG_JSON", "").strip()
    config_b64 = os.environ.get("CAMPAIGN_CONFIG_B64", "").strip()
    config_url = os.environ.get("CAMPAIGN_CONFIG_URL", "").strip()

    if config_json:
        return json.loads(config_json)
    if config_b64:
        return json.loads(base64.b64decode(config_b64).decode("utf-8"))
    if config_url:
        return read_json_from_url(config_url)
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def flatten_campaign_config(config: dict[str, object]) -> dict[str, object]:
    """Accept nested campaign config while keeping env application simple."""
    flattened: dict[str, object] = {}
    for key, value in config.items():
        if key in {"sender", "runtime", "queue", "status"} and isinstance(value, dict):
            for child_key, child_value in value.items():
                flattened[f"{key}_{child_key}"] = child_value
        else:
            flattened[key] = value

    aliases = {
        "queue_csv": "source_csv",
        "queue_source_csv": "source_csv",
        "queue_url": "queue_csv_url",
        "runtime_agent_timeout_seconds": "agent_timeout_seconds",
        "runtime_batch_limit": "batch_limit",
        "runtime_browser_channel": "browser_channel",
        "runtime_delay_seconds": "delay_seconds",
        "runtime_dry_run": "dry_run",
        "runtime_headless": "headless",
        "runtime_loop_sleep_seconds": "loop_sleep_seconds",
        "runtime_review_before_submit": "review_before_submit",
        "runtime_run_mode": "run_mode",
        "runtime_stop_after_successes": "stop_after_successes",
        "sender_postal": "sender_postal_code",
        "sender_zip": "sender_postal_code",
        "status_auth_token": "status_auth_token",
        "status_enabled": "status_server_enabled",
        "status_host": "status_host",
        "status_port": "status_port",
    }
    for old_key, new_key in aliases.items():
        if old_key in flattened and new_key not in flattened:
            flattened[new_key] = flattened[old_key]
    return flattened


def apply_campaign_config(config: dict[str, object]) -> None:
    flattened = flatten_campaign_config(config)
    applied: list[str] = []
    for config_key, env_name in CONFIG_ENV_MAP.items():
        if config_key not in flattened:
            continue
        value = flattened[config_key]
        if value is None:
            continue
        if isinstance(value, bool):
            env_value = "true" if value else "false"
        elif isinstance(value, (dict, list)):
            env_value = json.dumps(value, ensure_ascii=True)
        else:
            env_value = str(value)
        os.environ[env_name] = env_value
        applied.append(env_name)

    if applied:
        safe_applied: list[str] = []
        for name in sorted(applied):
            if name in SENSITIVE_CONFIG_KEYS:
                safe_applied.append(f"{name}={'SET' if os.environ.get(name, '') else 'EMPTY'}")
            else:
                safe_applied.append(name)
        log_event("campaign_config_applied", keys=safe_applied)


def load_and_apply_campaign_config() -> None:
    try:
        config = load_campaign_config()
    except Exception as exc:
        log_event("campaign_config_error", error=str(exc), error_type=type(exc).__name__)
        raise
    if config:
        apply_campaign_config(config)
    else:
        log_event(
            "campaign_config_not_found",
            path=os.environ.get("CAMPAIGN_CONFIG_PATH", "/data/config/campaign.json"),
        )


def apply_mobile_home_resume_override() -> None:
    """Keep the production mobile-home service on the approved resume point.

    Coolify may still have an older CAMPAIGN_CONFIG_B64 set for this service.
    That config points at an exhausted state file, so force the known live
    resume settings after config load without touching secrets.
    """
    if os.environ.get("CAMPAIGN_NAME", "mobile-home").strip().lower() != "mobile-home":
        return
    if env_bool("DISABLE_MOBILE_HOME_RESUME_OVERRIDE", False):
        return
    os.environ["SOURCE_CSV"] = "/data/input/mobile-home-full-queue.csv"
    os.environ["QUEUE_SKIP_ROWS"] = "6426"
    os.environ["STATE_FILE"] = "/data/state/mobile-home-resume-after-6426-state.json"
    os.environ["RUN_MODE"] = "loop"
    os.environ["DRY_RUN"] = "false"
    os.environ["REVIEW_BEFORE_SUBMIT"] = "false"
    log_event(
        "mobile_home_resume_override_applied",
        source_csv=os.environ["SOURCE_CSV"],
        queue_skip_rows=os.environ["QUEUE_SKIP_ROWS"],
        state_file=os.environ["STATE_FILE"],
    )


def normalize_domain(url: str | None) -> str:
    raw = str(url or "").strip()
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
        fieldnames = []
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


def ensure_source_csv(path: Path) -> None:
    """Create the queue CSV from env when a mounted file is not available."""
    if path.exists():
        log_event("queue_exists", path=str(path), bytes=path.stat().st_size)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    queue_b64 = os.environ.get("QUEUE_CSV_B64", "").strip()
    queue_text = os.environ.get("QUEUE_CSV_TEXT", "").strip()
    queue_url = os.environ.get("QUEUE_CSV_URL", "").strip()

    if queue_b64:
        log_event("queue_from_b64_start", path=str(path), chars=len(queue_b64))
        path.write_bytes(base64.b64decode(queue_b64))
        log_event("queue_from_b64_done", path=str(path), bytes=path.stat().st_size)
        return

    if queue_text:
        log_event("queue_from_text_start", path=str(path), chars=len(queue_text))
        path.write_text(queue_text, encoding="utf-8")
        log_event("queue_from_text_done", path=str(path), bytes=path.stat().st_size)
        return

    if queue_url:
        log_event("queue_download_start", path=str(path), url_host=urlparse(queue_url).netloc)
        request = Request(queue_url, headers={"User-Agent": "website-submission-agent/1.0"})
        with urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
        log_event("queue_download_done", path=str(path), bytes=path.stat().st_size)
        return

    raise FileNotFoundError(
        f"Source queue not found: {path}. Provide SOURCE_CSV on /data, QUEUE_CSV_B64, QUEUE_CSV_TEXT, or QUEUE_CSV_URL."
    )


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"attempted_domains": [], "runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(f".corrupt-{int(time.time())}.json")
        shutil.copy2(path, backup)
        return {"attempted_domains": [], "runs": [], "corrupt_backup": str(backup)}


def save_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def pick_batch(source_rows: list[dict[str, str]], attempted: set[str], limit: int) -> list[dict[str, str]]:
    picked: list[dict[str, str]] = []
    seen = set(attempted)
    skip_rows = int(os.environ.get("QUEUE_SKIP_ROWS", "0") or "0")
    for row in source_rows[skip_rows:]:
        domain = normalize_domain(row.get("website") or row.get("url"))
        if not domain or domain in seen:
            continue
        seen.add(domain)
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def read_agent_results(batch_domains: set[str]) -> list[dict[str, object]]:
    if not AGENT_LOG.exists():
        return []
    try:
        rows = json.loads(AGENT_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        domain = normalize_domain(str(row.get("url") or row.get("website") or row.get("contact_url") or ""))
        if domain and domain in batch_domains:
            latest[domain] = row
    return list(latest.values())


def row_status(row: dict[str, object]) -> str:
    for key in ("status", "outcome", "result", "submission_status", "final_status", "phase"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def row_likely_success(row: dict[str, object]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in row).lower()
    negative = ("fail", "error", "blocked", "skip", "no form", "no_form", "validation", "captcha_failed", "timeout")
    positive = ("success", "submitted", "thank you", "received", "sent")
    return any(token in text for token in positive) and not any(token in text for token in negative)


def summarize_all_results(results_root: Path) -> dict[str, object]:
    files = sorted(results_root.glob("*/results.csv"))
    status_counts: Counter[str] = Counter()
    total_rows = 0
    likely_success = 0
    rows_with_after_screenshot = 0
    rows_with_contact_details = 0
    last_run_dir = ""

    for path in files:
        last_run_dir = str(path.parent)
        try:
            rows = read_csv(path)
        except Exception as exc:
            status_counts[f"read_error:{type(exc).__name__}"] += 1
            continue
        for row in rows:
            total_rows += 1
            status_counts[row_status(row)] += 1
            if row_likely_success(row):
                likely_success += 1
            if str(row.get("screenshot_after") or row.get("after_screenshot") or "").strip():
                rows_with_after_screenshot += 1
            if str(row.get("contact_details") or row.get("notes") or row.get("email") or "").strip():
                rows_with_contact_details += 1

    success_rate = round((likely_success / total_rows) * 100, 2) if total_rows else 0.0
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "run_files": len(files),
        "total_result_rows": total_rows,
        "likely_successful_submissions": likely_success,
        "likely_success_rate_percent": success_rate,
        "rows_with_after_screenshot": rows_with_after_screenshot,
        "rows_with_contact_details": rows_with_contact_details,
        "status_counts": dict(status_counts.most_common()),
        "last_run_dir": last_run_dir,
    }


def write_latest_summary(summary: dict[str, object], result: dict[str, object] | None = None) -> None:
    payload = dict(summary)
    if result is not None:
        payload["last_worker_result"] = result
    summary_file = Path(os.environ.get("SUMMARY_FILE", "/data/state/latest-summary.json"))
    write_json_atomic(summary_file, payload)


def write_worker_status(status: str, **fields: object) -> None:
    status_file = Path(os.environ.get("WORKER_STATUS_FILE", "/data/state/latest-worker-status.json"))
    payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    write_json_atomic(status_file, payload)


def copy_screenshots(run_dir: Path, result_rows: list[dict[str, object]]) -> None:
    screenshot_dir = run_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    for row in result_rows:
        for key in ("screenshot_before", "screenshot_after", "review_screenshot"):
            value = str(row.get(key) or "")
            if not value:
                continue
            src = Path(value)
            if src.exists():
                shutil.copy2(src, screenshot_dir / src.name)


def build_command(batch_csv: Path, run_id: str, limit: int) -> list[str]:
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(AGENT),
        "--batch",
        str(batch_csv),
        "--limit",
        str(limit),
        "--browser-channel",
        os.environ.get("BROWSER_CHANNEL", "chromium"),
    ]
    if env_bool("HEADLESS", True):
        cmd.append("--headless")
    cmd.extend(
        [
            "--profile-suffix",
            run_id,
            "--name",
            os.environ.get("SENDER_NAME", ""),
            "--email",
            os.environ.get("SENDER_EMAIL", ""),
            "--phone",
            os.environ.get("SENDER_PHONE", ""),
            "--sender-address",
            os.environ.get("SENDER_ADDRESS", "1455 Clearview Drive"),
            "--sender-city",
            os.environ.get("SENDER_CITY", "McKinney"),
            "--sender-state",
            os.environ.get("SENDER_STATE", "TX"),
            "--sender-postal-code",
            os.environ.get("SENDER_POSTAL_CODE", "75072"),
            "--subject",
            os.environ.get("SUBJECT", "Michigan mobile home case study"),
            "--delay",
            os.environ.get("DELAY_SECONDS", "3"),
        ]
    )
    template_flag = os.environ.get("TEMPLATE_FLAG", "--exact-mobile-home-template").strip()
    if template_flag and template_flag.lower() not in {"0", "false", "none", "off"}:
        cmd.append(template_flag)
    message = os.environ.get("MESSAGE", "").strip()
    if message:
        cmd.extend(["--message", message])
    if env_bool("DRY_RUN"):
        cmd.append("--dry-run")
    if env_bool("REVIEW_BEFORE_SUBMIT"):
        cmd.append("--review-before-submit")
    stop_after = os.environ.get("STOP_AFTER_SUCCESSES", "").strip()
    if stop_after:
        cmd.extend(["--stop-after-successes", stop_after])
    return cmd


def run_once() -> dict[str, object]:
    source_csv = Path(os.environ.get("SOURCE_CSV", "/data/input/mobile-home-strict-form-submission-queue.csv"))
    results_root = Path(os.environ.get("RESULTS_ROOT", "/data/runs"))
    state_file = Path(os.environ.get("STATE_FILE", "/data/state/mobile-home-worker-state.json"))
    limit = int(os.environ.get("BATCH_LIMIT", "25"))
    timeout_seconds = int(os.environ.get("AGENT_TIMEOUT_SECONDS", "1800"))

    log_event(
        "run_once_start",
        campaign=os.environ.get("CAMPAIGN_NAME", "mobile-home"),
        source_csv=str(source_csv),
        state_file=str(state_file),
        limit=limit,
        mode=os.environ.get("RUN_MODE", "once"),
        dry_run=env_bool("DRY_RUN"),
    )
    write_worker_status(
        "running",
        campaign=os.environ.get("CAMPAIGN_NAME", "mobile-home"),
        source_csv=str(source_csv),
        state_file=str(state_file),
        limit=limit,
    )
    ensure_source_csv(source_csv)
    if not os.environ.get("SENDER_NAME") or not os.environ.get("SENDER_EMAIL"):
        raise RuntimeError("SENDER_NAME and SENDER_EMAIL are required")

    state = load_state(state_file)
    attempted = set(str(domain) for domain in state.get("attempted_domains", []))
    source_rows = read_csv(source_csv)
    log_event("queue_loaded", rows=len(source_rows), attempted=len(attempted))
    batch_rows = pick_batch(source_rows, attempted, limit)
    if not batch_rows:
        log_event("batch_empty", rows=len(source_rows), attempted=len(attempted))
        return {"status": "exhausted", "picked": 0}

    run_prefix = os.environ.get("RUN_ID_PREFIX", "mh").strip() or "mh"
    run_id = datetime.now(timezone.utc).strftime(f"{run_prefix}-%Y%m%d-%H%M%S")
    run_dir = results_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    batch_csv = run_dir / "input.csv"
    write_csv(batch_csv, batch_rows)
    batch_domains = {
        normalize_domain(row.get("website") or row.get("url"))
        for row in batch_rows
        if normalize_domain(row.get("website") or row.get("url"))
    }
    log_event("batch_picked", run_id=run_id, picked=len(batch_rows), domains=sorted(batch_domains)[:5])

    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    started = time.time()
    cmd = build_command(batch_csv, run_id, limit)
    log_event("agent_start", run_id=run_id, timeout_seconds=timeout_seconds, batch_csv=str(batch_csv))
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        try:
            proc = subprocess.run(cmd, cwd=APP_ROOT, stdout=stdout, stderr=stderr, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            log_event("agent_timeout", run_id=run_id, timeout_seconds=timeout_seconds)
            raise

    result_rows = read_agent_results(batch_domains)
    log_event("agent_done", run_id=run_id, returncode=proc.returncode, result_rows=len(result_rows))
    write_csv(run_dir / "results.csv", result_rows)
    copy_screenshots(run_dir, result_rows)
    if AGENT_LOG.exists():
        shutil.copy2(AGENT_LOG, run_dir / "plumbing_website_submission_log.json")

    attempted.update(batch_domains)
    state["attempted_domains"] = sorted(attempted)
    runs = list(state.get("runs", []))
    runs.append(
        {
            "run_id": run_id,
            "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
            "duration_seconds": round(time.time() - started, 1),
            "returncode": proc.returncode,
            "input_count": len(batch_rows),
            "logged_count": len(result_rows),
            "run_dir": str(run_dir),
        }
    )
    state["runs"] = runs
    save_state(state_file, state)
    return runs[-1]


class StatusHandler(BaseHTTPRequestHandler):
    server_version = "WebsiteSubmissionWorker/1.0"

    def _authorized(self) -> bool:
        token = os.environ.get("STATUS_AUTH_TOKEN", "").strip()
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        query_token = parse_qs(urlsplit(self.path).query).get("token", [""])[0]
        return header == f"Bearer {token}" or query_token == token

    def _send_json(self, status: int, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_file(self, path: Path) -> object:
        if not path.exists():
            return {"status": "missing", "path": str(path)}
        return json.loads(path.read_text(encoding="utf-8"))

    def _tail_events(self, path: Path, limit: int = 100) -> list[dict[str, object]]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        events: list[dict[str, object]] = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"raw": line})
        return events

    def do_GET(self) -> None:
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return

        path = urlsplit(self.path).path.rstrip("/") or "/"
        try:
            if path in {"/", "/health"}:
                self._send_json(200, {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})
            elif path == "/summary":
                self._send_json(200, self._read_json_file(Path(os.environ.get("SUMMARY_FILE", "/data/state/latest-summary.json"))))
            elif path == "/status":
                self._send_json(200, self._read_json_file(Path(os.environ.get("WORKER_STATUS_FILE", "/data/state/latest-worker-status.json"))))
            elif path == "/events":
                self._send_json(200, self._tail_events(Path(os.environ.get("WORKER_EVENTS_FILE", "/data/state/worker-events.jsonl"))))
            else:
                self._send_json(404, {"error": "not_found"})
        except Exception as exc:
            self._send_json(500, {"error": str(exc), "error_type": type(exc).__name__})

    def log_message(self, format: str, *args: object) -> None:
        return


def start_status_server() -> None:
    if not env_bool("STATUS_SERVER_ENABLED", False):
        return
    host = os.environ.get("STATUS_HOST", "0.0.0.0")
    port = int(os.environ.get("STATUS_PORT", "8080"))

    def serve() -> None:
        try:
            server = ThreadingHTTPServer((host, port), StatusHandler)
            log_event(
                "status_server_start",
                host=host,
                port=port,
                auth_enabled=bool(os.environ.get("STATUS_AUTH_TOKEN", "").strip()),
            )
            server.serve_forever()
        except Exception as exc:
            log_event("status_server_error", error=str(exc), error_type=type(exc).__name__)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()


def main() -> int:
    load_and_apply_campaign_config()
    apply_mobile_home_resume_override()
    start_status_server()
    mode = os.environ.get("RUN_MODE", "once").strip().lower()
    sleep_seconds = int(os.environ.get("LOOP_SLEEP_SECONDS", "300"))
    while True:
        try:
            result = run_once()
            print(json.dumps(result, indent=2), flush=True)
            summary = summarize_all_results(Path(os.environ.get("RESULTS_ROOT", "/data/runs")))
            write_latest_summary(summary, result)
            write_worker_status("idle", last_worker_result=result, latest_summary=summary)
            log_event("aggregate_summary", **summary)
            if result.get("status") == "exhausted":
                return 0
        except Exception as exc:
            error_payload = {"status": "error", "error": str(exc), "error_type": type(exc).__name__}
            print(json.dumps(error_payload, indent=2), flush=True)
            log_event("worker_error", **error_payload)
            try:
                write_worker_status("error", **error_payload)
            except Exception:
                pass
            if mode != "loop":
                return 1
        if mode != "loop":
            return 0
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
