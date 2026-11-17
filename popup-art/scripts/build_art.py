"""Build the pop-up art bundle from art.json: cut out every piece, then write one script, popup-art.js, that adds the
pictures around the site's existing pop-up, plus the one-line loader that fetches it after the page has loaded.

    python build_art.py art.json                 cut out all pieces and write the bundle
    python build_art.py art.json --skip-cutout   reuse existing cutouts (after changing only positions or styles)

Output in "out_dir": <piece>-1x.webp, <piece>.webp, <piece>-cutout.png, popup-art.js, loader.js, report.json.
Put the loader line into a script every page already loads (append it), or inline before </body> as <script>...</script>.
The page then requests nothing extra before its load event: the art never slows the page down.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cutout import cutout  # noqa: E402

BACKDROP = ("background:radial-gradient(ellipse at 50% 45%,rgba(30,32,20,.5),rgba(14,16,9,.66) 80%);"
            "backdrop-filter:blur(1px);-webkit-backdrop-filter:blur(1px)")
SHINE = ("content:\"\";position:absolute;top:-20%;bottom:-20%;left:0;width:38%;pointer-events:none;"
         "background:linear-gradient(100deg,rgba(255,255,255,0),rgba(255,244,214,.5) 45%,rgba(255,255,255,.62) 50%,"
         "rgba(255,244,214,.5) 55%,rgba(255,255,255,0));transform:translateX(-130%) skewX(-20deg)")

ENGINE = r"""/* Pop-up art. Fetched only after the page has finished loading; adds pictures around the site's own pop-up.
   The pop-up itself (wording, buttons, when it opens) is not changed. To go back: remove the loader line. */
