from pathlib import Path
from scripts.common import read_csv, write_csv
from scripts.ingest_research_report import FIELDS, parse_report
from scripts.linkedin_matcher import score_candidate
def test_offline_report_to_candidate_score(tmp_path):
    rows=parse_report(Path('tests/fixtures/genspark_report.md').read_text(encoding='utf-8'),'manufactured housing')
    out=tmp_path/'manufactured-housing-podcasts-discovered.csv'; write_csv(out,rows,FIELDS); loaded=read_csv(out)
    candidate={'url':'https://www.linkedin.com/in/frank-rizzo','title':'Frank Rizzo - The MHP Exchange','content':'manufactured housing podcast'}
    assert score_candidate(candidate,loaded[0])['confidence'] in {'high','verify'}
