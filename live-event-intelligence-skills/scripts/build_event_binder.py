#!/usr/bin/env python3
"""
Build a client-facing prospect binder from conference roster CSVs.

Why a binder and not a spreadsheet
----------------------------------
A CSV is a file you attach. A binder is a link you send — it opens on a phone,
it looks like you spent money on it, and it gets forwarded to the person who
actually signs. Same data, completely different reception.

What it produces
----------------
  index.html        full-screen splash over a photo of the host city, then the
                    binder: live consoles first, reference lists below
  <section>.html    for a console: a working outreach desk — per-row "Create
                    Gmail Draft" and "Copy Msg + Open LinkedIn"
                    for a list: searchable, sortable, filterable table

Everything is inlined. No build step, no server, no dependencies.

Usage
-----
    python -X utf8 -m scripts.build_event_binder \\
        --config data/example-binder.json --outdir dist/example

See the README for the config shape and the pitch templates.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
from datetime import date
from pathlib import Path

from scripts.common import read_csv

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600'
         '&family=Lato:wght@300;400;700&family=Overpass:wght@300;400;500;600'
         '&display=swap" rel="stylesheet">')

# Delta Vega palette. Cream paper, navy, one gold accent, Cinzel display serif
# over Lato. Deliberately an editorial document, not a dashboard.
BASE = """
:root{--brand:#1b3a5c;--dark:#0f2640;--accent:#c5985e;--accent-l:#d4ab73;
      --cream:#f9f7f3;--line:#e7e2d9;--ink:#26313d;--mut:#8a94a0;}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Lato',system-ui,Arial,sans-serif;color:var(--ink);
     background:var(--cream);font-size:14px;line-height:1.6}
a{color:var(--brand)}
.wrap{max-width:1280px;margin:0 auto;padding:30px 24px 80px}
h1{font-family:'Cinzel',Georgia,serif;font-weight:500;letter-spacing:.06em;color:var(--brand)}
h2{font-family:'Cinzel',Georgia,serif;font-weight:600;letter-spacing:.06em;color:var(--brand);
   font-size:19px;margin:34px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
"""

SPLASH = """
/* Full-screen splash. The photo of the host city is the entire first
   impression — the binder only appears once they choose to enter. */
#dvHero{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;
        justify-content:center;text-align:center;overflow:hidden;transition:opacity .7s ease}
#dvHero .bg{position:absolute;inset:0;background-size:cover;background-position:center}
#dvHero .grad{position:absolute;inset:0;background:linear-gradient(180deg,
        rgba(10,26,46,.55),rgba(15,38,64,.45) 40%,rgba(15,38,64,.62))}
#dvHero .inner{position:relative;z-index:2;padding:0 24px;max-width:820px}
#dvHero .eyebrow{font-family:'Overpass',sans-serif;font-size:11px;letter-spacing:.34em;
        text-transform:uppercase;color:rgba(255,255,255,.55);margin-bottom:22px}
#dvHero h1{font-family:'Cinzel',Georgia,serif;font-weight:400;color:#fff;letter-spacing:.09em;
        line-height:1.1;margin:0 0 8px;font-size:clamp(30px,5.6vw,62px)}
#dvHero .rule{width:54px;height:1px;background:rgba(255,255,255,.45);margin:26px auto}
#dvHero p.sub{font-size:clamp(15px,2vw,18px);color:rgba(255,255,255,.75);line-height:1.7;
        max-width:600px;margin:0 auto 40px;font-weight:300}
#dvHero .cta{display:inline-block;background:var(--accent);color:#fff;font-family:'Overpass',sans-serif;
        font-size:12px;letter-spacing:.16em;text-transform:uppercase;font-weight:500;
        padding:18px 46px;border:none;cursor:pointer;transition:background .3s,transform .3s}
#dvHero .cta:hover{background:var(--accent-l);transform:translateY(-1px)}
#dvHero .credit{position:absolute;right:14px;bottom:12px;color:rgba(255,255,255,.4);
        font-size:10px;z-index:3}
