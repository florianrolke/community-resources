"""Build an AEO blog from Markdown content.

Reads content/**/*.md (frontmatter + markdown), renders each page through
templates/base.html, and writes a complete static site to public/:

  - one folder-style URL per page (public/<section>/<slug>/index.html)
  - JSON-LD per page: Article (+ FAQPage when faqs present) + BreadcrumbList;
    the configured entity on the homepage, contact page, and about page
  - sitemap.xml, robots.txt, llms.txt
  - templates/style.css copied to public/style.css

No server-side anything. Cloudflare Pages (or any static host) serves
public/ as-is.

Usage:  python execution/build_site.py
Deps:   pip install markdown python-frontmatter
"""

import json
import html
import shutil
import sys
from datetime import date
from pathlib import Path

import frontmatter
import markdown

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
PUBLIC = ROOT / "public"

CONFIG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
SITE_URL = CONFIG["site_url"].rstrip("/")
SITE_NAME = CONFIG["site_name"]
PHONE = CONFIG.get("phone", "")
PHONE_DISPLAY = CONFIG.get("phone_display", PHONE)
EMAIL = CONFIG.get("email", "")
GBP_URL = CONFIG.get("business_profile_url", "")
SOCIAL_PROFILES = CONFIG.get("social_profiles", [])
BRAND_PERSON = CONFIG.get("brand_person")
AREAS_SERVED = CONFIG.get("areas_served", [])
SECTION_LABELS = CONFIG.get("sections", {"": "Home", "guides": "Guides"})

# Editorial warnings, not a ranking or AI-detection score.
BANNED_WORDS = ["leverage", "leveraging", "delve", "elevate your", "unlock the"]

MD = markdown.Markdown(extensions=["tables", "attr_list", "md_in_html"])


def is_published(meta, today_iso, include_drafts):
    """A page is live if it isn't a draft and its publishDate (if any) has arrived.
    include_drafts=True (preview builds) shows everything. This is the drip gate."""
    if include_drafts:
        return True
    if meta.get("draft"):
        return False
    pd = meta.get("publishDate")
    if pd:
        pd_str = pd.isoformat() if hasattr(pd, "isoformat") else str(pd)
        if pd_str > today_iso:
            return False
    return True


def load_pages(include_drafts=False):
    pages = []
    today_iso = date.today().isoformat()
    for path in sorted(CONTENT.rglob("*.md")):
        post = frontmatter.load(path)
        if not is_published(post.metadata, today_iso, include_drafts):
            continue  # queued/scheduled — hidden until its publishDate (drip)
        rel = path.relative_to(CONTENT)
        section = rel.parent.as_posix() if rel.parent.as_posix() != "." else ""
        stem = rel.stem
        if stem == "index" and section == "":
            url = "/"
        elif stem == "_hub":
            url = f"/{section}/"
        else:
            url = f"/{section}/{stem}/" if section else f"/{stem}/"
        pages.append({
            "path": path,
            "section": section,
            "slug": stem,
            "url": url,
            "meta": post.metadata,
            "body": post.content,
        })
    return pages


def check_banned_words(page):
    faq_text = " ".join(
        f.get("q", "") + " " + f.get("a", "")
        for f in (page["meta"].get("faqs") or [])
    )
    lower = (page["body"] + " " + faq_text
             + " " + str(page["meta"].get("description", ""))).lower()
    hits = [w for w in BANNED_WORDS if w in lower]
    if hits:
        print(f"  WARNING {page['url']}: contains banned word(s): {hits}")


def breadcrumbs_html(page):
    if page["url"] == "/":
        return ""
    parts = ['<p class="crumbs"><a href="/">Home</a>']
    if page["section"] and page["slug"] != "_hub":
        section = html.escape(page["section"], quote=True)
        label = html.escape(SECTION_LABELS.get(page["section"], page["section"]))
        parts.append(f' &rsaquo; <a href="/{section}/">{label}</a>')
    parts.append(" &rsaquo; " + html.escape(page["meta"].get("shortTitle", page["meta"]["title"])))
    return "".join([*parts, "</p>"])


