#!/usr/bin/env python3
"""
Build dist/index.html from story.config.json + templates/ + assets/hero/.

- Injects palette + fonts into hero.css -> dist/style.css
- Renders the scroll-scrub hero (video element only if assets/hero/ascent.mp4 exists)
- Renders the body for the chosen "style" ("blog" | "proposal")
- Copies assets/hero/{scene*.jpg, ascent.mp4} into dist/assets/hero/

Usage:
  python scripts/build.py
  python scripts/build.py --config examples/blog/story.config.json --out examples/blog/dist
"""
import html, shutil, sys
from pathlib import Path
from _common import ROOT, load_config

TPL = ROOT / "templates"
GOOGLE_FONTS = ("https://fonts.googleapis.com/css2?family={serif}:wght@700;900"
                "&family={sans}:wght@400;600;700&family={display}:wght@800&display=swap")


def esc(s):
    return html.escape(str(s), quote=True)


def font_url(fonts):
    def slug(n):
        return n.replace(" ", "+")
    return GOOGLE_FONTS.format(serif=slug(fonts["serif"]), sans=slug(fonts["sans"]),
                              display=slug(fonts["display"]))


def gold_headline(headline, highlight):
    """Wrap the highlight fragment (if present) in <span class=gold>."""
    headline = esc(headline)
    if highlight:
        hl = esc(highlight)
        return f'{headline} <span class="gold">{hl}</span>' if hl not in headline \
            else headline.replace(hl, f'<span class="gold">{hl}</span>')
    return headline


def render_hero(cfg, has_video):
    hero = cfg["hero"]
    scenes = hero["scenes"]
    scene_divs = "".join(
        f'<div class="scene" data-scene="{i}">'
        f'<img src="assets/hero/scene{i+1}.jpg" alt="{esc(s.get("beat_headline", ""))}"'
        f'{"" if i == 0 else " loading=lazy"}></div>'
        for i, s in enumerate(scenes))
    video = ('<video id="ascentVid" muted playsinline preload="auto" '
             'poster="assets/hero/scene1.jpg" data-src="assets/hero/ascent.mp4"></video>'
             if has_video else "")
    last = len(scenes) - 1
    beats = []
    for i, s in enumerate(scenes):
        head = gold_headline(s.get("beat_headline", ""), s.get("beat_highlight", ""))
        tag = f'<div class="beat-tag"><span>{esc(hero.get("eyebrow", ""))}</span></div>' \
            if i == 0 and hero.get("eyebrow") else ""
        htag = "h1" if i == 0 else "h2"
        extra = ""
        if i == 0:
            cp, cs = hero.get("cta_primary", {}), hero.get("cta_secondary", {})
            extra = (f'<div class="hero-ctas">'
                     f'<a class="btn btn-primary" href="{esc(cp.get("href", "#"))}">{esc(cp.get("label", "Get started"))}</a>'
                     + (f'<a class="btn btn-ghost" href="{esc(cs.get("href", "#body"))}">{esc(cs.get("label", "Learn more"))}</a>' if cs else "")
                     + f'</div><div class="scroll-hint">{esc(hero.get("scroll_hint", "Scroll to explore"))}</div>')
        elif i == last:
            extra = f'<div class="scroll-hint">{esc(hero.get("scroll_hint_last", "Keep scrolling"))}</div>'
        center = "" if i == 0 else " beat-center"
        beats.append(f'<div class="beat{center}" data-beat="{i}">{tag}'
                     f'<{htag}>{head}</{htag}><p class="sub">{esc(s.get("beat_sub", ""))}</p>{extra}</div>')
    dots = "".join("<i></i>" for _ in scenes)
    tpl = (TPL / "hero.html.tmpl").read_text(encoding="utf-8")
    return (tpl.replace("{{VIDEO}}", video).replace("{{SCENES}}", scene_divs)
            .replace("{{BEATS}}", "".join(beats)).replace("{{DOTS}}", dots))


def render_stats(stats):
    return "".join(f'<div class="stat"><b>{esc(s["value"])}</b><span>{esc(s["label"])}</span></div>'
                   for s in stats)


def render_sections(body, style):
    out = []
    for sec in body.get("sections", []):
        label = (f'<div class="sec-label"><b>{esc(sec["number"])}</b> {esc(sec.get("label", ""))}</div>'
                 if sec.get("number") else "")
        h = f'<h2>{esc(sec["heading"])}</h2>' if sec.get("heading") else ""
        parts = [f'<p>{esc(p)}</p>' for p in sec.get("paragraphs", [])]
        if sec.get("bullets"):
            parts.append("<ul>" + "".join(f"<li>{esc(b)}</li>" for b in sec["bullets"]) + "</ul>")
        if sec.get("deliverables"):
            items = "".join(f'<div class="d-item"><div class="d-check">&#10003;</div>'
                            f'<div><h4>{esc(d["title"])}</h4><p>{esc(d.get("detail", ""))}</p></div></div>'
                            for d in sec["deliverables"])
            parts.append(f'<div class="deliv">{items}</div>')
        if sec.get("pricing"):
            cards = ""
            for c in sec["pricing"]:
                best = " best" if c.get("best") else ""
                lis = "".join(f"<li>{esc(x)}</li>" for x in c.get("features", []))
                cards += (f'<div class="price-card{best}"><div class="p-name">{esc(c.get("name", ""))}</div>'
                          f'<div class="amt">{esc(c["amount"])}</div><p>{esc(c.get("sub", ""))}</p>'
                          f'<ul>{lis}</ul></div>')
            parts.append(f'<div class="price-cards">{cards}</div>')
        out.append(f'<section class="sec rv">{label}{h}{"".join(parts)}</section>')
    return "".join(out)


