from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apify_client import fetch_dataset, load_token, read_json, start_actor, wait_for_run, write_json


EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-']+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def chunks(rows: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def unique_email_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out, seen = [], set()
    for row in rows:
        email = (row.get("email") or row.get("best_email") or "").strip().lower()
        if EMAIL_RE.match(email) and email not in seen:
            seen.add(email)
            item = dict(row)
            item["email"] = email
            out.append(item)
    return out


FIELDS = ["batch_id", "email", "business_name", "status", "decision", "score", "raw_json"]


def parse(items: list[dict[str, Any]], batch: list[dict[str, str]], batch_id: int) -> list[dict[str, str]]:
    context = {row["email"]: row for row in batch}
    parsed = []
    for item in items:
        raw = json.dumps(item, ensure_ascii=False, sort_keys=True)
        match = re.search(r"[A-Z0-9._%+\-']+@[A-Z0-9.\-]+\.[A-Z]{2,}", raw, re.I)
        email = match.group(0).lower() if match else ""
        source = context.get(email, {})
        status = str(item.get("smtpStatus") or item.get("status") or item.get("is_reachable") or "")
        decision = str(item.get("decision") or item.get("result") or item.get("verdict") or "")
        parsed.append(
            {
                "batch_id": str(batch_id),
                "email": email,
                "business_name": source.get("business_name", ""),
                "status": status,
                "decision": decision,
                "score": str(item.get("score") or item.get("confidence") or ""),
                "raw_json": raw,
            }
        )
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Checkpointed Apify email verification.")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/email_verification"))
    parser.add_argument("--actor-id", default="ryanclinton~bulk-email-verifier")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--verification-level", default="deep")
    parser.add_argument("--from-email", default="verify@example.com")
    parser.add_argument("--timeout-minutes", type=int, default=30)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = unique_email_rows(read_csv(args.queue))
    batches = chunks(rows, args.batch_size)
    checkpoint_path = args.out_dir / "checkpoint.json"
    checkpoint = read_json(checkpoint_path, {"created_at": now(), "batches": {}})
    pending = [idx for idx in range(len(batches)) if checkpoint["batches"].get(str(idx), {}).get("status") != "SUCCEEDED"]
    selected = pending[:args.max_batches]
    print(json.dumps({"unique_emails": len(rows), "selected_batches": selected}, indent=2))
    if args.dry_run:
        return 0

    token = load_token()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for batch_id in selected:
        batch = batches[batch_id]
        emails = [row["email"] for row in batch]
        entry = {"batch_id": batch_id, "status": "STARTING", "input_count": len(emails), "started_at": now()}
        checkpoint["batches"][str(batch_id)] = entry
        write_json(checkpoint_path, checkpoint)
        payload = {
            "emails": emails,
            "verificationLevel": args.verification_level,
            "fromEmail": args.from_email,
            "smtpPort": 25,
            "timeoutSeconds": 30,
            "checkCatchAll": True,
        }
        run_id = start_actor(args.actor_id, token, payload)
        entry.update({"status": "RUNNING", "run_id": run_id})
        write_json(checkpoint_path, checkpoint)
        status, dataset_id = wait_for_run(run_id, token, args.timeout_minutes, args.poll_seconds)
        entry.update({"status": status, "dataset_id": dataset_id, "finished_at": now()})
        write_json(checkpoint_path, checkpoint)
        if status != "SUCCEEDED":
            continue
        items = fetch_dataset(dataset_id, token, limit=max(100, len(batch) * 2))
        raw_path = args.out_dir / f"raw_batch_{batch_id:05d}.json"
        parsed_path = args.out_dir / f"parsed_batch_{batch_id:05d}.csv"
        write_json(raw_path, items)
        write_csv(parsed_path, parse(items, batch, batch_id), FIELDS)
        entry.update({"raw_path": str(raw_path), "parsed_path": str(parsed_path), "output_count": len(items)})
        write_json(checkpoint_path, checkpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