def breadcrumbs_schema(page):
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"}]
    pos = 2
    if page["section"]:
        items.append({
            "@type": "ListItem", "position": pos,
            "name": SECTION_LABELS.get(page["section"], page["section"]),
            "item": f"{SITE_URL}/{page['section']}/",
        })
        pos += 1
    if page["slug"] not in ("_hub", "index"):
        items.append({
            "@type": "ListItem", "position": pos,
            "name": page["meta"].get("shortTitle", page["meta"]["title"]),
            "item": SITE_URL + page["url"],
        })
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def local_business_schema(area_served=None):
    """Describe only the real entity fields explicitly configured by the owner."""
    schema = {
        "@context": "https://schema.org", "@type": CONFIG.get("entity_type", "Organization"),
        "@id": SITE_URL + "/#business", "name": SITE_NAME,
        "description": CONFIG.get("description", ""), "url": SITE_URL,
    }
    for key, value in (("telephone", PHONE), ("email", EMAIL), ("address", CONFIG.get("address"))):
        if value:
            schema[key] = value
    areas = [area_served] if area_served else AREAS_SERVED
    if areas:
        schema["areaServed"] = [{"@type": "Place", "name": name} for name in areas]
    same_as = [u for u in [GBP_URL, *SOCIAL_PROFILES] if u]
    if same_as:
        schema["sameAs"] = same_as
    return schema


def article_schema(page):
    meta = page["meta"]
    schema = {
        "@context": "https://schema.org", "@type": "Article", "headline": meta["title"],
        "description": meta.get("description", ""), "inLanguage": CONFIG.get("language", "en-US"),
        "mainEntityOfPage": SITE_URL + page["url"],
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
        "about": meta.get("primaryQuestion", meta["title"]),
    }
    if CONFIG.get("author_name"):
        schema["author"] = {"@type": "Person", "name": CONFIG["author_name"], "url": SITE_URL + "/about/"}
    for key in ("datePublished", "dateModified"):
        if meta.get(key):
            schema[key] = str(meta[key])
    return schema


def faq_schema(faqs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f["q"],
                "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
            }
            for f in faqs
        ],
    }


def faq_html(page):
    faqs = page["meta"].get("faqs") or []
    if not faqs:
        return ""
    label = html.escape(page["meta"].get("faqTitle", "Frequently Asked Questions"))
    out = [f'<section class="faq-section"><h2>{label}</h2>']
    for faq in faqs:
        out.append(f'<div class="faq-item"><h3>{html.escape(faq["q"])}</h3><p>{html.escape(faq["a"])}</p></div>')
    return "\n".join([*out, "</section>"])


def cta_html(page):
    if page["meta"].get("noCta"):
        return ""
    cta = CONFIG.get("cta", {})
    url = cta.get("url", "/contact/")
    if not (url.startswith("/") and not url.startswith("//")) and not url.startswith("https://"):
        raise ValueError("CTA URL must be a site-relative path or HTTPS URL")
    return ('<section class="cta-band">'
            f'<h2>{html.escape(cta.get("heading", "Have a question?"))}</h2>'
            f'<p>{html.escape(cta.get("body", "Read our contact page for the next step."))}</p>'
            f'<a class="btn" href="{html.escape(url, quote=True)}">{html.escape(cta.get("label", "Contact"))}</a>'
            '</section>')


def related_html(page, pages_by_url):
    rels = page["meta"].get("related") or []
    if not rels:
        return ""
    items = []
    for url in rels:
        target = pages_by_url.get(url)
        label = target["meta"].get("shortTitle", target["meta"]["title"]) if target else url
        if target is None:
            print(f"  WARNING {page['url']}: related link not found: {url}")
            continue
        items.append(f'<li><a href="{html.escape(url, quote=True)}">{html.escape(label)}</a></li>')
    return (
        '<section class="related"><h2>Related guides</h2><ul>'
        + "".join(items)
        + "</ul></section>"
    )


