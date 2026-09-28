from pathlib import Path
from scripts.ingest_research_report import parse_report
def test_parse_perplexity_fixture():
    rows=parse_report(Path('tests/fixtures/perplexity_report.md').read_text(encoding='utf-8'),'mobile home park investing')
    assert rows and rows[0]['source']=='perplexity'
    assert rows[0]['apple_url'].startswith('https://podcasts.apple.com')
def test_parse_genspark_fixture():
    rows=parse_report(Path('tests/fixtures/genspark_report.md').read_text(encoding='utf-8'),'manufactured housing')
    assert rows and rows[0]['source']=='genspark'
    assert rows[0]['youtube_url'].startswith('https://www.youtube.com')
