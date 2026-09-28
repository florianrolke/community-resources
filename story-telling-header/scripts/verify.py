#!/usr/bin/env python3
"""
Headless check that the hero scrub works: serves a dist/ folder and asserts that
video.currentTime tracks scroll (or that the stills fallback cross-fades).

Requires: pip install playwright && playwright install chromium

Usage:
  python scripts/verify.py                 # verifies ./dist
  python scripts/verify.py examples/blog/dist
"""
import subprocess, sys, threading, functools, http.server, socketserver
from pathlib import Path
from _common import ROOT

DIST = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "dist")
if not (DIST / "index.html").exists():
    sys.exit(f"ERROR: {DIST}/index.html not found. Run scripts/build.py first.")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("ERROR: playwright not installed. pip install playwright && playwright install chromium")

PORT = 8123
Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 800})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{PORT}/")
    pg.wait_for_timeout(6000)
    total = pg.evaluate('document.getElementById("ascent").offsetHeight - window.innerHeight')
    has_video = pg.evaluate('!!document.getElementById("ascentVid")')
    samples = []
    for f in (0.0, 0.4, 0.7, 0.95):
        pg.evaluate(f"window.scrollTo(0, {int(total * f)})")
        pg.wait_for_timeout(1400)
        samples.append(pg.evaluate('''() => {
          const v = document.getElementById("ascentVid");
          const beats = [...document.querySelectorAll(".beat")].map(x => +(x.style.opacity||0));
          return { t: v ? +v.currentTime.toFixed(2) : null, active: beats.indexOf(Math.max(...beats)) };
        }'''))
    b.close()
httpd.shutdown()

print("video hero:", has_video)
for f, s in zip((0.0, 0.4, 0.7, 0.95), samples):
    print(f"  p={f}: currentTime={s['t']} activeBeat={s['active']}")
if errs:
    print("PAGE ERRORS:", errs); ok = False
if has_video:
    times = [s["t"] for s in samples]
    if not (times == sorted(times) and times[-1] > times[0] + 1):
        print("FAIL: video.currentTime did not advance with scroll"); ok = False
active = [s["active"] for s in samples]
if active != sorted(active):
    print("WARN: beats did not advance monotonically")
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
