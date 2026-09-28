from __future__ import annotations

import argparse
from scripts.api_clients import TavilySearch
from scripts.common import ASSOCIATION_FIELDS, compact_text, write_csv


def association_queries(niche: str, city: str = "", state: str = "", year: str = "") -> list[str]:
    terms = [
        f'"{niche}" association "{city}" events',
        f'"{niche}" society "{state}" conference',
        f'site:.org "{niche}" "{city}" "events"',
        f'site:.org "{niche}" "{state}" "annual meeting" {year}',
        f'"{niche}" professional association "{city}"',
    ]
    return [" ".join(q.split()) for q in terms if q.strip()]


def discover_associations(niche: str, city: str = "", state: str = "", year: str = "", max_results: int = 5) -> list[dict]:
    client = TavilySearch()
    rows = []
    for query in association_queries(niche, city, state, year):
        for result in client.search(query, max_results=max_results):
            rows.append({
                "association_name": result.get("title", ""),
                "segment": niche,
                "city": city,
                "state": state,
                "country": "",
                "website": result.get("url", ""),
                "event_calendar_url": result.get("url", "") if "event" in query.lower() else "",
                "member_directory_url": "",
                "linkedin_url": "",
                "facebook_url": "",
                "instagram_url": "",
                "contact_name": "",
                "contact_title": "",
                "email": "",
                "phone": "",
                "source": "tavily_serp",
                "confidence": "needs-manual-verification",
                "evidence": compact_text(result.get("content", ""), 400),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Find professional associations and event calendars.")
    parser.add_argument("--niche", required=True)
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--year", default="")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_csv(args.output, discover_associations(args.niche, args.city, args.state, args.year, args.max_results), ASSOCIATION_FIELDS)


if __name__ == "__main__":
    main()