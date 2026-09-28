from __future__ import annotations

import argparse
import re

from scripts.apify_serp import apify_serp_search
from scripts.common import dedupe_rows, slugify, write_csv
from scripts.extraction import extract_guest_names

FIELDS = ["podcast_or_series", "episode_title", "guest_or_speaker", "episode_url", "linkedin_url", "notes"]


def niche_queries(niche: str, audience: str = "", seed_terms: str = "") -> list[str]:
    seeds = [niche]
    if audience:
        seeds.append(audience)
    if seed_terms:
        seeds.extend([part.strip() for part in re.split(r"[,;]", seed_terms) if part.strip()])
    compact = []
    seen = set()
    for seed in seeds:
        seed = re.sub(r"\s+", " ", seed).strip()
        if seed and seed.lower() not in seen:
            seen.add(seed.lower())
            compact.append(seed)
    queries = []
    for target in compact[:8]:
        queries.extend(
            [
                f'"{target}" podcast interview',
                f'"{target}" podcast "with"',
                f'"{target}" "interview with" podcast',
            ]
        )
    primary = compact[0] if compact else niche
    queries.extend(
        [
            f'site:youtube.com/watch "{primary}" podcast interview',
            f'site:podcasts.apple.com "{primary}" podcast "with"',
            f'site:spotify.com/episode "{primary}" podcast',
            f'site:podcastaddict.com "{primary}" "episode"',
        ]
    )
    return queries


def looks_like_episode(row: dict, niche: str) -> bool:
    hay = " ".join([row.get("title", ""), row.get("snippet", ""), row.get("url", "")]).lower()
    if "linkedin.com/" in hay:
        return False
    episode_terms = ["podcast", "episode", "interview", "with ", "guest"]
    niche_terms = [term for term in re.split(r"[^a-z0-9]+", niche.lower()) if len(term) >= 4]
    return any(term in hay for term in episode_terms) and (not niche_terms or any(term in hay for term in niche_terms))


def guess_podcast_name(title: str) -> str:
    title = re.sub(r"\s+-\s+YouTube$", "", title or "", flags=re.I)
    pieces = re.split(r"\s+[|–—-]\s+", title)
    podcastish = [p.strip() for p in pieces if "podcast" in p.lower()]
    return podcastish[-1] if podcastish else ""


def serp_rows_to_episode_rows(rows: list[dict], niche: str) -> list[dict]:
    out = []
    for row in rows:
        if not looks_like_episode(row, niche):
            continue
        title = row.get("title", "").strip()
        names = extract_guest_names(title) or extract_guest_names(row.get("snippet", ""))
        out.append(
            {
                "podcast_or_series": guess_podcast_name(title),
                "episode_title": title,
                "guest_or_speaker": "; ".join(names),
                "episode_url": row.get("url", ""),
                "linkedin_url": "",
                "notes": f"Apify SERP query: {row.get('query', '')}; rank: {row.get('rank', '')}; snippet: {row.get('snippet', '')[:240]}",
            }
        )
    return dedupe_rows(out, ["episode_url"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover niche podcast interview episodes from Apify SERPs.")
    parser.add_argument("--niche", required=True)
    parser.add_argument("--audience", default="", help="Optional ICP/audience phrase, e.g. pool builders.")
    parser.add_argument("--seed-terms", default="", help="Optional extra terms such as design build remodeling.")
    parser.add_argument("--output", help="Defaults to data/<niche>-podcast-interview-episode-serp-discovery.csv")
    parser.add_argument("--max-pages-per-query", type=int, default=1)
    parser.add_argument("--results-per-page", type=int, default=10)
    args = parser.parse_args()
    output = args.output or f"data/{slugify(args.niche)}-podcast-interview-episode-serp-discovery.csv"
    serp_rows = apify_serp_search(niche_queries(args.niche, args.audience, args.seed_terms), args.max_pages_per_query, args.results_per_page)
    rows = serp_rows_to_episode_rows(serp_rows, args.niche)
    write_csv(output, rows, FIELDS)
    print(f"Rows written: {len(rows)} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
