from __future__ import annotations
import csv, json, os, re, time, unicodedata
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
ROOT = Path(__file__).resolve().parents[1]
def load_env():
    if load_dotenv: load_dotenv(ROOT / '.env')
def env_keys(prefix, max_number=20, preferred=None):
    load_env(); names=[]
    if preferred: names=[f'{prefix}_{s}' if s else prefix for s in preferred]
    else: names=[prefix]+[f'{prefix}_{i}' for i in range(2,max_number+1)]
    out=[]
    for n in names:
        v=os.getenv(n)
        if v and v not in out: out.append(v)
    return out
class RotatingKeyClient:
    def __init__(self,label,keys,min_delay=0.5): self.label=label; self.keys=keys; self.index=0; self.exhausted=set(); self.min_delay=min_delay; self.last_call=0.0
    @property
    def available(self): return bool(self.keys) and len(self.exhausted)<len(self.keys)
    def key(self):
        if not self.available: raise RuntimeError(f'No {self.label} keys available')
        return self.keys[self.index]
    def wait(self):
        elapsed=time.time()-self.last_call
        if elapsed<self.min_delay: time.sleep(self.min_delay-elapsed)
        self.last_call=time.time()
    def mark_exhausted_and_rotate(self):
        self.exhausted.add(self.index)
        for _ in range(len(self.keys)):
            self.index=(self.index+1)%len(self.keys)
            if self.index not in self.exhausted: return True
        return False
def read_csv(path):
    with open(path,'r',encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def write_csv(path, rows, fieldnames=None):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if fieldnames is None:
        fieldnames=[]
        for r in rows:
            for k in r:
                if k not in fieldnames: fieldnames.append(k)
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def write_json(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
def ascii_norm(text):
    text=(text or '').lower(); text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode(); return re.sub(r'[^a-z0-9]+',' ',text).strip()
def compact_text(text,max_len=160): return re.sub(r'\s+',' ',re.sub(r'https?://\S+',' ',text or '')).strip()[:max_len]
def dedupe_rows(rows,keys):
    seen=set(); out=[]
    for r in rows:
        mark=tuple(ascii_norm(str(r.get(k,''))) for k in keys)
        if mark in seen: continue
        seen.add(mark); out.append(r)
    return out
def slugify(v): return re.sub(r'\s+','-',ascii_norm(v)).strip('-') or 'podcast-campaign'
