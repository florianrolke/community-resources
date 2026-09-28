from pathlib import Path
from scripts.extraction import classify_report_source
from scripts.extract_youtube_urls_from_report import extract_youtube_rows


def test_genspark_tool_trace_classified():
    text = Path('tests/fixtures/genspark_family_law_youtube_report.md').read_text(encoding='utf-8')
    assert classify_report_source(text) == 'genspark'


def test_extract_youtube_rows_from_genspark_report():
    text = Path('tests/fixtures/genspark_family_law_youtube_report.md').read_text(encoding='utf-8')
    rows = extract_youtube_rows(text)
    urls = {row['youtube_url'] for row in rows}
    assert 'https://www.youtube.com/watch?v=th6THDn7lvg' in urls
    assert 'https://www.youtube.com/watch?v=ri5K8l6fS5w' in urls
    assert 'https://www.youtube.com/watch?v=abc123DEF45' in urls



def test_extract_confirmed_episode_table_rows():
    text = Path('tests/fixtures/genspark_confirmed_family_law_episode_urls.md').read_text(encoding='utf-8')
    rows = extract_youtube_rows(text)
    by_url = {row['youtube_url']: row for row in rows}
    assert len(by_url) == 6
    assert by_url['https://www.youtube.com/watch?v=PwVRtF2sr10']['guest_or_speaker'] == 'Christy A. Example'
    assert by_url['https://www.youtube.com/watch?v=GRO6Ow7pXfI']['podcast_or_series'] == 'Family Law Formula Podcast'
