from __future__ import annotations
import re
from scripts.common import ascii_norm
NAME=r"((?:(?:Dr|Mr|Mrs|Ms)\.?\s+)?(?:[A-Z][A-Za-z'\-]+\s+){1,3}[A-Z][A-Za-z'\-]+)"
NAME_STOP=NAME+r"(?=[,)]|\s+and\s+|\s+(?:of|from|at|on|about|with|has|tells|shares|explains|discusses)\b|\s*[\-:\u2013\u2014|]|\s*$)"
GUEST_PATTERNS=[r"^\s*ep\.?\s*\d+\s*[\-:|]\s*"+NAME+r"(?=,|\s*[\-:\u2013\u2014|])",r"\bwith\s+"+NAME_STOP,r"\bw/\s+"+NAME_STOP,r"\bfeaturing\s+"+NAME_STOP,r"\bfeat\.?\s+"+NAME_STOP,r"\b(?:spoke|talked|sat down)\s+with\s+"+NAME_STOP,r"\binterview\s+(?:with\s+|of\s+)?"+NAME_STOP,r"^\s*(?:ep\.?\s*\d+\s*[\-:|]\s*)?"+NAME+r"\s*(?:[\-:\u2013\u2014|]|,\s*[A-Z])",r"[\-:\u2013\u2014|]\s*"+NAME+r"\s*$",NAME+r"\s+(?:tells|shares|explains|discusses|talks|reveals)\b"]
SOLO_PATTERNS=[r"^\s*(how to|what is|why|top \d+|\d+ tips|trailer|welcome|bonus|recap|q&a)\b",r"\bsolo\b"]
BAD_NAME_PARTS={'podcast','episode','interview','guest','host','founder','owner','ceo','mobile home','real estate','cash flow','business','marketing','youtube','building','homes','home','prefab','construction','investing','association','community','section','specialization','governance','validation','tech talk','risk management','emerging topics','partner','course','webinar','summit','conference'}
def clean_name(name):
    name=re.sub(r"^(?:guest|host|interview)\s+",'',name or '',flags=re.I).strip(); name=re.sub(r'\s+',' ',name); return re.sub(r'[,|].*$','',name).strip()
def is_likely_person_name(name, known_hosts=None):
    name=clean_name(name); known_hosts=known_hosts or set()
    if not name or name in known_hosts: return False
    parts=name.split()
    if len(parts)<2 or len(parts)>5 or any(ch.isdigit() for ch in name): return False
    if parts[0].lower() in {'the','a','an'}: return False
    lowered=ascii_norm(name)
    if any(bad in lowered for bad in BAD_NAME_PARTS): return False
    return all(part[:1].isupper() or part.lower() in {'de','van','von','la','le'} for part in parts)
def is_probably_solo(title): return any(re.search(p,title or '',re.I) for p in SOLO_PATTERNS)
def extract_guest_names(text, known_hosts=None):
    if not text or is_probably_solo(text): return []
    found=[]
    for pat in GUEST_PATTERNS:
        for m in re.finditer(pat,text,re.I):
            name=clean_name(m.group(1))
            if is_likely_person_name(name,known_hosts) and name not in found: found.append(name)
    return found
def classify_report_source(text):
    low=(text or '').lower(); g=sum(1 for m in ['genspark','sparkpage','super agent','using tool','parallel search','parallel read','video search','write file','read file','bash command','download file','research report'] if m in low); p=sum(1 for m in ['perplexity','sonar','citations','related questions'] if m in low)
    return 'genspark' if g>p else 'perplexity' if p>g else 'unknown'
