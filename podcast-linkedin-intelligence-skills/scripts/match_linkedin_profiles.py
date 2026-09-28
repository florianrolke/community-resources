from __future__ import annotations
import argparse
from scripts.common import read_csv, write_csv
from scripts.linkedin_matcher import match_one
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); ap.add_argument('--person-kind',choices=['owner','guest'],default='owner'); ap.add_argument('--use-perplexity',action='store_true'); a=ap.parse_args()
    rows=read_csv(a.input); out=[]; field='guest_name' if a.person_kind=='guest' else 'host_or_owner_name'
    for i,row in enumerate(rows,1):
        name=row.get(field,'').strip()
        if name:
            print(f'[{i}/{len(rows)}] {name}'); row={**row,**match_one(row,a.person_kind,a.use_perplexity)}
        out.append(row)
    write_csv(a.output,out); print(f'Rows written: {len(out)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
