from __future__ import annotations
import argparse, os
from scripts.api_clients import apify_run_sync
from scripts.common import load_env, read_csv, write_json
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--episodes',required=True); ap.add_argument('--output',required=True); ap.add_argument('--actor',default=''); a=ap.parse_args(); load_env(); actor=a.actor or os.getenv('APIFY_AUDIO_TRANSCRIPT_ACTOR','')
    if not actor: raise SystemExit('Set APIFY_AUDIO_TRANSCRIPT_ACTOR or pass --actor for your chosen audio transcript actor.')
    urls=[r.get('audio_url') or r.get('episode_url') for r in read_csv(a.episodes) if r.get('audio_url') or r.get('episode_url')]
    data=apify_run_sync(actor,{'startUrls':[{'url':u} for u in urls]}); write_json(a.output,data); print(f'Transcript items written: {len(data)} -> {a.output}')
if __name__=='__main__': raise SystemExit(main())
