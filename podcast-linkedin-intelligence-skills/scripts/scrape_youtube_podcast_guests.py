from __future__ import annotations
import argparse, os
from scripts.api_clients import apify_run_sync
from scripts.common import load_env, read_csv, write_csv
from scripts.extraction import extract_guest_names
from scripts.linkedin_matcher import match_one
FIELDS=['podcast_name','episode_title','episode_url','platform','guest_name','guest_role','guest_company','linkedin_url','extraction_source','match_confidence','evidence']
def norm(item): return {'title':item.get('title') or item.get('videoTitle') or item.get('video_title') or '', 'url':item.get('url') or item.get('videoUrl') or item.get('video_url') or '', 'description':item.get('description') or item.get('text') or ''}
def scrape_channel(url,max_videos=500):
    load_env(); actor=os.getenv('APIFY_YOUTUBE_CHANNEL_ACTOR','streamers/youtube-channel-scraper'); return apify_run_sync(actor,{'startUrls':[{'url':url}],'maxResults':max_videos})
def rows_from_episodes(podcast,episodes,known_hosts=None):
    out=[]
    for item in episodes:
        ep=norm(item); names=extract_guest_names(ep['title'],known_hosts) or extract_guest_names(ep['description'][:1000],known_hosts)
        for name in names: out.append({'podcast_name':podcast,'episode_title':ep['title'],'episode_url':ep['url'],'platform':'youtube','guest_name':name,'guest_role':'','guest_company':'','linkedin_url':'','extraction_source':'title_or_description','match_confidence':'verify','evidence':ep['title']})
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--channels',required=True); ap.add_argument('--output',required=True); ap.add_argument('--max-videos',type=int,default=500); ap.add_argument('--match-linkedin',action='store_true'); a=ap.parse_args(); rows=[]
    for ch in read_csv(a.channels):
        url=ch.get('youtube_url') or ch.get('channel_url') or ''
        if not url: continue
        eps=scrape_channel(url,a.max_videos); rows.extend(rows_from_episodes(ch.get('podcast_name') or url,eps,{ch.get('host_or_owner_name','')}))
    if a.match_linkedin:
        for row in rows:
            m=match_one(row,'guest'); row['linkedin_url']=m.get('linkedin_url',''); row['match_confidence']=m.get('linkedin_confidence',''); row['evidence']=(row.get('evidence','')+' | '+m.get('linkedin_notes','')).strip(' |')
    write_csv(a.output,rows,FIELDS); print(f'Rows written: {len(rows)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
