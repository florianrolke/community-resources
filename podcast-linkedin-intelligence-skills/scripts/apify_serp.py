from __future__ import annotations

import argparse
import os
from typing import Iterable

from scripts.api_clients import apify_run_sync
from scripts.common import load_env, write_csv

FIELDS = ["query", "rank", "title", "url", "snippet", "source"]


def normalize_serp_items(items: Iterable[dict]) -> list[dict]:
    rows = []
    for item in items:
        query = item.get("searchQuery") or item.get("query") or item.get("keyword") or ""
        organic = item.get("organicResults") or item.get("organic") or item.get("results")
        if isinstance(organic, list):
            for i, result in enumerate(organic, 1):
                url = result.get("url") or result.get("link") or result.get("displayedUrl") or ""
                if not url:
                    continue
                rows.append(
                    {
                        "query": query,
                        "rank": i,
                        "title": result.get("title") or result.get("name") or "",
                        "url": url,
                        "snippet": result.get("description") or result.get("snippet") or result.get("text") or "",
                        "source": "apify_serp",
                    }
                )
            continue

        url = item.get("url") or item.get("link") or ""
        if url:
            rows.append(
                {
                    "query": query,
                    "rank": item.get("position") or item.get("rank") or "",
                    "title": item.get("title") or item.get("name") or "",
                    "url": url,
                    "snippet": item.get("description") or item.get("snippet") or item.get("text") or "",
                    "source": "apify_serp",
                }
            )
    return rows


def apify_serp_search(queries: list[str], max_pages_per_query: int = 1, results_per_page: int = 10, actor_id: str | None = None) -> list[dict]:
    load_env()
    actor = actor_id or os.getenv("APIFY_SERP_ACTOR", "apify/google-search-scraper")
    payload = {
        "queries": "\n".join(queries),
        "maxPagesPerQuery": max_pages_per_query,
        "resultsPerPage": results_per_page,
        "csvFriendlyOutput": False,
    }
    return normalize_serp_items(apify_run_sync(actor, payload))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Apify SERP searches and normalize organic results.")
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-pages-per-query", type=int, default=1)
    parser.add_argument("--results-per-page", type=int, default=10)
    parser.add_argument("--actor-id")
    args = parser.parse_args()
    rows = apify_serp_search(args.query, args.max_pages_per_query, args.results_per_page, args.actor_id)
    write_csv(args.output, rows, FIELDS)
    print(f"Rows written: {len(rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
