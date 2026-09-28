from __future__ import annotations

import argparse
from scripts.api_clients import TavilySearch
from scripts.common import write_csv
from scripts.generate_event_queries import generate_queries


def discover_events(
    niche: str,
    city: str = "",
    state: str = "",
    year: str = "",
    max_results: int = 5,
    association_levels: list[str] | None = None,
) -> list[dict]:
    client = TavilySearch()
    rows = []
    for q in generate_queries(niche=niche, city=city, state=state, year=year, association_levels=association_levels):
        if q["stage"] not in {
            "broad_event_discovery",
            "local_suburb_discovery",
            "local_association_discovery",
            "regional_association_discovery",
            "national_association_discovery",
        }:
            continue
        for result in client.search(q["query"], max_results=max_results):
            rows.append({
                "query": q["query"],
                "stage": q["stage"],
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", ""),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Discover event pages from generated queries using Tavily.")
    parser.add_argument("--niche", required=True)
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--year", default="")
    parser.add_argument("--association-levels", nargs="*", default=[])
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_csv(args.output, discover_events(args.niche, args.city, args.state, args.year, args.max_results, args.association_levels))


if __name__ == "__main__":
    main()