def render_body(cfg, style):
    body = cfg.get("body", {})
    tpl = (TPL / f"{style}.body.html.tmpl").read_text(encoding="utf-8")
    cp, cs = cfg["hero"].get("cta_primary", {}), cfg["hero"].get("cta_secondary", {})
    cta = body.get("cta", {})
    repl = {
        "{{STATS}}": render_stats(cfg["hero"].get("stats", [])),
        "{{SECTIONS}}": render_sections(body, style),
        "{{ANSWER_LABEL}}": esc(body.get("answer_label", "In short")),
        "{{ANSWER_Q}}": esc(body.get("answer_q", "")),
        "{{ANSWER_A}}": esc(body.get("answer_a", "")),
        "{{CTA_HEADLINE}}": esc(cta.get("headline", "")),
        "{{CTA_SUB}}": esc(cta.get("sub", "")),
        "{{CTA_PRIMARY_HREF}}": esc(cp.get("href", "#")),
        "{{CTA_PRIMARY_LABEL}}": esc(cp.get("label", "Get started")),
        "{{CTA_SECONDARY_HREF}}": esc(cs.get("href", "#")),
        "{{CTA_SECONDARY_LABEL}}": esc(cs.get("label", "Learn more")),
        "{{FOOTER}}": esc(body.get("footer", cfg.get("brand", ""))),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    return tpl


def render_css(cfg):
    pal = cfg.get("palette", {})
    fonts = cfg.get("fonts", {"serif": "Merriweather", "sans": "Source Sans 3", "display": "Playfair Display"})
    css = (TPL / "hero.css").read_text(encoding="utf-8")
    repl = {
        "{{INK}}": pal.get("ink", "#1b1206"), "{{INK2}}": pal.get("ink_2", "#241706"),
        "{{GOLD}}": pal.get("gold", "#e0a526"), "{{GOLD_BRIGHT}}": pal.get("gold_bright", "#f6c453"),
        "{{CREAM}}": pal.get("cream", "#fdf7ec"), "{{TRACK_HEIGHT}}": cfg["hero"].get("track_height", "520vh"),
        "{{FONT_SERIF}}": fonts["serif"], "{{FONT_SANS}}": fonts["sans"], "{{FONT_DISPLAY}}": fonts["display"],
    }
    for k, v in repl.items():
        css = css.replace(k, v)
    return css, fonts


def main():
    cfg_path, out_dir = None, None
    if "--config" in sys.argv:
        cfg_path = sys.argv[sys.argv.index("--config") + 1]
    if "--out" in sys.argv:
        out_dir = Path(sys.argv[sys.argv.index("--out") + 1])
    cfg = load_config(cfg_path)
    style = cfg.get("style", "blog")
    if style not in ("blog", "proposal"):
        sys.exit('ERROR: style must be "blog" or "proposal".')

    # assets source: alongside the config (so examples build from their own media)
    cfg_dir = Path(cfg_path).resolve().parent if cfg_path else ROOT
    src_hero = cfg_dir / "assets" / "hero"
    if not src_hero.exists():
        src_hero = ROOT / "assets" / "hero"
    has_video = (src_hero / "ascent.mp4").exists()

    dist = out_dir or (ROOT / "dist")
    (dist / "assets" / "hero").mkdir(parents=True, exist_ok=True)

    css, fonts = render_css(cfg)
    (dist / "style.css").write_text(css, encoding="utf-8")

    page = (TPL / "page.html.tmpl").read_text(encoding="utf-8")
    nav = "".join(f'<a href="{esc(n["href"])}">{esc(n["label"])}</a>'
                  for n in cfg.get("nav", []))
    cp = cfg["hero"].get("cta_primary", {})
    repl = {
        "{{LANG}}": esc(cfg.get("lang", "en")), "{{TITLE}}": esc(cfg.get("title", cfg.get("brand", ""))),
        "{{DESCRIPTION}}": esc(cfg.get("description", "")), "{{INK}}": cfg.get("palette", {}).get("ink", "#1b1206"),
        "{{FONTS_URL}}": font_url(fonts), "{{BRAND}}": esc(cfg.get("brand", "")),
        "{{NAV}}": nav, "{{CTA_PRIMARY_HREF}}": esc(cp.get("href", "#")),
        "{{CTA_PRIMARY_LABEL}}": esc(cp.get("label", "Get started")),
        "{{HERO}}": render_hero(cfg, has_video), "{{BODY}}": render_body(cfg, style),
        "{{HERO_SCRIPT}}": (TPL / "hero.js.tmpl").read_text(encoding="utf-8"),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    (dist / "index.html").write_text(page, encoding="utf-8")

    # copy media
    for i in range(1, 5):
        f = src_hero / f"scene{i}.jpg"
        if f.exists():
            shutil.copy2(f, dist / "assets" / "hero" / f.name)
    if has_video:
        shutil.copy2(src_hero / "ascent.mp4", dist / "assets" / "hero" / "ascent.mp4")

    print(f"Built -> {dist}/index.html  (style={style}, video={'yes' if has_video else 'stills-only'})")
    print(f"Preview: python -m http.server 8000 --directory {dist}")


if __name__ == "__main__":
    main()
