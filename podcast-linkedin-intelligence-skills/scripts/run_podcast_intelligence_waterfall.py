from __future__ import annotations

import argparse

from scripts.build_interviewee_linkedin_list import rows_from_report_files
from scripts.common import slugify, write_csv
from scripts.discover_podcast_interviews_serp import FIELDS as DISCOVERY_FIELDS, niche_queries, serp_rows_to_episode_rows
from scripts.apify_serp import apify_serp_search
from scripts.enrich_linkedin_via_apify_serp import enrich_rows


def ask_if_missing(value: str, prompt: str) -> str:
    return value or input(prompt).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the no-manual-research podcast interviewee LinkedIn waterfall.")
    parser.add_argument("--niche", default="")
    parser.add_argument("--audience", default="")
    parser.add_argument("--seed-terms", default="")
    parser.add_argument("--max-pages-per-query", type=int, default=1)
    parser.add_argument("--results-per-page", type=int, default=10)
    parser.add_argument("--linkedin-results-per-person", type=int, default=5)
    parser.add_argument("--output-prefix", default="")
    args = parser.parse_args()

    niche = ask_if_missing(args.niche, "Niche/industry, e.g. pool construction: ")
    audience = ask_if_missing(args.audience, "Target audience/ICP, e.g. pool builders, designers, remodelers: ")
    seed_terms = args.seed_terms or input("Optional seed terms, e.g. design build remodeling service; press Enter to skip: ").strip()
    prefix = args.output_prefix or f"data/{slugify(niche)}"

    serp_rows = apify_serp_search(niche_queries(niche, audience, seed_terms), args.max_pages_per_query, args.results_per_page)
    discovery_rows = serp_rows_to_episode_rows(serp_rows, niche)
    discovery_path = f"{prefix}-podcast-interview-episode-serp-discovery.csv"
    write_csv(discovery_path, discovery_rows, DISCOVERY_FIELDS)

    # Reuse the same generic report parser by writing discovery rows first.
    guest_rows = rows_from_report_files([discovery_path])
    raw_guest_path = f"{prefix}-podcast-interviewees-extracted.csv"
    write_csv(raw_guest_path, guest_rows)

    enriched_rows = enrich_rows(guest_rows, "guest_name", 1, args.linkedin_results_per_person)
    enriched_path = f"{prefix}-podcast-interviewees-linkedin-enriched.csv"
    write_csv(enriched_path, enriched_rows)

    print(f"Discovery rows: {len(discovery_rows)} -> {discovery_path}")
    print(f"Guest rows: {len(guest_rows)} -> {raw_guest_path}")
    print(f"LinkedIn enriched rows: {len(enriched_rows)} -> {enriched_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
