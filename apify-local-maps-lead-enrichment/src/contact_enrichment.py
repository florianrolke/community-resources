from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apify_client import fetch_dataset, load_token, read_json, start_actor, wait_for_run, write_json


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-']+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:(?:\+?1[\s().-]*)?(?:\(?\d{3}\)?[\s().-]*)\d{3}[\s().-]*\d{4})")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def chunks(rows: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def unique(values: list[str]) -> list[str]:
    out, seen = [], set()
    for value in values:
        value = value.strip().strip(".,;:)]}")
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value is None else [value])


def parse_items(items: list[dict[str, Any]], batch: list[dict[str, str]], batch_id: int) -> list[dict[str, str]]:
    rows = []
    for index, item in enumerate(items):
        target = batch[index] if index < len(batch) else {}
        raw = json.dumps(item, ensure_ascii=False)
        contacts = as_list(item.get("contacts"))
        names = []
        for contact in contacts:
            if isinstance(contact, dict):
                name = str(contact.get("name") or contact.get("fullName") or "").strip()
                title = str(contact.get("title") or contact.get("position") or "").strip()
                if name:
                    names.append(f"{name} ({title})" if title else name)
        rows.append(
            {
                "batch_id": str(batch_id),
                "input_url": target.get("website", target.get("input_url", "")),
                "business_name": target.get("business_name", ""),
                "emails": " | ".join(email.lower() for email in unique(EMAIL_RE.findall(raw))),
                "phones": " | ".join(unique(PHONE_RE.findall(raw))),
                "named_contacts": " | ".join(unique(names)),
                "raw_item_index": str(index),
            }
        )
    return rows


FIELDS = ["batch_id", "input_url", "business_name", "emails", "phones", "named_contacts", "raw_item_index"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Website/contact enrichment over known lead websites.")
    parser.add_argument("--queue", type=Path, required=True, help="CSV with website or input_url column.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/contact_enrichment"))
    parser.add_argument("--actor-id", default="rp_openpro.ai~contact-details-scraper")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--timeout-minutes", type=int, default=25)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = [row for row in read_csv(args.queue) if row.get("website") or row.get("input_url")]
    batches = chunks(targets, args.batch_size)
    checkpoint_path = args.out_dir / "checkpoint.json"
    checkpoint = read_json(checkpoint_path, {"created_at": now(), "batches": {}})
    pending = [idx for idx in range(len(batches)) if checkpoint["batches"].get(str(idx), {}).get("status") != "SUCCEEDED"]
    selected = pending[:args.max_batches]
    print(json.dumps({"queue_rows": len(targets), "selected_batches": selected}, indent=2))
    if args.dry_run:
        return 0

    token = load_token()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for batch_id in selected:
        batch = batches[batch_id]
        urls = [row.get("website") or row.get("input_url") for row in batch]
        entry = {"batch_id": batch_id, "status": "STARTING", "input_count": len(urls), "started_at": now()}
        checkpoint["batches"][str(batch_id)] = entry
        write_json(checkpoint_path, checkpoint)
        run_id = start_actor(args.actor_id, token, {"urls": urls, "proxyConfiguration": {"useApifyProxy": True}})
        entry.update({"status": "RUNNING", "run_id": run_id})
        write_json(checkpoint_path, checkpoint)
        status, dataset_id = wait_for_run(run_id, token, args.timeout_minutes, args.poll_seconds)
        entry.update({"status": status, "dataset_id": dataset_id, "finished_at": now()})
        write_json(checkpoint_path, checkpoint)
        if status != "SUCCEEDED":
            continue
        items = fetch_dataset(dataset_id, token, limit=max(1000, len(batch) * 10))
        raw_path = args.out_dir / f"raw_batch_{batch_id:05d}.json"
        parsed_path = args.out_dir / f"parsed_batch_{batch_id:05d}.csv"
        write_json(raw_path, items)
        parsed = parse_items(items, batch, batch_id)
        write_csv(parsed_path, parsed, FIELDS)
        entry.update({"raw_path": str(raw_path), "parsed_path": str(parsed_path), "output_count": len(items)})
        write_json(checkpoint_path, checkpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

