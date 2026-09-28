from __future__ import annotations
import json, re
from scripts.api_clients import ExaSearch, TavilySearch, perplexity_chat
from scripts.common import ascii_norm, compact_text
LINKEDIN_RE=re.compile(r"https?://(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_%\-.]+)/?",re.I)
BAD_SLUGS={'company','school','jobs','learning','pulse','posts','feed','dir','profile'}
def clean_linkedin_url(text):
    m=LINKEDIN_RE.search(text or '')
    if not m: return ''
    slug=m.group(1).strip('/')
    if not slug or slug.lower() in BAD_SLUGS: return ''
    return f'https://www.linkedin.com/in/{slug}'
def name_parts(name): return [p for p in ascii_norm(name).split() if len(p)>1]
def slug_matches_name(url,name):
    clean=clean_linkedin_url(url); parts=name_parts(name)
    if not clean or len(parts)<2: return False
    slug=ascii_norm(clean.rsplit('/',1)[-1]); first,last=parts[0],parts[-1]
    return (last in slug.split() or slug.endswith(last)) and (first in slug or first[:3] in slug)
def score_candidate(candidate,row):
    name=row.get('host_or_owner_name') or row.get('guest_name') or row.get('name') or ''
    context=' '.join(str(row.get(k,'')) for k in ['podcast_name','company','niche','episode_title','website'])
    hay=ascii_norm(' '.join(str(candidate.get(k,'')) for k in ['url','title','content','snippet','text']))
    url=clean_linkedin_url(candidate.get('url','')); parts=name_parts(name); score=0; evidence=[]
    if url: score+=1; evidence.append('Direct LinkedIn profile result')
    if slug_matches_name(url,name): score+=5; evidence.append('LinkedIn slug matches first/last name')
    if parts and all(part in hay for part in parts[:1]+parts[-1:]): score+=2; evidence.append('Result text repeats name')
    terms=[t for t in ascii_norm(context).split() if len(t)>=5][:12]; matched=[t for t in terms if t in hay]
    if matched: score+=min(3,len(matched)); evidence.append('Context evidence: '+', '.join(matched[:5]))
    if 'linkedin com company' in hay or '/company/' in str(candidate.get('url','')).lower(): score-=5; evidence.append('Rejected company-style result')
    conf='high' if score>=7 and slug_matches_name(url,name) else 'verify' if score>=5 and url else 'low'
    return {'url':url,'score':score,'confidence':conf,'evidence':'; '.join(evidence) or 'No useful evidence','title':candidate.get('title',''),'content':compact_text(candidate.get('content') or candidate.get('snippet') or candidate.get('text') or '',500),'provider':candidate.get('provider','unknown'),'query_variant':candidate.get('query_variant','')}
def query_variants(row, person_kind='owner'):
    name=row.get('host_or_owner_name') or row.get('guest_name') or row.get('name') or ''
    if not name: return []
    vals=[('name_linkedin',f'"{name}" linkedin.com/in')]
    for key,label in [('podcast_name','podcast_context'),('company','company_context'),('niche','niche_context')]:
        v=compact_text(row.get(key,''),80)
        if v: vals.append((label,f'"{name}" "{v}" linkedin.com/in'))
    ep=compact_text(row.get('episode_title',''),100)
    if person_kind=='guest' and ep: vals.append(('episode_context',f'"{name}" "{ep}" linkedin.com/in'))
    seen=set(); out=[]
    for label,q in vals:
        if q.lower() not in seen: seen.add(q.lower()); out.append((label,q))
    return out
def match_one(row, person_kind='owner', use_perplexity=False, tavily=None, exa=None):
    tavily=tavily or TavilySearch(); exa=exa or ExaSearch(); candidates=[]
    for label,q in query_variants(row,person_kind):
        for r in tavily.search(q,include_domains=['linkedin.com']): r=dict(r); r.update(provider='tavily',query_variant=label); candidates.append(r)
        for r in exa.search(q,include_domains=['linkedin.com']): r=dict(r); r.update(provider='exa',query_variant=label); r.setdefault('content',r.get('text','')); candidates.append(r)
    scored=[]; seen=set()
    for c in candidates:
        s=score_candidate(c,row); url=s.get('url','')
        if url and url not in seen: seen.add(url); scored.append(s)
    scored.sort(key=lambda c:c['score'],reverse=True)
    if use_perplexity and (not scored or scored[0]['confidence']!='high'):
        name=row.get('host_or_owner_name') or row.get('guest_name') or row.get('name') or ''
        ans=perplexity_chat(f'Find the LinkedIn /in/ profile for {name}. Context: {json.dumps(row,ensure_ascii=False)}. Return only the URL or NOT_FOUND.',max_tokens=200); url=clean_linkedin_url(ans)
        if url: scored.append(score_candidate({'url':url,'title':ans,'provider':'perplexity'},row)); scored.sort(key=lambda c:c['score'],reverse=True)
    best=scored[0] if scored else {}; accepted=best.get('url','') if best.get('confidence')=='high' else ''
    return {'linkedin_url':row.get('linkedin_url') or accepted,'linkedin_candidate':best.get('url',''),'linkedin_source':best.get('provider','not_found'),'linkedin_confidence':best.get('confidence','low'),'linkedin_evidence_score':best.get('score',0),'linkedin_notes':best.get('evidence','no LinkedIn candidate found'),'linkedin_candidates_json':json.dumps(scored[:5],ensure_ascii=False)}
