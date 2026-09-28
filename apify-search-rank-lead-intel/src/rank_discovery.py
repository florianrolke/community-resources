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


def build_query_rows(locations: list[dict[str, str]], terms: list[str]) -> list[dict[str, str]]:
    rows = []
    for location in locations:
        geo_text = location.get("geo_text") or " ".join(
            part for part in [location.get("city"), location.get("county"), location.get("state")] if part
        )
        for term in terms:
            rows.append(
                {
                    "input_query": f"{term} {geo_text}".strip(),
                    "query_term": term,
                    "query_location": geo_text,
                    "query_city": location.get("city", ""),
                    "query_county": location.get("county", ""),
                    "query_state": location.get("state", ""),
                    "query_state_abbr": location.get("state_abbr", ""),
                }
            )
    return rows


def rank_bucket(rank: int, buckets: dict[str, int]) -> str:
    if rank <= int(buckets.get("top_3", 3)):
        return "top_3"
    if rank <= int(buckets.get("top_10", 10)):
        return "top_10"
    if rank <= int(buckets.get("top_20", 20)):
        return "top_20"
    return "below_20"


def confidence(item: dict[str, Any], include_terms: list[str], exclude_terms: list[str]) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in ["name", "categoryName", "categories", "description", "address"]
    ).lower()
    if any(term.lower() in text for term in exclude_terms):
        return "reject"
    hits = sum(term.lower() in text for term in include_terms)
    if hits >= 2:
        return "high"
    if hits == 1:
        return "medium"
    return "review"


def item_rows(items: list[dict[str, Any]], query_rows: list[dict[str, str]], config: dict[str, Any], batch_id: int) -> list[dict[str, str]]:
    parsed = []
    buckets = config.get("rank_buckets", {})
    include_terms = config.get("include_terms", [])
    exclude_terms = config.get("exclude_terms", [])
    fallback_query = query_rows[0] if query_rows else {}
    ranks_by_query: dict[str, int] = {}
    for item in items:
        query_value = ""
        search_query = item.get("searchQuery")
        if isinstance(search_query, dict):
            query_value = str(search_query.get("term") or search_query.get("query") or "")
        elif search_query:
            query_value = str(search_query)
        query = next((row for row in query_rows if row["input_query"] == query_value), fallback_query)
        ranks_by_query[query["input_query"]] = ranks_by_query.get(query["input_query"], 0) + 1
        rank = int(item.get("rank") or item.get("position") or ranks_by_query[query["input_query"]])
        categories = item.get("categories") or []
        if isinstance(categories, str):
            categories = [categories]
        parsed.append(
            {
                "batch_id": str(batch_id),
                "input_query": query.get("input_query", query_value),
                "query_term": query.get("query_term", ""),
                "query_location": query.get("query_location", ""),
                "query_city": query.get("query_city", ""),
                "query_county": query.get("query_county", ""),
                "query_state": query.get("query_state", ""),
                "result_rank": str(rank),
                "rank_bucket": rank_bucket(rank, buckets),
                "place_id": str(item.get("placeId") or ""),
                "business_name": str(item.get("name") or ""),
                "category_name": str(item.get("categoryName") or ""),
                "google_categories": "; ".join(str(cat) for cat in categories),
                "address": str(item.get("address") or ""),
                "city": str(item.get("city") or ""),
                "state": str(item.get("state") or ""),
                "phone": str(item.get("phone") or ""),
                "website": str(item.get("website") or ""),
                "rating": str(item.get("totalScore") or ""),
                "reviews_count": str(item.get("reviewsCount") or ""),
                "claimed": "YES" if item.get("claimedBusiness") else "NO",
                "google_maps_url": str(item.get("url") or ""),
                "reseller_confidence": confidence(item, include_terms, exclude_terms),
            }
        )
    return parsed


FIELDS = [
    "batch_id",
    "input_query",
    "query_term",
    "query_location",
    "query_city",
    "query_county",
    "query_state",
    "result_rank",
    "rank_bucket",
    "place_id",
    "business_name",
    "category_name",
    "google_categories",
    "address",
    "city",
    "state",
    "phone",
    "website",
    "rating",
    "reviews_count",
    "claimed",
    "google_maps_url",
    "reseller_confidence",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Checkpointed Apify Maps ranking intelligence.")
    parser.add_argument("--config", type=Path, default=Path("config/example_rank_intel.json"))
    parser.add_argument("--locations", type=Path, default=Path("examples/locations.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/rank_discovery"))
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--timeout-minutes", type=int, default=45)
    parser.add_argument("--poll-seconds", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    locations = read_csv(args.locations)
    query_rows = build_query_rows(locations, config["search_terms"])
    batch_size = args.batch_size or int(config.get("batch_size_queries", 100))
    batches = chunks(query_rows, batch_size)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.out_dir / "checkpoint.json"
    checkpoint = read_json(checkpoint_path, {"created_at": now(), "batches": {}})
    pending = [idx for idx in range(len(batches)) if checkpoint["batches"].get(str(idx), {}).get("status") != "SUCCEEDED"]
    selected = pending[:args.max_batches]
    print(json.dumps({"query_count": len(query_rows), "total_batches": len(batches), "selected_batches": selected}, indent=2))
    if args.dry_run:
        return 0

    token = load_token()
    for batch_id in selected:
        batch = batches[batch_id]
        payload = {
            "searchQueries": [row["input_query"] for row in batch],
            "maxResults": int(config.get("max_results_per_query", 20)) * len(batch),
            "language": "en",
        }
        entry = {"batch_id": batch_id, "status": "STARTING", "query_count": len(batch), "started_at": now()}
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
        write_json(raw_path, {"query_rows": batch, "items": items})
        parsed = item_rows(items, batch, config, batch_id)
        write_csv(parsed_path, parsed, FIELDS)
        entry.update({"raw_path": str(raw_path), "parsed_path": str(parsed_path), "output_count": len(items)})
        write_json(checkpoint_path, checkpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

