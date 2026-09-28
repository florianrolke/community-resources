from __future__ import annotations
import argparse
from scripts.api_clients import ExaSearch, TavilySearch
from scripts.common import read_csv, write_csv
def find_youtube(row,tavily,exa):
    if row.get('youtube_url'): return row['youtube_url']
    q=f'"{row.get("podcast_name","")}" "{row.get("host_or_owner_name","")}" YouTube podcast channel'
    for r in tavily.search(q,5,['youtube.com'])+exa.search(q,5,['youtube.com']):
        if 'youtube.com' in r.get('url',''): return r.get('url','')
    return ''
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); a=ap.parse_args(); rows=read_csv(a.input); tavily,exa=TavilySearch(),ExaSearch()
    for row in rows: row['youtube_url']=find_youtube(row,tavily,exa); row['youtube_resolution_confidence']='verify' if row['youtube_url'] else 'low'
    write_csv(a.output,rows); print(f'Rows written: {len(rows)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
