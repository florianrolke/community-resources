from __future__ import annotations

import argparse
import json

from scripts.apify_serp import apify_serp_search
from scripts.common import compact_text, read_csv, write_csv
from scripts.linkedin_matcher import score_candidate


def linkedin_query(row: dict, person_field: str) -> str:
    name = row.get(person_field, "").strip()
    context = compact_text(" ".join([row.get("guest_company", ""), row.get("podcast_name", ""), row.get("episode_title", "")]), 120)
    return f'"{name}" "{context}" linkedin.com/in' if context else f'"{name}" linkedin.com/in'


def enrich_rows(rows: list[dict], person_field: str, max_pages_per_query: int, results_per_page: int) -> list[dict]:
    out = []
    for row in rows:
        name = row.get(person_field, "").strip()
        if not name:
            out.append(row)
            continue
        serp = apify_serp_search([linkedin_query(row, person_field)], max_pages_per_query=max_pages_per_query, results_per_page=results_per_page)
        candidates = [
            {"url": r.get("url", ""), "title": r.get("title", ""), "content": r.get("snippet", ""), "provider": "apify_serp", "query_variant": "linkedin_serp"}
            for r in serp
        ]
        scored = [score_candidate(candidate, row) for candidate in candidates]
        scored = [s for s in scored if s.get("url")]
        scored.sort(key=lambda item: item.get("score", 0), reverse=True)
        best = scored[0] if scored else {}
        row = dict(row)
        row["linkedin_candidate"] = best.get("url", "")
        row["linkedin_source"] = best.get("provider", "not_found")
        row["linkedin_confidence"] = best.get("confidence", "low")
        row["linkedin_evidence_score"] = best.get("score", 0)
        row["linkedin_notes"] = best.get("evidence", "no LinkedIn candidate found")
        row["linkedin_candidates_json"] = json.dumps(scored[:5], ensure_ascii=False)
        if best.get("confidence") == "high":
            row["linkedin_url"] = row.get("linkedin_url") or best.get("url", "")
        out.append(row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich people to LinkedIn using Apify SERP results instead of Tavily/Exa.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--person-field", default="guest_name")
    parser.add_argument("--max-pages-per-query", type=int, default=1)
    parser.add_argument("--results-per-page", type=int, default=5)
    args = parser.parse_args()
    rows = enrich_rows(read_csv(args.input), args.person_field, args.max_pages_per_query, args.results_per_page)
    write_csv(args.output, rows)
    print(f"Rows written: {len(rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
