"""
Free-tier Apify fallback for live event discovery.

Uses apify/google-search-scraper (official actor, available on free-tier accounts)
instead of paid third-party actors (10times, Eventbrite, scraperlink) which require
a paid Apify subscription and return 403 on free accounts.

Same interface as discover_events_serp.py — drop-in replacement when Tavily keys
are exhausted OR Apify account is on a free plan.

Output CSV is compatible with normalize_events.py → dedupe_events.py → rank_opportunities.py.
Runs queries in parallel (default 5 workers) to keep runtime under 3 minutes for 70+ queries.
"""
from __future__ import annotations

import argparse
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from scripts.api_clients import env_keys
from scripts.common import load_env, write_csv
from scripts.generate_event_queries import generate_queries

SERP_FIELDS = ["query", "stage", "title", "url", "snippet"]

ACTIVE_STAGES = {
    "broad_event_discovery",
    "local_suburb_discovery",
    "local_association_discovery",
    "regional_association_discovery",
    "national_association_discovery",
    "industry_trade_association",
}

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg)


def _get_token() -> str:
    load_env()
    token = next(iter(env_keys("APIFY_API_TOKEN", preferred=["7", "6", "5", "4", "3", "2", ""])), "")
    if not token:
        raise RuntimeError("No APIFY_API_TOKEN found in environment")
    return token


def run_query(token: str, query: str, stage: str, results_per_page: int = 10) -> list[dict]:
    try:
        response = requests.post(
            "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items",
            params={"token": token},
            json={"queries": query, "maxPagesPerQuery": 1, "resultsPerPage": results_per_page},
            timeout=120,
        )
        response.raise_for_status()
        rows = []
        for page in response.json():
            for r in page.get("organicResults", []):
                rows.append({
                    "query": query,
                    "stage": stage,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                })
        _log(f"  [{stage}] {query[:70]} -> {len(rows)} results")
        return rows
    except Exception as e:
        _log(f"  [{stage}] {query[:70]} -> ERROR: {e}")
        return []


def discover_events(
    niche: str,
    city: str = "",
    state: str = "",
    year: str = "",
    association_levels: list[str] | None = None,
    known_associations: list[str] | None = None,
    results_per_page: int = 10,
    workers: int = 5,
) -> list[dict]:
    token = _get_token()

    all_queries = generate_queries(
        niche=niche,
        city=city,
        state=state,
        year=year,
        association_levels=association_levels,
        known_associations=known_associations,
    )
    queries = [q for q in all_queries if q["stage"] in ACTIVE_STAGES]
    print(f"Running {len(queries)} queries across {len({q['stage'] for q in queries})} stages ({workers} workers)...")

    all_rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_query, token, q["query"], q["stage"], results_per_page): q
            for q in queries
        }
        for future in as_completed(futures):
            all_rows.extend(future.result())

    print(f"\nTotal raw rows: {len(all_rows)}")
    return all_rows


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Discover events via Google SERP — free-tier Apify fallback. "
            "Same interface as discover_events_serp.py. "
            "Defaults to local + regional + national + trade association coverage."
        )
    )
    parser.add_argument("--niche", required=True, help="Industry or niche e.g. 'plumbing HVAC contractor'")
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--year", default="")
    parser.add_argument(
        "--association-levels", nargs="*", default=["local", "regional", "national"],
        help="Coverage levels: local regional national (all enabled by default)"
    )
    parser.add_argument(
        "--known-associations", nargs="*", default=[],
        help="Specific trade/industry associations e.g. 'PHCC' 'ACCA' 'ASHRAE'"
    )
    parser.add_argument("--results-per-page", type=int, default=10)
    parser.add_argument("--workers", type=int, default=5, help="Parallel query workers (default 5)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = discover_events(
        niche=args.niche,
        city=args.city,
        state=args.state,
        year=args.year,
        association_levels=args.association_levels,
        known_associations=args.known_associations,
        results_per_page=args.results_per_page,
        workers=args.workers,
    )
    write_csv(args.output, rows, SERP_FIELDS)
    print(f"Saved {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
