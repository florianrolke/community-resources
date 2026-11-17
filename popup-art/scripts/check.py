"""Check the pop-up art in a real browser before anything goes live.

    python check.py art.json --page example/index.html
    python check.py art.json --page https://example.com/blog/post/ --serve https://example.com/=dist/
    python check.py art.json --page https://example.com/blog/post/ --trigger exit --wait 9

For each window size (desktop 1600x900, short wide 1536x791, laptop 1280x720, tablet 820x1000, phone 390x800) it opens
the page, opens the pop-up, waits for the art and saves a screenshot to shots/<tag>-<size>.png. It then reloads once at
1536x791 to check speed (no art file may be requested before the page's load event) and, with --trigger exit, waits and
fires an exit intent to see the pop-up open by the site's own rules with its art.

--serve URL_PREFIX=FOLDER answers every request under that address from a local folder, so you can test the real
address of a page before you deploy. Prints one JSON line per check. Needs: pip install playwright; playwright install
chromium (or pass --channel chrome to use an installed Chrome).
"""
import argparse
import json
import mimetypes
import pathlib

from playwright.sync_api import sync_playwright

SIZES = (("desktop", 1600, 900), ("short-wide", 1536, 791), ("laptop", 1280, 720), ("tablet", 820, 1000), ("phone", 390, 800))
STATE = """() => { const a=[...document.querySelectorAll('.rp-art img')];
  return {pieces:a.length, shown:a.filter(i=>getComputedStyle(i).display!=='none').length,
          loaded:a.filter(i=>i.complete&&i.naturalWidth>0).length,
          broken:a.filter(i=>i.complete&&i.getAttribute('src')&&i.naturalWidth===0).map(i=>i.getAttribute('src'))}; }"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--page", required=True, help="local HTML file or URL")
    ap.add_argument("--serve", action="append", default=[], help="URL_PREFIX=FOLDER")
    ap.add_argument("--tag", default="check")
    ap.add_argument("--out", default="shots")
    ap.add_argument("--trigger", choices=["none", "exit"], default="none")
    ap.add_argument("--wait", type=float, default=9, help="seconds before the exit intent (site rules often wait 5 to 8 s)")
    ap.add_argument("--scroll", type=int, default=900, help="pixels to scroll before the exit intent (some pop-ups need reading first)")
    ap.add_argument("--channel", default=None)
    a = ap.parse_args()
    cfg = json.loads(pathlib.Path(a.config).read_text(encoding="utf-8"))["popup"]
    root, kind, open_class = cfg["root"], cfg["kind"], cfg.get("open_class", "is-open")
    page = a.page if "://" in a.page else pathlib.Path(a.page).resolve().as_uri()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    serve = [s.split("=", 1) for s in a.serve]
    opener = (f"() => {{ const d=document.querySelector({json.dumps(root)}); if(!d) return 'no pop-up';"
              f" if(d.showModal&&!d.open) {{ d.showModal(); return 'dialog'; }}"
              f" d.classList.add({json.dumps(open_class)}); d.setAttribute('aria-hidden','false'); return 'class'; }}")

    def handler(prefix, folder):
        # a one-argument handler: Playwright passes (route, request) to handlers that take two or more arguments
        def handle(r):
            rel = r.request.url.split("#")[0].split("?")[0][len(prefix):]
            f = folder / (rel + "index.html" if rel.endswith("/") or not rel else rel)
            if f.is_file():
                r.fulfill(status=200, body=f.read_bytes(), headers={"content-type": mimetypes.guess_type(str(f))[0] or "application/octet-stream"})
            else:
                r.fulfill(status=404, body=b"")
        return handle

    def route(ctx):
        for prefix, folder in serve:
            ctx.route(prefix + "**", handler(prefix, pathlib.Path(folder)))

    with sync_playwright() as p:
        b = p.chromium.launch(channel=a.channel) if a.channel else p.chromium.launch()
        for name, vw, vh in SIZES:
            ctx = b.new_context(viewport={"width": vw, "height": vh})
            route(ctx)
            pg = ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(page, wait_until="load")
            pg.wait_for_timeout(1500)
            how = pg.evaluate(opener)
            pg.wait_for_timeout(2600)
            pg.screenshot(path=str(out / f"{a.tag}-{name}.png"))
            print(json.dumps({"size": name, "opened": how, **pg.evaluate(STATE), "errors": errors[:3]}))
            ctx.close()
        ctx = b.new_context(viewport={"width": 1536, "height": 791})
        route(ctx)
        pg = ctx.new_page()
        pg.goto(page, wait_until="load")
        pg.wait_for_timeout(1500)
        # the browser's own timing: every art file must start at or after the load event
        early = pg.evaluate("""() => { const nav=performance.getEntriesByType('navigation')[0];
          return performance.getEntriesByType('resource').filter(e=>/popup-art\/[^\/?#]+([?#].*)?$/.test(e.name)&&e.startTime<nav.loadEventStart)
            .map(e=>e.name); }""")
        result = {"check": "speed", "art_requests_before_load": early, "passed": not early}
        if page.startswith("file:"):  # Chrome keeps no resource timing for files opened from disk
            result.update(passed=None, note="speed check needs an http(s) address: use --page https://site.test/... --serve https://site.test/=FOLDER")
        if a.trigger == "exit":
            pg.mouse.wheel(0, a.scroll)
            pg.wait_for_timeout(int(a.wait * 1000))
            pg.mouse.move(700, 300)
            pg.mouse.move(700, 2)
            pg.evaluate("document.dispatchEvent(new MouseEvent('mouseout',{clientY:0,clientX:700,relatedTarget:null,bubbles:true}))")
            pg.wait_for_timeout(2500)
            opened = pg.evaluate(f"() => {{ const d=document.querySelector({json.dumps(root)}); return !!d&&(d.open||d.classList.contains({json.dumps(open_class)})); }}")
            result.update(trigger="exit", opened_by_site=opened, **pg.evaluate(STATE))
        print(json.dumps(result))
        ctx.close()
        b.close()


if __name__ == "__main__":
    main()