def schema_blocks(page):
    blocks = [article_schema(page), breadcrumbs_schema(page)]
    faqs = page["meta"].get("faqs") or []
    if faqs:
        blocks.append(faq_schema(faqs))
    if page["section"] == "service-areas" and page["slug"] != "_hub":
        # per-suburb LocalBusiness (areaServed = that suburb)
        blocks.append(local_business_schema(area_served=page["meta"].get("shortTitle")))
    elif page["url"] in ("/", "/about/", "/contact/", "/service-areas/"):
        blocks.append(local_business_schema())
    if page["url"] == "/":
        blocks.extend(brand_schema())
    return "\n".join(
        '<script type="application/ld+json">'
        + json.dumps(b, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>"
        for b in blocks
    )


def brand_schema():
    """Person + Organization JSON-LD for the personal-brand Knowledge Graph.
    Only emitted when BRAND_PERSON is configured. sameAs pulls together every
    owned profile so Google links person -> brand -> activities."""
    if not BRAND_PERSON:
        return []
    same_as = [u for u in ([GBP_URL] + list(SOCIAL_PROFILES) + list(BRAND_PERSON.get("sameAs", []))) if u]
    org = {
        "@context": "https://schema.org", "@type": "Organization",
        "@id": SITE_URL + "/#org", "name": SITE_NAME, "url": SITE_URL,
    }
    person = {
        "@context": "https://schema.org", "@type": "Person",
        "@id": SITE_URL + "/#person", "name": BRAND_PERSON["name"],
        "url": SITE_URL, "worksFor": {"@id": SITE_URL + "/#org"},
    }
    if BRAND_PERSON.get("jobTitle"):
        person["jobTitle"] = BRAND_PERSON["jobTitle"]
    if same_as:
        org["sameAs"] = same_as
        person["sameAs"] = same_as
    return [org, person]


def render(page, template, pages_by_url):
    meta = page["meta"]
    MD.reset()
    # Markdown is owner-authored trusted content; do not render untrusted submissions.
    content_html = MD.convert(page["body"])
    nav = " ".join(f'<a href="/{html.escape(section, quote=True)}/">{html.escape(label)}</a>'
                   for section, label in SECTION_LABELS.items() if section)
    replacements = {
        "{{title}}": html.escape(meta.get("metaTitle", meta["title"] + " | " + SITE_NAME)),
        "{{description}}": html.escape(meta.get("description", ""), quote=True),
        "{{canonical}}": html.escape(SITE_URL + page["url"], quote=True),
        "{{language}}": html.escape(CONFIG.get("language", "en-US"), quote=True),
        "{{site_name}}": html.escape(SITE_NAME),
        "{{site_description}}": html.escape(CONFIG.get("description", "")),
        "{{nav}}": nav, "{{schema}}": schema_blocks(page),
        "{{breadcrumbs}}": breadcrumbs_html(page), "{{content}}": content_html,
        "{{faq}}": faq_html(page), "{{cta}}": cta_html(page),
        "{{related}}": related_html(page, pages_by_url),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def write_page(page, html):
    if page["url"] == "/":
        out = PUBLIC / "index.html"
    else:
        out = PUBLIC / page["url"].strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def write_sitemap(pages):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        entry = f'<url><loc>{html.escape(SITE_URL + page["url"])}</loc>'
        # Only genuine editorial dates; rebuilding does not reset freshness.
        modified = page["meta"].get("dateModified")
        if modified:
            entry += f'<lastmod>{html.escape(str(modified))}</lastmod>'
        lines.append(entry + '</url>')
    lines.append('</urlset>')
    (PUBLIC / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")


def write_robots():
    """Basic crawl policy. Owners choose any additional search/training bot rules."""
    (PUBLIC / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")


def write_llms_txt(pages):
    """Optional site summary; not a requirement or ranking/citation guarantee."""
    lines = [f"# {SITE_NAME}", "", CONFIG.get("description", ""), ""]
    for section in dict.fromkeys(p["section"] for p in pages):
        lines.extend([f"## {SECTION_LABELS.get(section, section)}", ""])
        for page in pages:
            if page["section"] == section:
                lines.append(f'- [{page["meta"]["title"]}]({SITE_URL}{page["url"]}): {page["meta"].get("description", "")}')
        lines.append("")
    (PUBLIC / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    global PUBLIC
    if not CONTENT.exists():
        sys.exit("content/ directory not found")

    # --include-drafts: preview build with ALL pages (incl. queued/scheduled),
    # written to preview/ separately. Configure deployments to use public/ only.
    include_drafts = "--include-drafts" in sys.argv
    if include_drafts:
        PUBLIC = ROOT / "preview"
        print("PREVIEW BUILD (includes drafts/scheduled) -> preview/  [do not deploy this dir]")

    template = (TEMPLATES / "base.html").read_text(encoding="utf-8")

    # Refuse symlinked or unexpected output targets before replacing generated files.
    if PUBLIC.is_symlink() or PUBLIC.resolve().parent != ROOT.resolve() or PUBLIC.name not in {"public", "preview"}:
        sys.exit("Output directory must be public/ or preview/ inside this kit")
    # Clean the verified generated output directory only.
    if PUBLIC.exists():
        for item in PUBLIC.iterdir():
            if item.is_symlink():
                sys.exit("Refusing a symlink in generated output")
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    PUBLIC.mkdir(exist_ok=True)

    pages = load_pages(include_drafts=include_drafts)
    pages_by_url = {p["url"]: p for p in pages}

    print(f"Building {len(pages)} pages...")
    for page in pages:
        check_banned_words(page)
        html = render(page, template, pages_by_url)
        write_page(page, html)

    shutil.copy2(TEMPLATES / "style.css", PUBLIC / "style.css")
    write_sitemap(pages)
    write_robots()
    write_llms_txt(pages)
    print(f"Done. Output in {PUBLIC}")


if __name__ == "__main__":
    main()
