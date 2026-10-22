"""Reverse-engineer a location-scaled blog/site to learn how it ranks across
many cities. Reads a competitor's sitemap(s), groups URLs into patterns to
expose the programmatic "geo page" structure, samples pages to profile their
on-page AEO/SEO (headings, word count, JSON-LD schema, FAQ, internal links),
and writes a findings report.

Usage:
    python execution/analyze_competitor.py example.org
    python execution/analyze_competitor.py site1.com site2.com --sample 8 --out docs/competitor-findings-local-seo.md

Deps: requests (stdlib for the rest). Firecrawl/Apify are optional fallbacks
for JS-heavy sites (not needed for typical sitemap-driven local-SEO sites).
"""

import argparse
import gzip
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
USE_FC = False  # paid requests require an explicit --firecrawl flag
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
TIMEOUT = 25


# ---------------------------------------------------------------------------
# Firecrawl fallback (handles anti-bot / cert-broken / JS sites)
# ---------------------------------------------------------------------------

def firecrawl_map(domain):
    base = domain if domain.startswith("http") else "https://" + domain
    try:
        r = requests.post("https://api.firecrawl.dev/v1/map",
                          headers={"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
                          json={"url": base}, timeout=90)
        d = r.json()
        links = d.get("links") or d.get("data") or []
        return {(l if isinstance(l, str) else l.get("url", "")) for l in links if l}
    except Exception:
        return set()


def firecrawl_html(url):
    try:
        r = requests.post("https://api.firecrawl.dev/v1/scrape",
                          headers={"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
                          json={"url": url, "formats": ["rawHtml"]}, timeout=90)
        d = r.json()
        return (d.get("data") or {}).get("rawHtml") or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Sitemap discovery
# ---------------------------------------------------------------------------

def _get(url):
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        content = r.content
        if url.endswith(".gz") or content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        return content.decode("utf-8", errors="replace")
    except Exception:
        return None


def find_sitemaps(domain):
    base = domain if domain.startswith("http") else "https://" + domain
    base = base.rstrip("/")
    candidates = [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/sitemap-index.xml"]
    # robots.txt often lists sitemaps
    robots = _get(base + "/robots.txt")
    if robots:
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return base, out


LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)


def collect_urls(sitemap_urls, cap=20000):
    """Follow sitemap indexes recursively; return the set of page URLs."""
    page_urls, to_visit, visited = set(), list(sitemap_urls), set()
    while to_visit and len(page_urls) < cap:
        sm = to_visit.pop(0)
        if sm in visited:
            continue
        visited.add(sm)
        xml = _get(sm)
        if not xml:
            continue
        locs = LOC_RE.findall(xml)
        is_index = "<sitemapindex" in xml.lower()
        for loc in locs:
            if is_index or loc.endswith(".xml") or loc.endswith(".xml.gz"):
                if loc not in visited:
                    to_visit.append(loc)
            else:
                page_urls.add(loc)
    return page_urls


# ---------------------------------------------------------------------------
# URL pattern grouping (exposes the programmatic geo-page structure)
# ---------------------------------------------------------------------------

SLUGY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")  # multi-word slug e.g. we-buy-houses-katy


STATE = re.compile(r"^[A-Za-z]{2}$")            # /TX/, /AZ/
CITYISH = re.compile(r"^[A-Z][A-Za-z]+(?:[_-][A-Za-z]+)*$")  # capitalized city segments


def is_variable(seg):
    """True if a path segment looks like a variable (city/slug/id), not a fixed route."""
    return bool(
        SLUGY.match(seg) or seg.isdigit() or re.search(r"\d", seg)
        or STATE.match(seg) or CITYISH.match(seg)
    )


def url_pattern(path):
    """Normalize a path into a template: variable segments (cities/slugs/ids) -> {slug}."""
    segs = [s for s in path.strip("/").split("/") if s]
    out = ["{slug}" if is_variable(s) else s for s in segs]
    return "/" + "/".join(out) + ("/" if path.endswith("/") else "")


# ---------------------------------------------------------------------------
# Page profiling
# ---------------------------------------------------------------------------

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts, self.in_skip, self.tag_stack = [], 0, []
        self.h = Counter()
        self.title = ""
        self.in_title = False
        self.jsonld = []
        self._ld_buf, self._in_ld = [], False
        self.internal_links = 0
        self.host = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.in_skip += 1
        if tag == "title":
            self.in_title = True
        if tag in ("h1", "h2", "h3"):
            self.h[tag] += 1
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self._ld_buf = []
        if tag == "a" and a.get("href", "").startswith("/"):
            self.internal_links += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.in_skip = max(0, self.in_skip - 1)
        if tag == "title":
            self.in_title = False
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.jsonld.append("".join(self._ld_buf))

    def handle_data(self, data):
        if self._in_ld:
            self._ld_buf.append(data)
        if self.in_title:
            self.title += data
        if not self.in_skip:
            t = data.strip()
            if t:
                self.text_parts.append(t)


def schema_types(jsonld_blocks):
    types = []
    for block in jsonld_blocks:
        for m in re.findall(r'"@type"\s*:\s*"([^"]+)"', block):
            types.append(m)
    return types


def profile_page(url):
    html = firecrawl_html(url) if USE_FC else _get(url)
    if not html:
        return None
    p = PageParser()
    try:
        p.feed(html)
    except Exception:
        pass
    words = len(" ".join(p.text_parts).split())
    types = schema_types(p.jsonld)
    faq = "FAQPage" in types or bool(re.search(r"\bfaq\b", html, re.I))
    # question-style headings (rough: headings ending with '?')
    q_headings = len(re.findall(r"<h[23][^>]*>[^<]*\?[^<]*</h[23]>", html, re.I))
    return {
        "url": url, "title": p.title.strip()[:90], "words": words,
        "h1": p.h["h1"], "h2": p.h["h2"], "h3": p.h["h3"],
        "schema": sorted(set(types)), "faq": faq,
        "q_headings": q_headings, "internal_links": p.internal_links,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def analyze(domain, sample_n):
    base, sitemaps = find_sitemaps(domain)
    urls = collect_urls(sitemaps)
    source = "sitemap"
    if USE_FC and FIRECRAWL_KEY:
        fc = firecrawl_map(domain)
        if len(fc) > len(urls):
            urls, source = fc, "firecrawl /map"
    lines = [f"## {domain}", ""]
    if not urls:
        lines += [f"- Sitemaps tried: {sitemaps}",
                  "- **No URLs found** via sitemap or Firecrawl (site may be very thin, blocked, or gone).", ""]
        return lines, None
    lines.append(f"- **URL source:** {source}")

    patterns = Counter(url_pattern(urlparse(u).path) for u in urls)
    lines += [
        f"- **Total URLs in sitemap(s):** {len(urls)}",
        f"- **Sitemaps:** {', '.join(sitemaps[:4])}",
        "",
        "### URL patterns (top 15 — the programmatic structure)",
        "",
        "| count | pattern |",
        "|------:|---------|",
    ]
    for pat, n in patterns.most_common(15):
        lines.append(f"| {n} | `{pat}` |")
    lines.append("")

    # sample pages: prefer the biggest slug-pattern group (likely the geo pages)
    geo_pattern = None
    for pat, n in patterns.most_common():
        if "{slug}" in pat and n >= 3:
            geo_pattern = pat
            break
    sample = []
    if geo_pattern:
        geo_urls = [u for u in urls if url_pattern(urlparse(u).path) == geo_pattern]
        sample = geo_urls[:sample_n]
        lines += [f"### Sampled pages from the largest geo pattern `{geo_pattern}` ({len(geo_urls)} pages)", ""]
    else:
        sample = list(urls)[:sample_n]
        lines += ["### Sampled pages", ""]

    profs = [p for p in (profile_page(u) for u in sample) if p]
    if profs:
        import statistics
        wc = [p["words"] for p in profs]
        lines += [
            "| words | h2 | Q-headings | FAQ | schema | url |",
            "|------:|---:|-----------:|:---:|--------|-----|",
        ]
        for p in profs:
            lines.append(f"| {p['words']} | {p['h2']} | {p['q_headings']} | {'yes' if p['faq'] else '-'} | "
                         f"{', '.join(p['schema']) or '-'} | {urlparse(p['url']).path} |")
        lines += [
            "",
            f"- **Median word count** of geo pages: ~{int(statistics.median(wc))}",
            f"- **Schema types seen:** {', '.join(sorted({t for p in profs for t in p['schema']})) or 'none detected'}",
            f"- **FAQ present on:** {sum(1 for p in profs if p['faq'])}/{len(profs)} sampled",
            f"- **Avg internal links/page:** ~{int(statistics.mean([p['internal_links'] for p in profs]))}",
            "",
        ]
    return lines, {"domain": domain, "total": len(urls), "geo_pattern": geo_pattern}


def main():
    ap = argparse.ArgumentParser(description="Reverse-engineer location-scaled blogs")
    ap.add_argument("domains", nargs="+")
    ap.add_argument("--sample", type=int, default=6, help="pages to profile per site")
    ap.add_argument("--firecrawl", action="store_true", help="force Firecrawl for discovery + profiling (anti-bot sites)")
    ap.add_argument("--out", default="docs/competitor-findings-local-seo.md")
    args = ap.parse_args()
    global USE_FC
    USE_FC = args.firecrawl
    if USE_FC and not FIRECRAWL_KEY:
        ap.error("--firecrawl requires FIRECRAWL_API_KEY in your local .env")

    report = ["# Competitor Teardown — Location-Scaled Local SEO/AEO Sites", "",
              "Auto-generated by `execution/analyze_competitor.py`. What to copy: the URL/silo "
              "pattern, the geo-page template, page volume, schema types, and FAQ usage.", ""]
    summary = []
    for d in args.domains:
        print(f"Analyzing {d} ...")
        lines, summ = analyze(d, args.sample)
        report += lines
        if summ:
            summary.append(summ)

    if summary:
        report += ["## Cross-site takeaways", ""]
        for s in summary:
            report.append(f"- **{s['domain']}**: {s['total']} URLs; geo template `{s['geo_pattern']}`")
        report.append("")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
