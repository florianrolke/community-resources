#!/usr/bin/env python3
"""Create a ready-to-deploy website form submission campaign package.

This helper is the intake layer above the cloud worker. It turns a client's
sender details, approved message, and lead CSV into a campaign.json plus the
single CAMPAIGN_CONFIG_B64 value used by Coolify.
"""

from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_OUTPUT_ROOT = Path(".tmp") / "campaign-setups"
DEFAULT_EMBED_LIMIT_BYTES = 500_000
WEBSITE_COLUMNS = ("website", "url", "domain")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "campaign"


def normalize_domain(raw: str | None) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    try:
        return urlparse(value).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def read_csv_summary(path: Path) -> tuple[list[str], int, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        domains: set[str] = set()
        rows = 0
        for row in reader:
            rows += 1
            raw = ""
            for col in WEBSITE_COLUMNS:
                if row.get(col):
                    raw = row.get(col, "")
                    break
            domain = normalize_domain(raw)
            if domain:
                domains.add(domain)
    return columns, rows, len(domains)


def require_csv_columns(columns: list[str]) -> None:
    lower = {col.lower() for col in columns}
    if not any(col in lower for col in WEBSITE_COLUMNS):
        joined = ", ".join(columns)
        raise SystemExit(f"Lead CSV needs one of these columns: {', '.join(WEBSITE_COLUMNS)}. Found: {joined}")


def read_message(args: argparse.Namespace) -> str:
    if args.message_file:
        return Path(args.message_file).read_text(encoding="utf-8-sig").strip()
    if args.message:
        return args.message.strip()
    raise SystemExit("Provide --message or --message-file.")


def encode_json(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(normalized).decode("ascii")


def build_campaign_config(args: argparse.Namespace, slug: str, queue_target: str, message: str) -> dict[str, object]:
    config: dict[str, object] = {
        "campaign_name": args.campaign_name,
        "run_id_prefix": args.run_id_prefix or slug[:20],
        "queue": {
            "source_csv": queue_target,
            "url": args.queue_url or "",
        },
        "runtime": {
            "run_mode": args.run_mode,
            "batch_limit": args.batch_limit,
            "loop_sleep_seconds": args.loop_sleep_seconds,
            "agent_timeout_seconds": args.agent_timeout_seconds,
            "browser_channel": args.browser_channel,
            "headless": not args.no_headless,
            "delay_seconds": args.delay_seconds,
            "dry_run": not args.live,
            "review_before_submit": args.review_before_submit,
        },
        "sender": {
            "name": args.sender_name,
            "email": args.sender_email,
            "phone": args.sender_phone,
            "address": args.sender_address,
            "city": args.sender_city,
            "state": args.sender_state,
            "postal_code": args.sender_postal_code,
        },
        "subject": args.subject,
        "template_flag": args.template_flag,
        "message": message,
        "results_root": "/data/runs",
        "state_file": f"/data/state/{slug}-worker-state.json",
        "summary_file": "/data/state/latest-summary.json",
        "worker_status_file": "/data/state/latest-worker-status.json",
        "worker_events_file": "/data/state/worker-events.jsonl",
        "status": {
            "enabled": args.enable_status_server,
            "host": "0.0.0.0",
            "port": args.status_port,
            "auth_token": args.status_auth_token or "",
        },
    }
    if args.stop_after_successes:
        config["runtime"]["stop_after_successes"] = args.stop_after_successes  # type: ignore[index]
    return config


def write_package(args: argparse.Namespace) -> dict[str, object]:
    queue_csv = Path(args.queue_csv).resolve()
    if not queue_csv.exists():
        raise SystemExit(f"Lead CSV not found: {queue_csv}")

    message = read_message(args)
    columns, rows, unique_domains = read_csv_summary(queue_csv)
    require_csv_columns(columns)

    slug = slugify(args.slug or args.campaign_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_root)
    output_dir = output_root / f"{timestamp}-{slug}"
    output_dir.mkdir(parents=True, exist_ok=True)

    queue_name = f"{slug}-queue.csv"
    copied_queue = output_dir / queue_name
    shutil.copy2(queue_csv, copied_queue)

    queue_size = copied_queue.stat().st_size
    queue_mode = args.queue_mode
    if queue_mode == "auto":
        queue_mode = "url" if args.queue_url else ("embed" if queue_size <= args.embed_limit_bytes else "mounted")

    queue_target = f"/data/input/{queue_name}"
    config = build_campaign_config(args, slug, queue_target, message)

    if queue_mode == "embed":
        config["queue_csv_b64"] = base64.b64encode(copied_queue.read_bytes()).decode("ascii")
    elif queue_mode == "url":
        if not args.queue_url:
            raise SystemExit("--queue-mode url requires --queue-url.")
    elif queue_mode == "mounted":
        pass
    else:
        raise SystemExit("--queue-mode must be auto, embed, mounted, or url.")

    config_path = output_dir / "campaign.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=True), encoding="utf-8")

    b64 = encode_json(config)
    (output_dir / "CAMPAIGN_CONFIG_B64.txt").write_text(b64 + "\n", encoding="utf-8")
    (output_dir / "coolify-env.txt").write_text(
        "CAMPAIGN_CONFIG_B64=" + b64 + "\n"
        "# Keep CAPSOLVER_API_KEY as a separate Coolify secret/env var when possible.\n",
        encoding="utf-8",
    )
    (output_dir / "message.txt").write_text(message + "\n", encoding="utf-8")

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "campaign_name": args.campaign_name,
        "slug": slug,
        "queue_mode": queue_mode,
        "queue_rows": rows,
        "unique_domains": unique_domains,
        "queue_size_bytes": queue_size,
        "output_dir": str(output_dir),
        "config_path": str(config_path),
        "queue_copy": str(copied_queue),
        "coolify_env_path": str(output_dir / "coolify-env.txt"),
        "dry_run": not args.live,
        "review_before_submit": args.review_before_submit,
        "mounted_queue_target": queue_target,
    }
    (output_dir / "setup-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    instructions = [
        f"# Campaign Setup: {args.campaign_name}",
        "",
        f"Rows: {rows}",
        f"Unique domains: {unique_domains}",
        f"Queue mode: {queue_mode}",
        f"Dry run: {str(not args.live).lower()}",
        f"Review before submit: {str(args.review_before_submit).lower()}",
        "",
        "## Coolify",
        "",
        "Use the existing website-submission-agent Docker Compose setup.",
        "Set this one env var from `coolify-env.txt`:",
        "",
        "```text",
        "CAMPAIGN_CONFIG_B64=<value from coolify-env.txt>",
        "```",
        "",
        "Keep `CAPSOLVER_API_KEY` as a separate Coolify secret/env var when possible.",
    ]
    if queue_mode == "mounted":
        instructions.extend(
            [
                "",
                "Because the queue is too large to embed cleanly, upload the copied queue CSV to:",
                "",
                f"`{queue_target}`",
            ]
        )
    elif queue_mode == "embed":
        instructions.extend(["", "The queue CSV is embedded in `CAMPAIGN_CONFIG_B64`; no separate queue upload is needed."])
    elif queue_mode == "url":
        instructions.extend(["", f"The worker will download the queue from: `{args.queue_url}`"])

    instructions.extend(
        [
            "",
            "## First Run",
            "",
            "Start with dry-run/review mode unless the user explicitly approved live submissions.",
            "After the first run, check `/data/state/latest-summary.json` and screenshots under `/data/runs/`.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(instructions) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a website form submission campaign package")
    parser.add_argument("--campaign-name", required=True)
    parser.add_argument("--queue-csv", required=True)
    parser.add_argument("--queue-url", default="", help="Direct-download CSV URL used by the cloud worker")
    parser.add_argument("--queue-mode", choices=["auto", "embed", "mounted", "url"], default="auto")
    parser.add_argument("--embed-limit-bytes", type=int, default=DEFAULT_EMBED_LIMIT_BYTES)
    parser.add_argument("--message", default="")
    parser.add_argument("--message-file", default="")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--sender-name", required=True)
    parser.add_argument("--sender-email", required=True)
    parser.add_argument("--sender-phone", default="")
    parser.add_argument("--sender-address", default="")
    parser.add_argument("--sender-city", default="")
    parser.add_argument("--sender-state", default="")
    parser.add_argument("--sender-postal-code", default="")
    parser.add_argument("--template-flag", default="none")
    parser.add_argument("--run-id-prefix", default="")
    parser.add_argument("--slug", default="")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-mode", choices=["once", "loop"], default="loop")
    parser.add_argument("--batch-limit", type=int, default=25)
    parser.add_argument("--loop-sleep-seconds", type=int, default=300)
    parser.add_argument("--agent-timeout-seconds", type=int, default=1800)
    parser.add_argument("--browser-channel", default="chromium")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--delay-seconds", type=int, default=3)
    parser.add_argument("--review-before-submit", action="store_true", default=True)
    parser.add_argument("--no-review-before-submit", dest="review_before_submit", action="store_false")
    parser.add_argument("--live", action="store_true", help="Create config with dry_run=false. Use only after approval.")
    parser.add_argument("--stop-after-successes", type=int, default=0)
    parser.add_argument("--enable-status-server", action="store_true")
    parser.add_argument("--status-port", type=int, default=8080)
    parser.add_argument("--status-auth-token", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    summary = write_package(args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
