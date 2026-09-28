from __future__ import annotations
import argparse, base64, json, os, re, requests
from scripts.common import load_env, read_csv, write_csv
from scripts.extraction import is_likely_person_name
PROMPT='Extract visible person names, titles, and companies from this podcast thumbnail. Return only JSON array: [{"name":"First Last","title":null,"company":null}]. Return [] if no guest name is visible.'
def video_id_from_url(url):
    m=re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})',url or ''); return m.group(1) if m else ''
def fetch_b64(video_id):
    for q in ['maxresdefault','hqdefault','mqdefault']:
        r=requests.get(f'https://img.youtube.com/vi/{video_id}/{q}.jpg',timeout=15)
        if r.status_code==200 and len(r.content)>5000: return base64.b64encode(r.content).decode('ascii')
    return ''
def ocr(video_id):
    load_env(); key=os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not key: raise RuntimeError('OPENROUTER_API_KEY or OPENAI_API_KEY required')
    b64=fetch_b64(video_id)
    if not b64: return []
    use_router=bool(os.getenv('OPENROUTER_API_KEY')); url='https://openrouter.ai/api/v1/chat/completions' if use_router else 'https://api.openai.com/v1/chat/completions'; model='anthropic/claude-haiku-4-5' if use_router else 'gpt-4o-mini'
    r=requests.post(url,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':model,'messages':[{'role':'user','content':[{'type':'text','text':PROMPT},{'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{b64}','detail':'low'}}]}],'temperature':0,'max_tokens':300},timeout=45); r.raise_for_status(); content=r.json()['choices'][0]['message']['content'].strip(); content=re.sub(r'^```(?:json)?\s*|\s*```$','',content); data=json.loads(content); return data if isinstance(data,list) else []
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--episodes',required=True); ap.add_argument('--output',required=True); a=ap.parse_args(); rows=[]
    for ep in read_csv(a.episodes):
        vid=ep.get('video_id') or video_id_from_url(ep.get('episode_url') or ep.get('youtube_url') or '')
        if not vid: continue
        for item in ocr(vid):
            name=(item.get('name') or '').strip()
            if is_likely_person_name(name): rows.append({**ep,'guest_name':name,'guest_role':item.get('title') or '','guest_company':item.get('company') or '','extraction_source':'thumbnail_ocr'})
    write_csv(a.output,rows); print(f'Rows written: {len(rows)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