"""

INDEX_CSS = BASE + SPLASH + """
.masthead{background:linear-gradient(135deg,var(--dark) 0%,var(--brand) 60%,#24507c 100%);
   border-radius:6px;padding:34px 38px;color:#fff;margin-bottom:26px}
.masthead .eyebrow{font-family:'Overpass',sans-serif;font-size:10px;letter-spacing:.28em;
   text-transform:uppercase;color:var(--accent-l);margin-bottom:12px}
.masthead h1{color:#fff;font-size:29px;margin-bottom:8px}
.masthead .where{color:rgba(255,255,255,.7);font-size:13.5px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 6px}
.stat{background:#fff;border:1px solid var(--line);padding:12px 18px;min-width:124px;border-radius:6px}
.stat .n{font-family:'Cinzel',Georgia,serif;font-size:24px;font-weight:600;color:var(--brand);line-height:1}
.stat .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-top:5px}
.intro{color:var(--mut);font-size:14px;max-width:860px;margin:16px 0 4px}

/* Live consoles: dark navy, gold border. These are tools, not lists. */
.dv-live{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-bottom:8px}
.dv-live a{text-decoration:none;color:inherit}
.dv-live .lc{background:linear-gradient(135deg,var(--dark),var(--brand));border:1px solid var(--accent);
   border-radius:6px;padding:26px 28px;transition:all .25s;height:100%}
.dv-live .lc:hover{transform:translateY(-3px);box-shadow:0 10px 30px rgba(15,38,64,.35)}
.dv-live .tag{font-family:'Overpass',sans-serif;font-size:10px;letter-spacing:.28em;
   text-transform:uppercase;color:var(--accent-l)}
.dv-live h3{font-family:'Cinzel',Georgia,serif;color:#fff;font-weight:500;font-size:20px;
   letter-spacing:.06em;margin:8px 0 6px}
.dv-live p{color:rgba(255,255,255,.66);font-size:13px;line-height:1.6;margin:0 0 14px}
.dv-live .go{font-family:'Overpass',sans-serif;font-size:11px;letter-spacing:.14em;
   text-transform:uppercase;color:var(--accent-l)}

/* Reference lists: white cards. */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{background:#fff;border:1px solid var(--line);border-radius:6px;padding:24px 26px;
   text-decoration:none;color:inherit;display:flex;flex-direction:column;transition:all .25s;
   box-shadow:0 2px 14px rgba(27,58,92,.07)}
.card:hover{border-color:var(--accent);box-shadow:0 6px 22px rgba(27,58,92,.14);transform:translateY(-2px)}
.card .tag{font-family:'Overpass',sans-serif;font-size:10px;letter-spacing:.22em;
   text-transform:uppercase;color:var(--mut)}
.card h3{font-family:'Cinzel',Georgia,serif;font-weight:500;font-size:18px;color:var(--brand);
   letter-spacing:.04em;margin:8px 0 7px}
.card p{font-size:13px;color:var(--mut);flex:1;margin-bottom:14px;line-height:1.6}
.card .go{font-family:'Overpass',sans-serif;font-size:11px;letter-spacing:.14em;
   text-transform:uppercase;color:var(--accent)}
.foot{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
   color:var(--mut);font-size:11.5px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
@media(max-width:680px){.masthead{padding:26px 22px}.masthead h1{font-size:22px}
  .dv-live,.cards{grid-template-columns:1fr}.wrap{padding:22px 14px 60px}}
"""

TABLE_CSS = BASE + """
.bar{background:linear-gradient(135deg,var(--dark),var(--brand));padding:18px 26px;color:#fff;
     display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.bar .eyebrow{font-family:'Overpass',sans-serif;font-size:10px;letter-spacing:.28em;
     text-transform:uppercase;color:var(--accent-l);margin-bottom:6px}
.bar h1{color:#fff;font-size:22px;margin-bottom:5px}
.bar .sub{color:rgba(255,255,255,.72);font-size:12.5px;max-width:780px}
.bar .acts{display:flex;gap:10px;flex-wrap:wrap}
.btn-g{background:var(--accent);color:#fff;font-family:'Overpass',sans-serif;font-size:11px;
     letter-spacing:.12em;text-transform:uppercase;font-weight:600;padding:11px 20px;
     border:none;border-radius:4px;cursor:pointer;text-decoration:none;white-space:nowrap}
.btn-g:hover{background:var(--accent-l)}
.note{background:var(--cream);border:1px solid var(--line);border-left:3px solid var(--accent);
     padding:13px 16px;margin:20px 0 16px;line-height:1.65;font-size:13px}
.note b{color:var(--brand)}
.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px;
     position:sticky;top:0;background:var(--cream);padding:12px 0;z-index:20}
select,#q{padding:9px 13px;border:1px solid var(--line);border-radius:4px;font-size:13px;
     font-family:inherit;background:#fff;color:var(--ink)}
#q{flex:1;min-width:220px}
.cnt{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-left:auto}
.cnt b{color:var(--brand);font-size:13px}
table{width:100%;border-collapse:separate;border-spacing:0;background:#fff;
      border:1px solid var(--line);font-size:13px}
th{background:var(--cream);color:var(--brand);font-size:10.5px;text-transform:uppercase;
   letter-spacing:.08em;text-align:left;padding:11px 12px;border-bottom:1px solid var(--line);
   position:sticky;top:var(--barh,58px);z-index:10;cursor:pointer;white-space:nowrap}
th:hover{background:#f2ede4}
td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:hover td{background:#fbfaf7}
.org{font-weight:700;color:var(--brand)}
.mut{color:var(--mut);font-size:12px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:10px;font-weight:700;
   text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
.b-grn{background:#e7f3ea;color:#2e7d46}.b-amb{background:#faf1dd;color:#a9781f}
.b-gry{background:#eef0f2;color:#6b7684}
.btn{display:block;width:100%;padding:8px 12px;border:none;border-radius:4px;font-size:11.5px;
   font-weight:700;cursor:pointer;font-family:inherit;margin-bottom:5px;text-align:center;
   white-space:nowrap}
.btn.pri{background:var(--dark);color:#fff}.btn.pri:hover{background:var(--brand)}
.btn.li{background:#0a66c2;color:#fff}.btn.li:hover{background:#0956a5}
.btn.disabled{background:#f0f2f4;color:#aab2bc;cursor:default}
.btn.done{background:#2e7d46;color:#fff}
.pv{cursor:pointer;color:var(--brand);font-size:11.5px;text-decoration:underline}
.pvbox{display:none;background:var(--cream);border:1px solid var(--line);padding:11px 13px;
   margin-top:7px;font-size:12px;line-height:1.6;white-space:pre-wrap;max-width:560px}
.foot{margin-top:30px;padding-top:16px;border-top:1px solid var(--line);color:var(--mut);font-size:11.5px}
@media(max-width:680px){th{position:static}.filters{position:static}}
"""


def esc(v) -> str:
    return html.escape(str(v or ""), quote=True)


def jesc(v) -> str:
    """Safe inside a <script> JSON blob."""
    return json.dumps(str(v or ""))


def badge(conf: str) -> str:
    c = (conf or "").lower()
    cls = {"confirmed": "b-grn", "probable": "b-amb"}.get(c, "b-gry")
    return f'<span class="badge {cls}">{esc(c or "unknown")}</span>' if c else '<span class="mut">—</span>'


def build_console(section, rows, cfg, outdir) -> dict:
    """
    A console is a table you can act from: one Gmail draft and one LinkedIn
    message per row, pre-filled from the pitch templates.

    Nothing sends automatically. Every button opens a draft the user reviews
    first — outreach that goes out unread is how a domain gets burned.
    """
    pitches = cfg.get("pitches", {})
    default_pitch = section.get("pitch") or "default"
    sender = cfg.get("sender", {})

    data = []
    for i, r in enumerate(rows):
        first = (r.get("person_name") or "").split()[0] if r.get("person_name") else ""
        data.append({
            "id": i,
            "name": r.get("person_name", ""),
            "first": first,
            "title": r.get("title", ""),
            "org": r.get("organization", ""),
            "email": r.get("email", ""),
            "linkedin": r.get("linkedin_url", ""),
            "website": r.get("website", ""),
            "conf": (r.get("confidence") or "").lower(),
            "role": r.get("role_type", ""),
            "pitch": r.get("pitch") or default_pitch,
        })

    # Reachable rows first. A console opens on whatever is at the top, and a
    # first screen of "No email / No LinkedIn" makes a good list look empty.
    # Email beats LinkedIn, LinkedIn beats nothing, then confirmed, then name.
    data.sort(key=lambda d: (
        0 if d["email"] else (1 if d["linkedin"] else 2),
        0 if d["conf"] == "confirmed" else 1,
        (d["name"] or d["org"] or "").lower(),
    ))
    for n, d in enumerate(data):
        d["id"] = n

    roles = sorted({d["role"] for d in data if d["role"]})
    confs = sorted({d["conf"] for d in data if d["conf"]})
    n_email = sum(1 for d in data if d["email"])
    n_li = sum(1 for d in data if d["linkedin"])

    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(cfg['title'])} — {esc(section['label'])}</title>{FONTS}
<style>{TABLE_CSS}</style></head><body>
<div class="bar">
  <div><div class="eyebrow">{esc(cfg.get('subtitle','Conference Prospect Binder'))}</div>
    <h1>{esc(section['label'])}</h1>
    <div class="sub">{esc(section.get('console_sub', section.get('blurb','')))}</div></div>
  <div class="acts">
    <a class="btn-g" href="index.html">&larr; Binder</a>
    <a class="btn-g" href="{esc(section['id'])}.csv" download>&darr; Download CSV</a>
  </div>
</div>
<div class="wrap">
<div class="note">{section.get('legend', '')}</div>
<div class="filters">
  <input id="q" placeholder="Search name / company / email&hellip;"/>
  {'<select id="fr"><option value="">All roles</option>' + ''.join(f'<option>{esc(r)}</option>' for r in roles) + '</select>' if roles else ''}
  {'<select id="fc"><option value="">All confidence</option>' + ''.join(f'<option>{esc(c)}</option>' for c in confs) + '</select>' if confs else ''}
  <select id="fh"><option value="">Everyone</option><option value="email">Has email</option>
    <option value="li">Has LinkedIn</option><option value="either">Reachable now</option></select>
  <span class="cnt"><b id="cnt">{len(data)}</b> shown</span>
</div>
<table><thead><tr>
  <th>#</th><th>Name</th><th>Title</th><th>Company</th><th>Contact</th><th>Confidence</th><th>Actions</th>
</tr></thead><tbody id="tb"></tbody></table>
<div class="foot">{len(data)} rows &middot; {n_email} with an email &middot; {n_li} with a LinkedIn profile.
Nothing sends automatically — every button opens a draft you review first.</div>
</div>
<script>
const ROWS = {json.dumps(data, ensure_ascii=False)};
const PITCHES = {json.dumps(pitches, ensure_ascii=False)};
const SENDER = {json.dumps(sender, ensure_ascii=False)};
const EVENT = {jesc(cfg.get('title',''))};
const DATES = {jesc(cfg.get('event_dates',''))};
const CITY  = {jesc(cfg.get('city',''))};

function fill(tpl, r){{
  return (tpl||"")
    .replace(/\\{{first\\}}/g, r.first || "there")
    .replace(/\\{{name\\}}/g, r.name || "")
    .replace(/\\{{title\\}}/g, r.title || "")
    .replace(/\\{{company\\}}/g, r.org || "")
    .replace(/\\{{event\\}}/g, EVENT)
    .replace(/\\{{dates\\}}/g, DATES)
    .replace(/\\{{city\\}}/g, CITY)
    .replace(/\\{{sender\\}}/g, SENDER.name || "")
    .replace(/\\{{signature\\}}/g, SENDER.signature || "");
}}
function pitchFor(r){{ return PITCHES[r.pitch] || PITCHES["default"] || {{subject:"",body:"",linkedin:""}}; }}

function createDraft(id, btn){{
  const r = ROWS[id], p = pitchFor(r);
  const url = "https://mail.google.com/mail/?view=cm&fs=1"
    + "&to=" + encodeURIComponent(r.email)
    + "&su=" + encodeURIComponent(fill(p.subject, r))
    + "&body=" + encodeURIComponent(fill(p.body, r));
  window.open(url, "_blank", "noopener");
  btn.textContent = "Draft opened \\u2713"; btn.classList.add("done");
}}
function openLinkedIn(id){{
  const r = ROWS[id], p = pitchFor(r);
  const msg = fill(p.linkedin, r);
  navigator.clipboard.writeText(msg).catch(()=>{{}});
  window.open(r.linkedin, "_blank", "noopener");
}}
function preview(id, el){{
  const box = el.parentNode.querySelector(".pvbox");
  if(box.style.display === "block"){{ box.style.display = "none"; return; }}
  const r = ROWS[id], p = pitchFor(r);
  box.textContent = "SUBJECT: " + fill(p.subject, r) + "\\n\\n" + fill(p.body, r)
    + (r.linkedin ? "\\n\\n--- LINKEDIN ---\\n" + fill(p.linkedin, r) : "");
  box.style.display = "block";
}}

function contactCell(r){{
  let out = "";
  if(r.email) out += '<div>' + r.email + '</div>';
  if(r.website) out += '<div class="mut"><a href="' + r.website + '" target="_blank" rel="noopener">'
     + r.website.replace(/^https?:\\/\\/(www\\.)?/,"").replace(/\\/$/,"").slice(0,30) + ' \\u2197</a></div>';
  return out || '<span class="mut">\\u2014</span>';
}}
function badgeFor(c){{
  if(!c) return '<span class="mut">\\u2014</span>';
  const cls = c==="confirmed" ? "b-grn" : (c==="probable" ? "b-amb" : "b-gry");
  return '<span class="badge '+cls+'">'+c+'</span>';
}}
function render(){{
  const q  = (document.getElementById("q").value||"").toLowerCase();
  const fr = document.getElementById("fr") ? document.getElementById("fr").value : "";
  const fc = document.getElementById("fc") ? document.getElementById("fc").value : "";
  const fh = document.getElementById("fh").value;
  let n = 0, out = "";
  ROWS.forEach(r => {{
    if(q && !((r.name+" "+r.org+" "+r.email+" "+r.title).toLowerCase().includes(q))) return;
    if(fr && r.role !== fr) return;
    if(fc && r.conf !== fc) return;
    if(fh === "email" && !r.email) return;
    if(fh === "li" && !r.linkedin) return;
    if(fh === "either" && !r.email && !r.linkedin) return;
    n++;
    const draft = r.email
      ? '<button class="btn pri" onclick="createDraft('+r.id+',this)">Create Gmail Draft</button>'
      : '<span class="btn disabled">No email</span>';
    const li = r.linkedin
      ? '<button class="btn li" onclick="openLinkedIn('+r.id+')">Copy Msg + Open LinkedIn</button>'
      : '<span class="btn disabled">No LinkedIn</span>';
    out += '<tr><td class="mut">'+(r.id+1)+'</td>'
      + '<td class="org">'+(r.name||'<span class="mut">\\u2014</span>')+'</td>'
      + '<td class="mut">'+(r.title||'')+'</td>'
      + '<td>'+(r.org||'')+'</td>'
      + '<td>'+contactCell(r)+'</td>'
      + '<td>'+badgeFor(r.conf)+'</td>'
      + '<td>'+draft+li
      + '<span class="pv" onclick="preview('+r.id+',this)">preview message</span>'
      + '<div class="pvbox"></div></td></tr>';
  }});
  document.getElementById("tb").innerHTML = out;
  document.getElementById("cnt").textContent = n;
}}
["q","fr","fc","fh"].forEach(id => {{
  const el = document.getElementById(id);
  if(el) el.addEventListener(id === "q" ? "input" : "change", render);
}});
function syncBar(){{ const b=document.querySelector(".filters");
  if(b) document.documentElement.style.setProperty("--barh", b.offsetHeight+"px"); }}
syncBar(); window.addEventListener("resize", syncBar);
render();
</script></body></html>"""
    (outdir / f"{section['id']}.html").write_text(page, encoding="utf-8")
    return {"rows": len(rows), "email": n_email, "linkedin": n_li,
            "confirmed": sum(1 for d in data if d["conf"] == "confirmed")}


def build_list(section, rows, cfg, outdir) -> dict:
    """A reference list: read, search, sort, export. No actions."""
    cols = section.get("columns") or [
        c for c in ["person_name", "title", "organization", "linkedin_url", "website", "confidence"]
        if any((r.get(c) or "").strip() for r in rows)
    ]
    PRETTY = {"person_name": "Name", "title": "Title", "organization": "Company",
              "linkedin_url": "LinkedIn", "email": "Email", "website": "Website",
              "role_type": "Role", "confidence": "Confidence", "source": "Source"}

    body = []
    for r in rows:
        hay = " ".join(str(r.get(c, "")) for c in cols).lower()
        tds = ""
        for i, c in enumerate(cols):
            v = (r.get(c) or "").strip()
            if c == "confidence":
                cell = badge(v)
            elif c == "linkedin_url" and v:
                cell = f'<a href="{esc(v)}" target="_blank" rel="noopener">profile &#8599;</a>'
            elif c == "website" and v:
                lab = v.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
                cell = f'<a href="{esc(v)}" target="_blank" rel="noopener">{esc(lab[:30])} &#8599;</a>'
            elif c == "source" and v.startswith("http"):
                cell = f'<a href="{esc(v)}" target="_blank" rel="noopener">page &#8599;</a>'
            elif not v:
                cell = '<span class="mut">&mdash;</span>'
            else:
                cell = esc(v[:160])
            klass = ' class="org"' if i == 0 and c in ("person_name", "organization") else ""
            tds += f"<td{klass}>{cell}</td>"
        body.append(f'<tr data-hay="{esc(hay)}">{tds}</tr>')

    ths = "".join(f'<th>{esc(PRETTY.get(c, c.replace("_", " ").title()))}</th>' for c in cols)
    n_li = sum(1 for r in rows if (r.get("linkedin_url") or "").strip())
    n_cf = sum(1 for r in rows if (r.get("confidence") or "").lower() == "confirmed")

    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(cfg['title'])} — {esc(section['label'])}</title>{FONTS}
<style>{TABLE_CSS}</style></head><body>
<div class="bar">
  <div><div class="eyebrow">{esc(cfg.get('subtitle','Conference Prospect Binder'))}</div>
    <h1>{esc(section['label'])}</h1>
    <div class="sub">{esc(section.get('blurb',''))}</div></div>
  <div class="acts">
    <a class="btn-g" href="index.html">&larr; Binder</a>
    <a class="btn-g" href="{esc(section['id'])}.csv" download>&darr; Download CSV</a>
  </div>
</div>
<div class="wrap">
<div class="filters">
  <input id="q" placeholder="Search&hellip;"/>
  <span class="cnt"><b id="cnt">{len(rows)}</b> shown</span>
</div>
<table><thead><tr>{ths}</tr></thead><tbody>{''.join(body)}</tbody></table>
<div class="foot">{len(rows)} rows &middot; {n_cf} confirmed &middot; {n_li} with LinkedIn.
Click a column heading to sort.</div>
</div>
<script>
const rows=[...document.querySelectorAll('tbody tr')];
const q=document.getElementById('q'),cnt=document.getElementById('cnt');
q.addEventListener('input',()=>{{const t=q.value.toLowerCase();let n=0;
  rows.forEach(r=>{{const s=!t||r.dataset.hay.includes(t);r.style.display=s?'':'none';if(s)n++;}});
  cnt.textContent=n;}});
document.querySelectorAll('th').forEach((th,i)=>th.addEventListener('click',()=>{{
  const tb=th.closest('table').querySelector('tbody');
  const asc=th.dataset.asc!=='1';th.dataset.asc=asc?'1':'0';
  [...tb.querySelectorAll('tr')].sort((a,b)=>{{
    const x=a.children[i].innerText.trim().toLowerCase(),y=b.children[i].innerText.trim().toLowerCase();
    if(!x)return 1;if(!y)return -1;return asc?x.localeCompare(y):y.localeCompare(x);}})
    .forEach(r=>tb.appendChild(r));}}));
function syncBar(){{const b=document.querySelector('.filters');
  if(b)document.documentElement.style.setProperty('--barh',b.offsetHeight+'px');}}
syncBar();window.addEventListener('resize',syncBar);
</script></body></html>"""
    (outdir / f"{section['id']}.html").write_text(page, encoding="utf-8")
    return {"rows": len(rows), "email": 0, "linkedin": n_li, "confirmed": n_cf}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a conference prospect binder")
    ap.add_argument("--config", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    consoles, lists = [], []
    stats = {}
    total = 0
    orgs: set[str] = set()

    for section in cfg["sections"]:
        p = Path(section["csv"])
        if not p.exists():
            print(f"  skip {section['id']}: {p} not found")
            continue
        rows = read_csv(p)
        if not rows:
            print(f"  skip {section['id']}: empty")
            continue

        is_console = bool(section.get("console"))
        s = (build_console if is_console else build_list)(section, rows, cfg, outdir)
        shutil.copy(p, outdir / f"{section['id']}.csv")
        stats[section["id"]] = s
        total += s["rows"]
        orgs |= {(r.get("organization") or "").strip().lower()
                 for r in rows if (r.get("organization") or "").strip()}

        if is_console:
            # Say what the console can actually do. Advertising "one-click Gmail
            # drafts" on a list with no email addresses is a promise the page
            # cannot keep, and the user finds out only after clicking in.
            if section.get("tag"):
                tag = section["tag"]
            elif s["email"] and s["linkedin"]:
                tag = "Gmail drafts + LinkedIn &middot; Live tool"
            elif s["email"]:
                tag = "One-click Gmail drafts &middot; Live tool"
            elif s["linkedin"]:
                tag = "LinkedIn messages &middot; Live tool"
            else:
                tag = "Outreach console"
            consoles.append(f"""<a href="{esc(section['id'])}.html"><div class="lc">
  <div class="tag">{tag}</div>
  <h3>{esc(section['label'])}</h3>
  <p>{esc(section.get('blurb',''))}</p>
  <div class="go">Open console &rarr;</div></div></a>""")
        else:
            lists.append(f"""<a class="card" href="{esc(section['id'])}.html">
  <div class="tag">{esc(section.get('tag','Research list'))}</div>
  <h3>{esc(section['label'])}</h3>
  <p>{esc(section.get('blurb',''))}</p>
  <div class="go">Open list &rarr;</div></a>""")
        print(f"  {section['id']}: {s['rows']} rows{' (console)' if is_console else ''}")

    n_cf = sum(s["confirmed"] for s in stats.values())
    n_li = sum(s["linkedin"] for s in stats.values())
    n_em = sum(s["email"] for s in stats.values())
    tiles = [(total, "Total records"), (len(orgs), "Companies")]
    if n_cf: tiles.append((n_cf, "Confirmed"))
    if n_li: tiles.append((n_li, "LinkedIn"))
    if n_em: tiles.append((n_em, "Emails"))
    tiles_html = "".join(
        f'<div class="stat"><div class="n">{n}</div><div class="l">{esc(l)}</div></div>'
        for n, l in tiles)

    # Copy the hero into the output so the binder is a self-contained folder.
    # Without this the splash renders transparent and the whole first
    # impression is missing — with no error to tell you why.
    hero = cfg.get("hero_image", "")
    if hero and not hero.startswith(("http://", "https://", "data:")):
        src = Path(hero)
        if src.exists():
            dest = outdir / hero
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)
        else:
            print(f"  WARNING: hero image not found at {src} — the splash will be blank")

    where = " &middot; ".join(esc(x) for x in
                             [cfg.get("event_dates"), cfg.get("venue"), cfg.get("city")] if x)
    splash_title = cfg.get("splash_title") or cfg.get("title", "")
    today = date.today()
    built = f"{today:%B} {today.day}, {today.year}"

    index = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(cfg['title'])} — {esc(cfg.get('subtitle','Prospect Binder'))}</title>{FONTS}
<style>{INDEX_CSS}</style></head><body>

<div id="dvHero">
  <div class="bg" style="background-image:url('{esc(hero)}')"></div>
  <div class="grad"></div>
  <div class="inner">
    <div class="eyebrow">{esc(cfg.get('subtitle','Conference Prospect Binder'))}</div>
    <h1>{splash_title}</h1>
    <div class="rule"></div>
    <p class="sub">{esc(cfg.get('splash_sub', cfg.get('intro','')))}</p>
    <button class="cta" onclick="var h=document.getElementById('dvHero');h.style.opacity='0';setTimeout(function(){{h.style.display='none';}},600);">Access the Lists</button>
  </div>
  {f'<div class="credit">{esc(cfg["hero_credit"])}</div>' if cfg.get("hero_credit") else ""}
</div>

<div class="wrap">
<div class="masthead">
  <div class="eyebrow">{esc(cfg.get('subtitle','Conference Prospect Binder'))}</div>
  <h1>{esc(cfg['title'])}</h1>
  <div class="where">{where}</div>
</div>
{f'<div class="intro">{esc(cfg["intro"])}</div>' if cfg.get("intro") else ""}
<div class="stats">{tiles_html}</div>
{f'<h2>&#9889; Live Outreach Consoles</h2><div class="dv-live">{"".join(consoles)}</div>' if consoles else ""}
{f'<h2>Research Lists</h2><div class="cards">{"".join(lists)}</div>' if lists else ""}
<div class="foot">
  <span>Built {built}{f" for {esc(cfg['owner'])}" if cfg.get("owner") else ""}</span>
  <span><span class="badge b-grn">confirmed</span> verified &middot;
  <span class="badge b-amb">probable</span> check first &middot;
  <span class="badge b-gry">weak</span> verify before contacting</span>
</div></div></body></html>"""
    (outdir / "index.html").write_text(index, encoding="utf-8")

    print(f"\n{'=' * 62}")
    print(f"Binder -> {outdir / 'index.html'}")
    print(f"  {total} records | {len(consoles)} consoles | {len(lists)} lists | {len(orgs)} companies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
