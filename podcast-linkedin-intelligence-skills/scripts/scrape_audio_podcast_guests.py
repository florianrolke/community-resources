from __future__ import annotations
import argparse, re, requests
from xml.etree import ElementTree as ET
from scripts.common import read_csv, write_csv
from scripts.extraction import extract_guest_names
from scripts.linkedin_matcher import match_one
FIELDS=['podcast_name','episode_title','episode_url','platform','guest_name','guest_role','guest_company','linkedin_url','extraction_source','match_confidence','evidence']
def fetch_rss(feed_url):
    r=requests.get(feed_url,headers={'User-Agent':'podcast-intelligence/0.1'},timeout=30); r.raise_for_status(); root=ET.fromstring(r.content); eps=[]
    for item in root.iter('item'):
        title_el=item.find('title'); link_el=item.find('link'); enc=item.find('enclosure'); desc_el=item.find('description')
        title=title_el.text.strip() if title_el is not None and title_el.text else ''; url=link_el.text.strip() if link_el is not None and link_el.text else ''
        if not url and enc is not None: url=enc.get('url','')
        desc=re.sub(r'<[^>]+>',' ',desc_el.text or '') if desc_el is not None else ''
        if title: eps.append({'title':title,'url':url,'description':desc})
    return eps
def extract_title_rows(feed_row):
    out=[]; podcast=feed_row.get('podcast_name','')
    for ep in fetch_rss(feed_row.get('rss_url','')):
        for name in (extract_guest_names(ep['title']) or extract_guest_names(ep['description'][:500])):
            out.append({'podcast_name':podcast,'episode_title':ep['title'],'episode_url':ep['url'],'platform':'rss','guest_name':name,'guest_role':'','guest_company':'','linkedin_url':'','extraction_source':'rss_title_or_description','match_confidence':'verify','evidence':ep['title']})
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--feeds',required=True); ap.add_argument('--phase',choices=['titles','transcripts'],required=True); ap.add_argument('--output',required=True); ap.add_argument('--match-linkedin',action='store_true'); a=ap.parse_args()
    if a.phase=='transcripts': raise SystemExit('Transcript phase is configured via scripts/transcribe_audio_episodes.py, then parse transcript-derived rows.')
    rows=[]
    for feed in read_csv(a.feeds):
        if feed.get('rss_url'): rows.extend(extract_title_rows(feed))
    if a.match_linkedin:
        for row in rows:
            m=match_one(row,'guest'); row['linkedin_url']=m.get('linkedin_url',''); row['match_confidence']=m.get('linkedin_confidence','')
    write_csv(a.output,rows,FIELDS); print(f'Rows written: {len(rows)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
