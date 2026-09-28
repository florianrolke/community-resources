from pathlib import Path

from scripts.build_interviewee_linkedin_list import generic_report_rows, report_rows_to_guest_rows, rows_from_report_files
from scripts.extract_youtube_urls_from_report import extract_youtube_rows


def test_report_episode_rows_become_interviewee_rows():
    text = Path("tests/fixtures/genspark_confirmed_family_law_episode_urls.md").read_text(encoding="utf-8")
    report_rows = extract_youtube_rows(text)
    guest_rows = report_rows_to_guest_rows(report_rows)
    by_url = {row["episode_url"]: row for row in guest_rows}
    assert by_url["https://www.youtube.com/watch?v=PwVRtF2sr10"]["guest_name"] == "Christy A. Example"
    assert by_url["https://www.youtube.com/watch?v=GRO6Ow7pXfI"]["platform"] == "youtube"


def test_rows_from_report_files_are_dedicated_guest_schema():
    rows = rows_from_report_files(["tests/fixtures/genspark_confirmed_family_law_episode_urls.md"])
    assert rows[0]["episode_url"].startswith("https://www.youtube.com/watch?v=")
    assert rows[0]["extraction_source"] == "research_report_episode_table"


def test_generic_report_rows_support_non_youtube_episode_urls():
    text = """podcast_or_series,episode_title,guest_or_speaker,episode_url,linkedin_url
Pool Chasers,Design Build with Jane Builder,Jane Builder,https://example.com/episode,jane-link
"""
    rows = report_rows_to_guest_rows(generic_report_rows(text))
    assert rows[0]["episode_url"] == "https://example.com/episode"
    assert rows[0]["linkedin_url"] == "jane-link"
