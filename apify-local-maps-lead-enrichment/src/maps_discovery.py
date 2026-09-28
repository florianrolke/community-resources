from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apify_client import fetch_dataset, load_token, read_json, start_actor, wait_for_run, write_json


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


def build_queries(locations: list[dict[str, str]], terms: list[str]) -> list[str]:
    queries = []
    for location in locations:
        geo_text = location.get("geo_text") or " ".join(
            part for part in [location.get("city"), location.get("county"), location.get("state")] if part
        )
        for term in terms:
            queries.append(f"{term} {geo_text}".strip())
    return queries


def row_from_item(item: dict[str, Any], batch_id: int) -> dict[str, str]:
    categories = item.get("categories") or []
    if isinstance(categories, str):
        categories = [categories]
    return {
        "batch_id": str(batch_id),
        "place_id": str(item.get("placeId") or ""),
        "business_name": str(item.get("name") or ""),
        "address": str(item.get("address") or ""),
        "city": str(item.get("city") or ""),
        "state": str(item.get("state") or ""),
        "postal_code": str(item.get("postalCode") or ""),
        "phone": str(item.get("phone") or ""),
        "phone_intl": str(item.get("phoneInternational") or ""),
        "website": str(item.get("website") or ""),
        "rating": str(item.get("totalScore") or ""),
        "reviews_count": str(item.get("reviewsCount") or ""),
        "claimed": "YES" if item.get("claimedBusiness") else "NO",
        "is_open": "NO" if item.get("permanentlyClosed") else "",
        "google_maps_url": str(item.get("url") or ""),
        "google_categories": "; ".join(str(cat) for cat in categories),
        "latitude": str(item.get("latitude") or ""),
        "longitude": str(item.get("longitude") or ""),
    }


FIELDS = [
    "batch_id",
    "place_id",
    "business_name",
    "address",
    "city",
    "state",
    "postal_code",
    "phone",
    "phone_intl",
    "website",
    "rating",
    "reviews_count",
    "claimed",
    "is_open",
    "google_maps_url",
    "google_categories",
    "latitude",
    "longitude",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic Google Maps lead discovery with Apify checkpoints.")
    parser.add_argument("--config", type=Path, default=Path("config/example_industry.json"))
    parser.add_argument("--locations", type=Path, default=Path("examples/locations.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/maps_discovery"))
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--timeout-minutes", type=int, default=45)
    parser.add_argument("--poll-seconds", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    locations = read_csv(args.locations)
    batch_size = args.batch_size or int(config.get("batch_size_locations", 50))
    batches = chunks(locations, batch_size)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.out_dir / "checkpoint.json"
    checkpoint = read_json(checkpoint_path, {"created_at": now(), "batches": {}})

    pending = [idx for idx in range(len(batches)) if checkpoint["batches"].get(str(idx), {}).get("status") != "SUCCEEDED"]
    selected = pending[:args.max_batches]
    print(json.dumps({"total_locations": len(locations), "total_batches": len(batches), "selected_batches": selected}, indent=2))
    if args.dry_run:
        return 0

    token = load_token()
    for batch_id in selected:
        queries = build_queries(batches[batch_id], config["search_terms"])
        payload = {
            "searchQueries": queries,
            "maxResults": int(config.get("max_results_per_batch", 20000)),
            "language": "en",
        }
        entry = {"batch_id": batch_id, "status": "STARTING", "query_count": len(queries), "started_at": now()}
        checkpoint["batches"][str(batch_id)] = entry
        write_json(checkpoint_path, checkpoint)
        run_id = start_actor(config["maps_actor_id"], token, payload)
        entry.update({"status": "RUNNING", "run_id": run_id})
        write_json(checkpoint_path, checkpoint)
        status, dataset_id = wait_for_run(run_id, token, args.timeout_minutes, args.poll_seconds)
        entry.update({"status": status, "dataset_id": dataset_id, "finished_at": now()})
        write_json(checkpoint_path, checkpoint)
        if status != "SUCCEEDED":
            continue
        items = fetch_dataset(dataset_id, token)
        raw_path = args.out_dir / f"raw_batch_{batch_id:05d}.json"
        parsed_path = args.out_dir / f"parsed_batch_{batch_id:05d}.csv"
        write_json(raw_path, items)
        write_csv(parsed_path, [row_from_item(item, batch_id) for item in items], FIELDS)
        entry.update({"raw_path": str(raw_path), "parsed_path": str(parsed_path), "output_count": len(items)})
        write_json(checkpoint_path, checkpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

