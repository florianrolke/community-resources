from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_many(input_dir: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(input_dir.glob("parsed_batch_*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Roll up ranking appearances by company/place.")
    parser.add_argument("--input-dir", type=Path, default=Path("outputs/rank_discovery"))
    parser.add_argument("--out", type=Path, default=Path("outputs/rank_rollup/company_rollup.csv"))
    parser.add_argument("--accepted-confidence", default="high,medium")
    args = parser.parse_args()

    accepted = {value.strip() for value in args.accepted_confidence.split(",") if value.strip()}
    rows = [row for row in read_many(args.input_dir) if row.get("reseller_confidence") in accepted]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = row.get("place_id") or f"{row.get('business_name')}|{row.get('phone')}"
        grouped[key].append(row)

    out = []
    for key, items in grouped.items():
        ranks = [int(row.get("result_rank") or 999) for row in items]
        first = sorted(items, key=lambda row: int(row.get("result_rank") or 999))[0]
        out.append(
            {
                "company_key": key,
                "business_name": first.get("business_name", ""),
                "place_id": first.get("place_id", ""),
                "best_rank": str(min(ranks)),
                "ranking_appearances": str(len(items)),
                "top_3_appearances": str(sum(row.get("rank_bucket") == "top_3" for row in items)),
                "top_10_appearances": str(sum(row.get("rank_bucket") in {"top_3", "top_10"} for row in items)),
                "locations_seen": " | ".join(sorted({row.get("query_location", "") for row in items if row.get("query_location")})),
                "queries_seen": " | ".join(sorted({row.get("input_query", "") for row in items if row.get("input_query")})),
                "phone": first.get("phone", ""),
                "website": first.get("website", ""),
                "category_name": first.get("category_name", ""),
                "reseller_confidence": first.get("reseller_confidence", ""),
            }
        )
    fields = [
        "company_key",
        "business_name",
        "place_id",
        "best_rank",
        "ranking_appearances",
        "top_3_appearances",
        "top_10_appearances",
        "locations_seen",
        "queries_seen",
        "phone",
        "website",
        "category_name",
        "reseller_confidence",
    ]
    write_csv(args.out, sorted(out, key=lambda row: (int(row["best_rank"]), row["business_name"])), fields)
    print(f"Wrote {len(out)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

