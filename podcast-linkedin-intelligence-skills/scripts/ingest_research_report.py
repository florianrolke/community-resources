from __future__ import annotations
import argparse, json, re
from pathlib import Path
from scripts.common import write_csv, write_json
from scripts.extraction import classify_report_source
FIELDS=['podcast_name','niche','host_or_owner_name','company','website','youtube_url','rss_url','spotify_url','apple_url','linkedin_url','source','confidence','evidence']
URL_RE=re.compile(r'https?://[^\s)\]>\"]+')
def infer_podcast_blocks(text):
    blocks=re.split(r'\n(?=(?:#{1,4}\s+|\d+\.\s+|[-*]\s+)?[A-Z][^\n]{3,120}(?:Podcast|Show|Radio|Interview|Mastery))',text)
    return [b.strip() for b in blocks if len(b.strip())>40]
def parse_report(text,niche=''):
    source=classify_report_source(text); rows=[]
    for block in infer_podcast_blocks(text):
        first=next((ln.strip('# -*0123456789.') for ln in block.splitlines() if ln.strip()),'')
        row={f:'' for f in FIELDS}; row.update(podcast_name=re.sub(r'\s+',' ',first).strip()[:120],niche=niche,source=source,confidence='verify',evidence=block[:600].replace('\n',' '))
        for url in URL_RE.findall(block):
            low=url.lower()
            if 'youtube.com' in low or 'youtu.be' in low: row['youtube_url']=row['youtube_url'] or url
            elif 'spotify.com' in low: row['spotify_url']=row['spotify_url'] or url
            elif 'podcasts.apple.com' in low: row['apple_url']=row['apple_url'] or url
            elif low.endswith('.xml') or 'rss' in low or 'feed' in low: row['rss_url']=row['rss_url'] or url
            elif 'linkedin.com/in/' in low: row['linkedin_url']=row['linkedin_url'] or url
            elif not row['website']: row['website']=url
        m=re.search(r'(?:host|hosted by|owner|creator|founded by)[:\s]+([A-Z][A-Za-z\'\-]+\s+[A-Z][A-Za-z\'\-]+)',block,re.I)
        if m: row['host_or_owner_name']=m.group(1)
        if row['podcast_name']: rows.append(row)
    return rows
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); ap.add_argument('--json-output'); ap.add_argument('--niche',default=''); a=ap.parse_args()
    text=Path(a.input).read_text(encoding='utf-8'); rows=parse_report(text,a.niche); write_csv(a.output,rows,FIELDS)
    if a.json_output: write_json(a.json_output,rows)
    print(f'Detected source: {classify_report_source(text)}'); print(f'Rows written: {len(rows)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
