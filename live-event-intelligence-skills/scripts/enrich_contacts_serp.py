from __future__ import annotations

import argparse
from scripts.api_clients import ExaSearch, TavilySearch
from scripts.common import CONTACT_FIELDS, compact_text, first_value, read_csv, write_csv
from scripts.find_linkedin_profiles import extract_linkedin_urls


def enrich_contacts(rows: list[dict], max_results: int = 5) -> list[dict]:
    tavily = TavilySearch()
    exa = ExaSearch()
    out = []
    for row in rows:
        person = first_value(row, "person_name", "name")
        org = first_value(row, "organization", "company")
        query = f'"{person}" "{org}" LinkedIn email phone'.strip()
        evidence_parts = [first_value(row, "evidence")]
        if person or org:
            for result in tavily.search(query, max_results=max_results) + exa.search(query, max_results=max_results):
                evidence_parts.append(" ".join([result.get("url", ""), result.get("title", ""), result.get("content", ""), result.get("text", "")]))
        evidence = " ".join(evidence_parts)
        enriched = dict(row)
        if not first_value(enriched, "linkedin_url"):
            urls = extract_linkedin_urls(evidence, "person")
            enriched["linkedin_url"] = urls[0] if urls else ""
        enriched["evidence"] = compact_text(evidence, 500)
        if not enriched.get("confidence"):
            enriched["confidence"] = "probable" if enriched.get("linkedin_url") else "needs-manual-verification"
        out.append(enriched)
    return out


def main():
    parser = argparse.ArgumentParser(description="Enrich event contacts with SERP/Tavily/Exa evidence.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()
    write_csv(args.output, enrich_contacts(read_csv(args.input), args.max_results), CONTACT_FIELDS)


if __name__ == "__main__":
    main()