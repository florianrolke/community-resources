from __future__ import annotations

import argparse
import json
from scripts.common import write_csv, write_json


def _clean(values):
    return [v.strip() for v in values or [] if v and v.strip()]


def generate_queries(
    niche: str,
    city: str = "",
    state: str = "",
    year: int | str = "",
    event_name: str = "",
    adjacent_niches: list[str] | None = None,
    asset_terms: list[str] | None = None,
    official_domains: list[str] | None = None,
    industry_publications: list[str] | None = None,
    companies: list[str] | None = None,
    people: list[str] | None = None,
    suburbs: list[str] | None = None,
    association_levels: list[str] | None = None,
    known_associations: list[str] | None = None,
) -> list[dict[str, str]]:
    year = str(year or "").strip()
    queries: list[dict[str, str]] = []

    def add(stage: str, query: str, intent: str):
        query = " ".join(query.split())
        if query and query not in {q["query"] for q in queries}:
            queries.append({"stage": stage, "query": query, "intent": intent})

    if niche and year:
        add("broad_event_discovery", f"{niche} conference {year}", "Find national or niche conferences")
        add("broad_event_discovery", f"{niche} events {year}", "Find event roundups and calendars")
        add("broad_event_discovery", f"{niche} expo {year}", "Find expos and trade shows")
    for term in _clean(adjacent_niches):
        add("broad_event_discovery", f"{term} conference {year}".strip(), "Find adjacent ecosystem events")
    for term in _clean(asset_terms):
        add("broad_event_discovery", f"{term} conference {year}".strip(), "Find asset/business-model events")
    for domain in _clean(official_domains):
        add("official_source_discovery", f"site:{domain} events {year}".strip(), "Find official event calendar")
        add("official_source_discovery", f"site:{domain} annual meeting {year}".strip(), "Find annual meetings")
        add("official_source_discovery", f"site:{domain} convention {year}".strip(), "Find conventions")
    for domain in _clean(industry_publications):
        add("official_source_discovery", f"site:{domain} events {niche} {year}".strip(), "Find industry publication event lists")

    if event_name:
        for suffix, intent in [
            ("speakers", "Find speakers"),
            ("exhibitors", "Find exhibitors"),
            ("sponsors", "Find sponsors"),
            ("attendees LinkedIn", "Find public attendee snippets"),
            ("agenda speakers", "Find agenda and session speakers"),
            ("app exhibitors sponsors", "Find app-gated list references"),
        ]:
            add("named_event_research", f"{event_name} {suffix} {year}".strip(), intent)
        for company in _clean(companies):
            add("attendance_post_snippets", f'"{event_name}" "LinkedIn" "{company}"', "Find public LinkedIn snippets")
            add("attendance_post_snippets", f'"{event_name}" "exhibiting" "{company}"', "Find booth/exhibitor posts")
            add("attendance_post_snippets", f'"{event_name}" "booth" "{company}"', "Find booth numbers")

    for person in _clean(people):
        parts = [p.strip() for p in person.split("|", 1)]
        name = parts[0]
        qualifier = parts[1] if len(parts) > 1 else niche
        add("person_linkedin_lookup", f'site:linkedin.com/in "{name}" "{qualifier}"', "Find personal LinkedIn profile")
        add("person_linkedin_lookup", f'"{name}" LinkedIn "{qualifier}"', "Fallback personal LinkedIn lookup")
    for company in _clean(companies):
        add("company_linkedin_lookup", f'site:linkedin.com/company "{company}" LinkedIn', "Find company LinkedIn page")
        if niche:
            add("company_linkedin_lookup", f'site:linkedin.com/company "{company}" "{niche}"', "Find company page with niche evidence")
        add("company_linkedin_lookup", f'"{company}" LinkedIn company', "Fallback company LinkedIn lookup")

    places = _clean(suburbs) or _clean([city])
    for place in places:
        if niche:
            add("local_suburb_discovery", f'"{niche}" events "{place}"', "Find local niche events")
            add("local_suburb_discovery", f'"{niche}" conference "{place}"', "Find local conferences")
            add("local_suburb_discovery", f'"{niche}" association "{place}" events', "Find local association events")
            add("local_suburb_discovery", f'site:.org "{niche}" "{place}" "events"', "Find nonprofit/association calendars")
        if state:
            add("local_suburb_discovery", f'"{niche}" society "{state}" conference', "Find state society conferences")

    levels = {level.lower() for level in _clean(association_levels)}
    if levels:
        if "local" in levels:
            for place in places:
                if not place:
                    continue
                for term in ["chapter", "section", "committee", "luncheon", "breakfast", "webinar", "CLE", "meeting"]:
                    add(
                        "local_association_discovery",
                        f'"{niche}" "{term}" "{place}" {year}'.strip(),
                        "Find local association chapters, committees, and recurring meetings",
                    )
                add(
                    "local_association_discovery",
                    f'"{place}" bar association "{niche}" events {year}'.strip(),
                    "Find local bar/association event calendars when relevant",
                )
        if "regional" in levels:
            region_terms = _clean([state, city])
            for region in region_terms:
                for term in ["state bar", "section", "chapter", "annual meeting", "conference", "seminar", "CLE"]:
                    add(
                        "regional_association_discovery",
                        f'"{niche}" "{term}" "{region}" {year}'.strip(),
                        "Find state/regional association conferences and education events",
                    )
            if state:
                add(
                    "regional_association_discovery",
                    f'"{state}" "{niche}" association event calendar {year}'.strip(),
                    "Find state association event calendars",
                )
        if "national" in levels:
            for term in ["association", "institute", "academy", "section", "annual conference", "annual meeting", "sponsors", "exhibitors"]:
                add(
                    "national_association_discovery",
                    f'"{niche}" national "{term}" {year}'.strip(),
                    "Find national association events and sponsor/exhibitor assets",
                )
            for term in ["speakers", "sponsors", "exhibitors", "conference", "annual meeting"]:
                add(
                    "national_association_discovery",
                    f'"{niche}" "{term}" United States {year}'.strip(),
                    "Find national US association opportunities",
                )
    # Industry / trade association events — pass specific org names e.g. "PHCC", "ACCA", "NASBA"
    for assoc in _clean(known_associations):
        for term in ["annual conference", "annual meeting", "trade show", "expo", "convention", "events"]:
            add(
                "industry_trade_association",
                f'"{assoc}" {term} {year}'.strip(),
                f"Find {assoc} {term}",
            )
        if city:
            add(
                "industry_trade_association",
                f'"{assoc}" chapter "{city}" {year}'.strip(),
                f"Find local {assoc} chapter events in {city}",
            )
        if state:
            add(
                "industry_trade_association",
                f'"{assoc}" "{state}" {year}'.strip(),
                f"Find {assoc} events in {state}",
            )

    return queries


def main():
    parser = argparse.ArgumentParser(description="Generate layered live-event deep research queries.")
    parser.add_argument("--niche", required=True)
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--year", default="")
    parser.add_argument("--event-name", default="")
    parser.add_argument("--adjacent", nargs="*", default=[])
    parser.add_argument("--asset-terms", nargs="*", default=[])
    parser.add_argument("--official-domains", nargs="*", default=[])
    parser.add_argument("--industry-publications", nargs="*", default=[])
    parser.add_argument("--companies", nargs="*", default=[])
    parser.add_argument("--people", nargs="*", default=[])
    parser.add_argument("--suburbs", nargs="*", default=[])
    parser.add_argument("--association-levels", nargs="*", default=[])
    parser.add_argument("--known-associations", nargs="*", default=[])
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    rows = generate_queries(
        args.niche, args.city, args.state, args.year, args.event_name, args.adjacent,
        args.asset_terms, args.official_domains, args.industry_publications, args.companies,
        args.people, args.suburbs, args.association_levels, args.known_associations,
    )
    if args.output:
        if args.output.lower().endswith(".json"):
            write_json(args.output, rows)
        else:
            write_csv(args.output, rows, ["stage", "query", "intent"])
    else:
        print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
