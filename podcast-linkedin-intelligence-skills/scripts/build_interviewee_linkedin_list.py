from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from scripts.common import dedupe_rows, read_csv, write_csv
from scripts.extract_youtube_urls_from_report import extract_youtube_rows
from scripts.extraction import extract_guest_names
from scripts.linkedin_matcher import match_one
from scripts.scrape_audio_podcast_guests import extract_title_rows
from scripts.scrape_youtube_podcast_guests import rows_from_episodes, scrape_channel

FIELDS = [
    "podcast_name",
    "episode_title",
    "episode_url",
    "platform",
    "guest_name",
    "guest_role",
    "guest_company",
    "linkedin_url",
    "extraction_source",
    "match_confidence",
    "evidence",
    "linkedin_candidate",
    "linkedin_source",
    "linkedin_confidence",
    "linkedin_evidence_score",
    "linkedin_notes",
    "linkedin_candidates_json",
]


def platform_from_url(url: str) -> str:
    low = (url or "").lower()
    if "youtube.com" in low or "youtu.be" in low:
        return "youtube"
    if "podcasts.apple.com" in low:
        return "apple"
    if "spotify.com" in low:
        return "spotify"
    return "web"


def report_rows_to_guest_rows(report_rows: list[dict]) -> list[dict]:
    rows = []
    for item in report_rows:
        title = item.get("episode_title", "").strip()
        url = (item.get("youtube_url") or item.get("episode_url") or "").strip()
        podcast = item.get("podcast_or_series", "").strip()
        guest = item.get("guest_or_speaker", "").strip()
        names = [guest] if guest else extract_guest_names(title)
        for name in names:
            rows.append(
                {
                    "podcast_name": podcast,
                    "episode_title": title,
                    "episode_url": url,
                    "platform": platform_from_url(url),
                    "guest_name": name,
                    "guest_role": "",
                    "guest_company": "",
                    "linkedin_url": item.get("linkedin_url", ""),
                    "extraction_source": item.get("extraction_source", "") or "research_report_episode_table",
                    "match_confidence": item.get("match_confidence", "") or "verify",
                    "evidence": item.get("notes", "") or title,
                }
            )
    return rows


def generic_report_rows(text: str) -> list[dict]:
    rows = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        header = line.strip().lower()
        if "episode_url" not in header or "episode_title" not in header:
            continue
        block = [line]
        for nxt in lines[i + 1 :]:
            if not nxt.strip() or nxt.startswith("#"):
                break
            block.append(nxt)
        for raw in csv.DictReader(io.StringIO("\n".join(block))):
            url = (raw.get("episode_url") or raw.get("youtube_url") or "").strip()
            title = (raw.get("episode_title") or "").strip()
            guest = (raw.get("guest_or_speaker") or raw.get("guest_name") or "").strip()
            if url and title and guest:
                rows.append(raw)
    return rows


def rows_from_report_files(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        report_rows = generic_report_rows(text) + extract_youtube_rows(text)
        rows.extend(report_rows_to_guest_rows(report_rows))
    return rows


def rows_from_podcast_sources(source_csv: str, max_videos: int) -> list[dict]:
    rows = []
    for source in read_csv(source_csv):
        podcast = source.get("podcast_name") or source.get("series") or source.get("channel_url") or source.get("rss_url") or ""
        known_hosts = {source.get("host_or_owner_name", ""), source.get("host_name", "")}
        channel = source.get("youtube_url") or source.get("channel_url") or ""
        if channel:
            episodes = scrape_channel(channel, max_videos=max_videos)
            rows.extend(rows_from_episodes(podcast, episodes, known_hosts=known_hosts))
        if source.get("rss_url"):
            rows.extend(extract_title_rows(source))
    return rows


def enrich_linkedin(rows: list[dict], use_perplexity: bool = False) -> list[dict]:
    enriched = []
    for row in rows:
        if row.get("guest_name"):
            match = match_one(row, "guest", use_perplexity=use_perplexity)
            row = {**row, **match}
            row["linkedin_url"] = row.get("linkedin_url") or match.get("linkedin_url", "")
            row["match_confidence"] = match.get("linkedin_confidence", row.get("match_confidence", "verify"))
        enriched.append(row)
    return enriched


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an interviewee/guest LinkedIn outreach list from podcast sources and pasted research reports.")
    parser.add_argument("--podcasts", help="CSV of podcast source rows with youtube_url/channel_url and/or rss_url.")
    parser.add_argument("--report", action="append", default=[], help="Pasted Genspark/Perplexity report markdown/text file. Repeat for multiple reports.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-videos", type=int, default=500)
    parser.add_argument("--match-linkedin", action="store_true")
    parser.add_argument("--use-perplexity", action="store_true")
    args = parser.parse_args()

    rows = []
    if args.podcasts:
        rows.extend(rows_from_podcast_sources(args.podcasts, args.max_videos))
    if args.report:
        rows.extend(rows_from_report_files(args.report))

    rows = dedupe_rows(rows, ["podcast_name", "episode_title", "episode_url", "guest_name"])
    if args.match_linkedin:
        rows = enrich_linkedin(rows, use_perplexity=args.use_perplexity)
    write_csv(args.output, rows, FIELDS)
    print(f"Rows written: {len(rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
