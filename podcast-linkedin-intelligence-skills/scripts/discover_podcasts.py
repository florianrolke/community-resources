from __future__ import annotations
import argparse
from scripts.api_clients import ExaSearch, TavilySearch, perplexity_chat
from scripts.common import dedupe_rows, slugify, write_csv
from scripts.ingest_research_report import FIELDS, parse_report
def build_queries(niche):
    return [f'best {niche} podcasts founder owner interview',f'{niche} podcast host LinkedIn',f'site:youtube.com/@ {niche} podcast',f'site:podcasts.apple.com {niche} podcast host',f'site:spotify.com/show {niche} podcast host',f'{niche} "podcast" "with" "CEO"']
def discover(niche,use_perplexity=True):
    rows=[]
    if use_perplexity:
        report=perplexity_chat(f'Find niche podcasts in this industry: {niche}. Return podcast name, host/owner, website, YouTube, RSS/Spotify/Apple, LinkedIn if known, and evidence.',max_tokens=1800)
        if report: rows.extend(parse_report(report,niche))
    tavily,exa=TavilySearch(),ExaSearch()
    for q in build_queries(niche):
        for provider,results in [('tavily',tavily.search(q,max_results=8)),('exa',exa.search(q,max_results=8))]:
            for r in results:
                url=r.get('url',''); low=url.lower(); title=r.get('title',''); content=r.get('content') or r.get('text') or ''
                rows.append({'podcast_name':title[:120],'niche':niche,'host_or_owner_name':'','company':'','website':url if 'linkedin.com' not in low else '','youtube_url':url if 'youtube.com' in low or 'youtu.be' in low else '','rss_url':'','spotify_url':url if 'spotify.com/show' in low else '','apple_url':url if 'podcasts.apple.com' in low else '','linkedin_url':url if 'linkedin.com/in/' in low else '','source':provider,'confidence':'verify','evidence':content[:500]})
    return dedupe_rows([r for r in rows if r.get('podcast_name')],['podcast_name','website','youtube_url'])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--niche',required=True); ap.add_argument('--output',default=''); ap.add_argument('--skip-perplexity',action='store_true'); a=ap.parse_args()
    out=a.output or f'data/{slugify(a.niche)}-podcasts-discovered.csv'; rows=discover(a.niche,not a.skip_perplexity); write_csv(out,rows,FIELDS); print(f'Rows written: {len(rows)} -> {out}')
if __name__=='__main__': raise SystemExit(main())
