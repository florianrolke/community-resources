from __future__ import annotations
import os, requests
from scripts.common import RotatingKeyClient, env_keys, load_env
RETRY_STATUS={401,402,403,429,432}
class TavilySearch(RotatingKeyClient):
    def __init__(self, keys=None): super().__init__('Tavily', keys or env_keys('TAVILY_API_KEY'), 1.0)
    def search(self, query, max_results=5, include_domains=None):
        if not self.available: return []
        while self.available:
            self.wait(); r=requests.post('https://api.tavily.com/search',json={'api_key':self.key(),'query':query,'search_depth':'basic','max_results':max_results,'include_answer':False,'include_domains':include_domains or []},timeout=30)
            if r.status_code==200: return r.json().get('results',[])
            if r.status_code in RETRY_STATUS and self.mark_exhausted_and_rotate(): continue
            return []
        return []
class ExaSearch(RotatingKeyClient):
    def __init__(self, keys=None): super().__init__('Exa', keys or env_keys('EXA_API_KEY'), 0.75)
    def search(self, query, max_results=5, include_domains=None):
        if not self.available: return []
        while self.available:
            self.wait(); r=requests.post('https://api.exa.ai/search',headers={'x-api-key':self.key(),'Content-Type':'application/json'},json={'query':query,'type':'neural','useAutoprompt':True,'numResults':max_results,'includeDomains':include_domains or []},timeout=30)
            if r.status_code==200: return r.json().get('results',[])
            if r.status_code in RETRY_STATUS and self.mark_exhausted_and_rotate(): continue
            return []
        return []
def perplexity_chat(prompt, system='Return concise factual results.', max_tokens=1200):
    load_env(); key=os.getenv('PERPLEXITY_API_KEY')
    if not key: return ''
    r=requests.post('https://api.perplexity.ai/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':'sonar','messages':[{'role':'system','content':system},{'role':'user','content':prompt}],'max_tokens':max_tokens,'temperature':0},timeout=60)
    if r.status_code!=200: return ''
    return r.json().get('choices',[{}])[0].get('message',{}).get('content','')
def apify_run_sync(actor_id, payload, token=None):
    load_env(); token=token or next(iter(env_keys('APIFY_API_TOKEN', preferred=['5','4','3','2',''])), '')
    if not token: raise RuntimeError('No APIFY_API_TOKEN found')
    actor=actor_id.replace('/','~')
    r=requests.post(f'https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items',params={'token':token},json=payload,timeout=300)
    if not r.ok:
        msg=(r.text or '')[:500].replace(token,'[REDACTED]')
        raise RuntimeError(f'Apify actor {actor_id} failed with HTTP {r.status_code}: {msg}')
    data=r.json(); return data if isinstance(data,list) else []
