from __future__ import annotations
import argparse, os
from pathlib import Path
from scripts.common import load_env
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--prompt-file',required=True); ap.add_argument('--output',required=True); ap.add_argument('--cdp-url',default=''); ap.add_argument('--wait-seconds',type=int,default=90); a=ap.parse_args(); load_env(); cdp=a.cdp_url or os.getenv('CHROME_CDP_URL','http://127.0.0.1:9222'); prompt=Path(a.prompt_file).read_text(encoding='utf-8')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit('Install browser extras first: python -m pip install -e .[browser]') from e
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp(cdp); page=browser.contexts[0].pages[-1]; page.bring_to_front(); page.keyboard.insert_text(prompt); page.keyboard.press('Enter'); page.wait_for_timeout(a.wait_seconds*1000); text=page.locator('body').inner_text(timeout=10000); out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(text,encoding='utf-8'); print(f'Saved visible Genspark page text -> {out}')
if __name__=='__main__': raise SystemExit(main())