(function(){
  if(window.__popupArt) return; window.__popupArt=1;
  var me=document.currentScript&&document.currentScript.src; if(!me) return;
  var base=me.replace(/[^\/]*$/,'');
  var A=__CONFIG__;
  var d=document.querySelector(A.root); if(!d||d.querySelector('.rp-art')) return;
  var card;
  if(A.kind==='wrap'){ card=document.createElement('div'); card.className=A.cardClass; while(d.firstChild) card.appendChild(d.firstChild); d.appendChild(card); }
  else { card=d.querySelector(A.card); if(!card) return; }
  var st=document.createElement('style'); st.textContent=A.css; document.head.appendChild(st);
  var back=A.back.split('__ART__/').join(base), front=A.front.split('__ART__/').join(base);
  if(A.kind==='overlay'){ var s=document.createElement('div'); s.className='rp-stage'; card.parentNode.insertBefore(s,card);
    s.insertAdjacentHTML('beforeend',back); s.appendChild(card); s.insertAdjacentHTML('beforeend',front); }
  else { card.insertAdjacentHTML('beforebegin',back); d.insertAdjacentHTML('beforeend',front); }
  function isOpen(){ return d.open||d.classList.contains(A.openClass); }
  if(location.hash==='#preview-popup'&&A.kind==='overlay'&&!isOpen()){ d.classList.add(A.openClass); d.setAttribute('aria-hidden','false'); }
  // Pictures: set only now, at idle, after the page's own pictures near the screen have arrived, or at once when the
  // pop-up opens. Pieces hidden at this screen size are never fetched.
  var hi=(window.devicePixelRatio||1)>1.3;
  function load(){ d.querySelectorAll('.rp-art img[data-src]').forEach(function(i){
    if(getComputedStyle(i).display==='none') return; i.src=hi&&i.dataset.src2x?i.dataset.src2x:i.dataset.src; i.removeAttribute('data-src'); }); }
  function idle(){ var done=false,go=function(){if(done)return;done=true;(window.requestIdleCallback||function(f){setTimeout(f,300);})(load,{timeout:4000});};
    var busy=[].filter.call(document.images,function(i){return !i.complete&&!i.closest('.rp-art')&&i.getBoundingClientRect().top<innerHeight*2;});
    var left=busy.length; if(!left) return go();
    busy.forEach(function(i){var f=function(){if(--left<=0)go();};i.addEventListener('load',f,{once:true});i.addEventListener('error',f,{once:true});});
    setTimeout(go,6000); }
  if(document.readyState==='complete') idle(); else window.addEventListener('load',idle);
  function ifOpen(){ if(isOpen()) load(); }
  new MutationObserver(ifOpen).observe(d,{attributes:true,attributeFilter:['open','class']}); ifOpen();
  var rt=0; window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(load,400);});
  // depth: pieces move a few pixels with the pointer, nearer pieces more
  if(!window.matchMedia||matchMedia('(prefers-reduced-motion:reduce)').matches) return;
  var raf=0,x=0,y=0;
  d.addEventListener('pointermove',function(e){ x=(e.clientX/innerWidth-.5); y=(e.clientY/innerHeight-.5);
    if(!raf) raf=requestAnimationFrame(function(){raf=0;d.style.setProperty('--px',(-x).toFixed(3));d.style.setProperty('--py',(-y).toFixed(3));}); });
})();
"""


def css_for(cfg):
    p = cfg["popup"]
    kind, root, card = p["kind"], p["root"], p["card"]
    open_sel = root + "." + p.get("open_class", "is-open") if kind == "overlay" else root + "[open]"
    card_css = cfg.get("card_css", "")
    lighter = cfg.get("backdrop", "lighter") == "lighter"
    out = []
    if kind == "overlay":
        if lighter:
            out.append(f"{root}{{{BACKDROP}}}")
        out.append(f"{root} .rp-stage{{position:relative;z-index:1;width:min({p.get('stage_width', '520px')},100%);pointer-events:none}}")
        out.append(f"{root} .rp-stage>{card}{{pointer-events:auto;position:relative;z-index:2;width:100%;max-width:none;box-sizing:border-box;"
                   f"max-height:calc(100dvh - 40px);overflow:auto;overscroll-behavior:contain;{card_css}}}")
        if p.get("min_height"):
            out.append(f"@media(min-width:601px){{{root} .rp-stage>{card}{{min-height:{p['min_height']};display:flex;flex-direction:column;justify-content:center}}}}")
        card_sel = f"{root} .rp-stage>{card}"
    else:
        out.append(f"{root}{{overflow:visible;background:transparent;border:0;padding:0;box-shadow:none;border-radius:0;max-height:none;"
                   f"width:min({p.get('width', '560px')},calc(100% - 32px))}}")
        if lighter:
            out.append(f"{root}::backdrop{{{BACKDROP}}}")
        card_sel = f"{root} .{p['card'].lstrip('.')}" if kind == "wrap" else f"{root} {card}"
        out.append(f"{card_sel}{{position:relative;z-index:2;max-height:calc(100dvh - 40px);overflow:auto;overscroll-behavior:contain;{card_css}}}")
    out.append(".rp-art{position:absolute;inset:0;pointer-events:none;z-index:1}.rp-art--front{z-index:3}")
    out.append(".rp-art>*{position:absolute;max-width:none;display:block;user-select:none;will-change:transform;opacity:0;"
               "transform:translate3d(calc(var(--px,0)*var(--d,0)*1px),calc(var(--py,0)*var(--d,0)*1px),0)}.rp-art>img{height:auto}")
    out.append(f"{open_sel} .rp-art>*{{animation:rp-in 1.1s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--delay,0s)}}")
    out.append("@keyframes rp-in{from{opacity:0;translate:var(--fx,0) var(--fy,0)}to{opacity:1;translate:0 0}}")
    if p.get("button"):
        b = p["button"]
        out.append(f"{b}{{position:relative;overflow:hidden;transition:transform .18s ease,box-shadow .18s ease}}"
                   f"{b}:hover{{transform:scale({cfg.get('hover_scale', 1.06)})}}{b}::after{{{SHINE}}}{b}:hover::after{{animation:rp-shine .85s ease-out}}"
                   "@keyframes rp-shine{from{transform:translateX(-130%) skewX(-20deg)}to{transform:translateX(330%) skewX(-20deg)}}")
    for pc in cfg["pieces"]:
        fx, fy = pc.get("from", [0, 0])
        shadow = pc.get("shadow", "drop-shadow(0 14px 20px rgba(0,0,0,.45))")
        out.append(f".rp-art .{pc['name']}{{{pc['style']};--d:{pc.get('depth', 10)};--fx:{fx}px;--fy:{fy}px;--delay:{pc.get('delay', 0.2)}s"
                   + (f";filter:{shadow}" if shadow else "") + "}")
    out.extend(cfg.get("media", []))
    out.append(f"@media(prefers-reduced-motion:reduce){{{open_sel} .rp-art>*{{animation:none;opacity:1}}.rp-art>*{{transform:none}}}}")
    out.append("@media print{.rp-art{display:none}}")
    out.append(cfg.get("extra_css", ""))
    return "\n".join(x for x in out if x), card_sel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--skip-cutout", action="store_true")
    a = ap.parse_args()
    cf = pathlib.Path(a.config)
    cfg = json.loads(cf.read_text(encoding="utf-8"))
    src_dir = cf.parent / cfg.get("source_dir", "source-art")
    out = cf.parent / cfg.get("out_dir", "popup-art")
    out.mkdir(parents=True, exist_ok=True)
    report = {"pieces": []}
    layers = {"back": [], "front": []}
    for pc in cfg["pieces"]:
        name = pc["name"]
        if a.skip_cutout:
            sizes = json.loads((out / "report.json").read_text(encoding="utf-8"))
            info = next(x for x in sizes["pieces"] if x["name"] == name)
        else:
            src = next((s for s in (src_dir / f"{name}{ext}" for ext in (".png", ".jpg", ".jpeg", ".webp")) if s.is_file()), None)
            assert src, f"no source picture for {name} in {src_dir}"
            opts = dict(pc.get("cutout", {}))
            for k in ("fade", "crop", "grabcut"):
                if k in opts and opts[k] is not None:
                    opts[k] = tuple(opts[k])
            info = cutout(src, out, name, css_w=pc.get("css_w", 600), **opts)
        report["pieces"].append(info)
        layers[pc.get("layer", "back")].append(
            f'<img class="{name}" data-src="__ART__/{name}-1x.webp" data-src2x="__ART__/{name}.webp" alt="" '
            f'width="{info["w"]}" height="{info["h"]}" decoding="async">')
    css, card_sel = css_for(cfg)
    p = cfg["popup"]
    config = {"root": p["root"], "card": p["card"], "cardClass": p["card"].lstrip("."), "kind": p["kind"],
              "openClass": p.get("open_class", "is-open"), "css": css,
              "back": '<div class="rp-art" aria-hidden="true">' + "".join(layers["back"]) + "</div>",
              "front": '<div class="rp-art rp-art--front" aria-hidden="true">' + "".join(layers["front"]) + "</div>"}
    (out / "popup-art.js").write_text(ENGINE.replace("__CONFIG__", json.dumps(config, ensure_ascii=False)), encoding="utf-8", newline="\n")
    url = cfg.get("public_url", "/popup-art/popup-art.js")
    version = cfg.get("version", "1")
    loader = ("/* popup-art: the art around the pop-up is fetched only after the page has finished loading */\n"
              "(function(){function a(){var s=document.createElement('script');s.src='" + url + "?v=" + version + "';s.async=true;"
              "document.head.appendChild(s);}if(document.readyState==='complete')a();else window.addEventListener('load',a);})();\n")
    (out / "loader.js").write_text(loader, encoding="utf-8", newline="\n")
    report.update(script_kb=round((out / "popup-art.js").stat().st_size / 1024, 1),
                  pictures_kb=sum(f["kb"] for x in report["pieces"] for f in x["files"]), card_selector=card_sel, loader=loader)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "pieces"}, indent=2))


if __name__ == "__main__":
    main()
