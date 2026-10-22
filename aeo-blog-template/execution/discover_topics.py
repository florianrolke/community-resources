"""Discover new blog topics by harvesting Google 'People Also Ask' + 'Related
searches' for seed queries via Apify. Read-only research — writes JSON to
.tmp/topic-discovery/ and prints a summary. No content is changed.

Usage: python execution/discover_topics.py
"""

import json
import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp" / "topic-discovery"
ENV_FILE = ROOT / ".env"
load_dotenv(ENV_FILE)

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
CONFIG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
SEEDS = CONFIG.get("seed_queries", [])


def apify_paa(query: str) -> dict:
    actor = "apify~google-search-scraper"
    url = (f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
           "?timeout=120&memory=256")
    r = requests.post(url, headers={"Authorization": f"Bearer {APIFY_TOKEN}"}, json={
        "queries": query, "maxPagesPerQuery": 1, "resultsPerPage": 10,
        "countryCode": CONFIG.get("country_code", "us"), "languageCode": CONFIG.get("language_code", "en"),
    }, timeout=150)
    if not (200 <= r.status_code < 300):
        return {"paa": [], "related": []}
    items = r.json()
    paa, related = [], []
    for item in items:
        for e in (item.get("peopleAlsoAsk") or []):
            q = e.get("question") or e.get("title")
            if q and q not in paa:
                paa.append(q)
        for e in (item.get("relatedQueries") or []):
            t = e.get("title") or e.get("query") or (e if isinstance(e, str) else None)
            if t and t not in related:
                related.append(t)
    return {"paa": paa, "related": related}


def main():
    parser = argparse.ArgumentParser(description="Research configured PAA topics through Apify")
    parser.add_argument("--live", action="store_true", help="Run paid Apify requests")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"queries": SEEDS, "live": False}, indent=2))
        print("Dry run. Pass --live to use your Apify credits.")
        return
    if not APIFY_TOKEN:
        print("No APIFY token in .env")
        return
    TMP.mkdir(parents=True, exist_ok=True)
    all_data = {}
    all_paa, all_related = [], []
    for i, seed in enumerate(SEEDS, 1):
        print(f"[{i}/{len(SEEDS)}] {seed}")
        d = apify_paa(seed)
        all_data[seed] = d
        print(f"    PAA:{len(d['paa'])}  related:{len(d['related'])}")
        for q in d["paa"]:
            if q not in all_paa:
                all_paa.append(q)
        for t in d["related"]:
            if t not in all_related:
                all_related.append(t)
    (TMP / "raw.json").write_text(json.dumps(all_data, indent=2), encoding="utf-8")
    (TMP / "all_questions.json").write_text(
        json.dumps({"paa": all_paa, "related": all_related}, indent=2), encoding="utf-8")
    print(f"\n=== {len(all_paa)} unique PAA questions, {len(all_related)} related searches ===")
    print("\n--- ALL PAA QUESTIONS ---")
    for q in all_paa:
        print("  Q:", q)
    print("\n--- RELATED SEARCHES ---")
    for t in all_related:
        print("  ~", t)


if __name__ == "__main__":
    main()
