#!/usr/bin/env python3
"""
YouTube to Ghost blog draft pipeline.

This orchestrates the blog workflow Florian described:
  - use YouTube videos as source material
  - engineer headlines before writing
  - embed long-form videos in the post
  - keep all article text visible in HTML
  - enrich with exact Reddit FAQ questions before review/publishing
  - create Ghost drafts only when explicitly requested

The script is deliberately conservative. Network/paid steps are opt-in:
  - transcript fetching uses Apify only when no transcript file is supplied
  - Reddit mining runs only with --reddit-live
  - Ghost draft creation runs only with --create-draft
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BLOG_ROOT
TMP_ROOT = BLOG_ROOT / ".tmp" / "youtube-blog-pipeline"
TRANSCRIPT_ROOT = TMP_ROOT / "transcripts"
DRAFT_ROOT = BLOG_ROOT / "content-drafts"
NOTES_ROOT = BLOG_ROOT / "theme-notes" / "youtube-repurposing"
CTA_CONFIG_PATH = BLOG_ROOT / "theme-assets" / "blog-cta-config.json"
STATE_FILE = TMP_ROOT / "state.json"

DEFAULT_CHANNEL_URL = "https://www.youtube.com/@yourchannel/videos"
TRANSCRIPT_ACTOR = "topaz_sharingan/youtube-transcript-scraper-1"
CHANNEL_ACTOR = "streamers/youtube-channel-scraper"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_CTA = {
    "headline": "Want to turn this into a working client acquisition system?",
    "body": "Use this article as the thinking layer. The next step is turning the idea into a concrete offer, workflow, or appointment-setting asset.",
    "primary_label": "Go to the main site",
    "primary_url": "https://example.com/",
    "secondary_label": "Read the glossary",
    "secondary_url": "/glossary/",
}


def site_author() -> str:
    return os.getenv("SITE_AUTHOR_NAME", "Your Name")


def site_name() -> str:
    return os.getenv("SITE_NAME", "Your Blog Name")


def site_url() -> str:
    return os.getenv("GHOST_URL", "https://your-ghost-domain.com")


@dataclass
class VideoSource:
    video_id: str
    url: str
    title: str
    duration_seconds: int | None = None
    published_at: str | None = None
    description: str | None = None
    channel: str | None = None
    thumbnail_url: str | None = None


@dataclass
class PipelineResult:
    video_id: str
    video_url: str
    title: str
    chosen_headline: str
    slug: str
    local_draft: str
    headline_notes: str
    transcript_file: str
    reddit_research_file: str | None
    ghost_url: str | None
    ghost_id: str | None
    feature_image: str | None
    status: str
    created_at: str


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(BLOG_ROOT / ".env")


def apify_tokens() -> list[tuple[str, str]]:
    load_environment()
    names = [
        "APIFY_API_TOKEN_5",
        "APIFY_API_TOKEN_6",
        "APIFY_API_TOKEN_4",
        "APIFY_API_TOKEN_3",
        "APIFY_API_TOKEN_2",
        "APIFY_API_TOKEN",
    ]
    return [(name, os.getenv(name, "")) for name in names if os.getenv(name)]


def actor_path(actor_id: str) -> str:
    return actor_id.replace("/", "~")


def ensure_dirs() -> None:
    for path in (TMP_ROOT, TRANSCRIPT_ROOT, DRAFT_ROOT, NOTES_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def load_cta_config() -> dict[str, str]:
    config = dict(DEFAULT_CTA)
    if CTA_CONFIG_PATH.exists():
        try:
            data = json.loads(CTA_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update({str(k): str(v) for k, v in data.items() if v is not None})
        except json.JSONDecodeError:
            print(f"CTA config is invalid JSON: {CTA_CONFIG_PATH}", file=sys.stderr)
    return config


def read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"videos": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def write_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def video_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        vid = parsed.path.strip("/").split("/")[0]
    elif "/shorts/" in parsed.path:
        vid = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
    elif "/embed/" in parsed.path:
        vid = parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
    else:
        vid = parse_qs(parsed.query).get("v", [""])[0]
    vid = re.sub(r"[^A-Za-z0-9_-]", "", vid)
    if not vid:
        raise ValueError(f"Could not extract YouTube video id from {url}")
    return vid


def slugify(text: str, max_words: int = 9) -> str:
    text = text.lower()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    words = [w for w in re.split(r"[\s-]+", text) if w]
    stop = {"the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "from"}
    compact = [w for w in words if w not in stop]
    chosen = compact[:max_words] or words[:max_words]
    return "-".join(chosen).strip("-") or "youtube-blog-draft"


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def transcript_from_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        return transcript_from_items(data)
    return clean_text(text)


def transcript_from_items(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("transcript", "text", "content"):
            if isinstance(data.get(key), str):
                return clean_text(data[key])
        for key in ("items", "segments", "captions"):
            if key in data:
                return transcript_from_items(data[key])
    if isinstance(data, list):
        parts: list[str] = []
        for item in data:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "caption", "transcript", "content"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
                        break
        return clean_text(" ".join(parts))
    return ""


def thumbnail_from_item(item: dict[str, Any]) -> str | None:
    direct = item.get("thumbnail") or item.get("thumbnailUrl") or item.get("thumbnail_url")
    if direct:
        return str(direct)
    thumbnails = item.get("thumbnails")
    if isinstance(thumbnails, list) and thumbnails:
        best = None
        best_score = -1
        for thumb in thumbnails:
            if not isinstance(thumb, dict):
                continue
            url = thumb.get("url")
            if not url:
                continue
            width = int(thumb.get("width") or 0)
            height = int(thumb.get("height") or 0)
            score = width * height
            if score > best_score:
                best = str(url)
                best_score = score
        return best
    return None


def fetch_video_metadata(url: str) -> dict[str, Any]:
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--dump-single-json",
        url,
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=90)
    return json.loads(completed.stdout)


def call_apify_actor(actor_id: str, payload: dict[str, Any], timeout_seconds: int = 180) -> list[dict[str, Any]]:
    tokens = apify_tokens()
    if not tokens:
        raise RuntimeError("No APIFY_API_TOKEN found in .env")
    last_error: Exception | None = None
    for token_name, token in tokens:
        try:
            print(f"Running Apify actor {actor_id} with {token_name}")
            url = (
                f"https://api.apify.com/v2/acts/{actor_path(actor_id)}"
                f"/run-sync-get-dataset-items"
            )
            resp = requests.post(
                url,
                params={"timeout": timeout_seconds},
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=timeout_seconds + 20,
            )
            if resp.status_code >= 400:
                print(f"Apify error body: {resp.text[:1200]}", file=sys.stderr)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data["items"]
            return []
        except requests.RequestException as exc:
            last_error = exc
            print(f"  {token_name} failed: {type(exc).__name__}", file=sys.stderr)
    if last_error:
        raise last_error
    return []


def fetch_transcript(video: VideoSource) -> tuple[str, Path]:
    payloads = [
        {"startUrls": [{"url": video.url}]},
        {"videoUrl": video.url},
        {"videoUrls": [video.url]},
    ]
    errors: list[str] = []
    for payload in payloads:
        try:
            items = call_apify_actor(TRANSCRIPT_ACTOR, payload, timeout_seconds=180)
            transcript = transcript_from_items(items)
            if transcript:
                out = TRANSCRIPT_ROOT / f"{video.video_id}.json"
                out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
                return transcript, out
            errors.append(f"payload returned no transcript: {payload}")
        except Exception as exc:
            errors.append(f"{payload}: {exc}")
    raise RuntimeError("Could not fetch transcript via Apify. " + " | ".join(errors[-3:]))


def openrouter_json(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 2500) -> dict[str, Any] | None:
    load_environment()
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url(),
        "X-Title": f"{site_name()} Blog Pipeline",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are {site_author()}'s blog editor. Write in a direct, practical, "
                    "high-trust voice. Avoid generic AI marketing language. Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.55,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def deterministic_headlines(video: VideoSource, transcript: str) -> dict[str, Any]:
    base = clean_text(video.title).rstrip(".")
    words = transcript.split()
    topic_hint = " ".join(words[:18])
    candidates = [
        {
            "headline": base,
            "score": 72,
            "reason": "Uses the original YouTube framing and keeps intent recognizable.",
        },
        {
            "headline": f"What {base} Means for AI Agencies",
            "score": 78,
            "reason": "Adds a business-owner and agency angle while staying specific.",
        },
        {
            "headline": f"{base}: The Practical Takeaway",
            "score": 74,
            "reason": "Signals a concise answer-first article rather than a raw transcript.",
        },
    ]
    return {
        "chosen_headline": candidates[1]["headline"],
        "primary_intent": base,
        "headline_candidates": candidates,
        "notes": f"Fallback headline set generated from title. Transcript starts: {topic_hint}",
    }


def engineer_headlines(video: VideoSource, transcript: str, no_llm: bool) -> dict[str, Any]:
    if no_llm:
        return deterministic_headlines(video, transcript)

    prompt = f"""
Create headline candidates for a Ghost blog post derived from this YouTube video.

Rules:
- The chosen headline must be clear, search-intent friendly, and not clickbait.
- It should be stronger than simply copying the video title.
- Avoid generic phrases such as "unlock", "leverage", "game changer", and "revolutionize".
- Prefer answer-first specificity for AI agency owners, consultants, founders, and business owners.
- Return JSON with: chosen_headline, primary_intent, headline_candidates, notes.
- headline_candidates must be an array of 8 objects with headline, score, reason.

Video title: {video.title}
Video URL: {video.url}
Transcript excerpt:
{transcript[:6500]}
"""
    data = openrouter_json(prompt, max_tokens=2600)
    if not data:
        return deterministic_headlines(video, transcript)
    if "chosen_headline" not in data:
        return deterministic_headlines(video, transcript)
    return data


def deterministic_article(video: VideoSource, headline_data: dict[str, Any], transcript: str) -> dict[str, Any]:
    chosen = clean_text(str(headline_data.get("chosen_headline") or video.title))
    intent = clean_text(str(headline_data.get("primary_intent") or video.title))
    excerpt = (
        "A transcript-based Your Blog Name article with a direct answer, "
        "embedded video, visible FAQs, related concepts, and a clear CTA."
    )
    paragraphs = split_transcript_summary(transcript)
    return {
        "title": chosen,
        "slug": slugify(chosen),
        "excerpt": excerpt,
        "meta_title": chosen[:60],
        "meta_description": excerpt[:155],
        "tags": ["AI Agency Strategy", "YouTube Repurposing", "AEO"],
        "bluf": (
            f"The useful takeaway from this video is simple: {intent}. "
            "Before this goes live, the draft should be tightened around one core decision, "
            "then enriched with exact Reddit questions and site-owner-voice answers."
        ),
        "toc": [
            "What the video is really about",
            "The practical takeaway",
            "How this applies to AI agencies",
            "Frequently asked questions",
        ],
        "sections": [
            {
                "heading": "What the video is really about",
                "body": paragraphs[0],
            },
            {
                "heading": "The practical takeaway",
                "body": paragraphs[1],
            },
            {
                "heading": "How this applies to AI agencies",
                "body": paragraphs[2],
            },
        ],
        "section_faqs": [
            {
                "question": "What should I take from this video first?",
                "answer": "Start with the operational decision it helps you make. The blog version should make that decision clearer than the video alone.",
            },
            {
                "question": "Why turn this video into a blog post?",
                "answer": "A blog post gives the idea a clean URL, searchable structure, visible FAQs, and internal links that a video platform alone does not control.",
            },
        ],
        "final_faqs": [
            {
                "question": "Should every YouTube video become a blog post?",
                "answer": "No. Long-form videos with a clear decision, tutorial, opinion, or framework deserve posts. Shorts are usually better as idea seeds unless they answer one valuable question cleanly.",
            },
            {
                "question": "Should the blog post copy the transcript?",
                "answer": "No. The transcript is raw material. The post should be structured around the reader's question, then use the transcript as proof and source material.",
            },
            {
                "question": "Where do Reddit questions fit in?",
                "answer": "They belong near the bottom as market-intel FAQs. The question wording can come from Reddit, but the answer should come from the site owner's point of view and the article thesis.",
            },
        ],
        "sources": ["YouTube transcript from the embedded video.", "Your Blog Name publishing checklist."],
    }


def split_transcript_summary(transcript: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", transcript)
    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences[:60]:
        if not sentence:
            continue
        current.append(sentence)
        if len(" ".join(current).split()) >= 90:
            chunks.append(" ".join(current))
            current = []
        if len(chunks) == 3:
            break
    if current and len(chunks) < 3:
        chunks.append(" ".join(current))
    while len(chunks) < 3:
        chunks.append(
            "This section is a placeholder generated from limited transcript context. "
            "Tighten it during review before publishing."
        )
    return [clean_text(c) for c in chunks[:3]]


def generate_article(video: VideoSource, headline_data: dict[str, Any], transcript: str, no_llm: bool) -> dict[str, Any]:
    if no_llm:
        return deterministic_article(video, headline_data, transcript)

    prompt = f"""
Write a Ghost-ready article plan from this YouTube transcript.

Return JSON with:
- title
- slug
- excerpt
- meta_title
- meta_description
- tags: array of 3-5 tag names
- bluf: 1 direct paragraph
- toc: array of 4-6 section titles
- sections: array of 3-5 objects with heading and body. Body can contain 1-3 paragraphs separated by blank lines.
- section_faqs: array of 2-4 objects with question and answer
- final_faqs: array of 3-5 objects with question and answer
- sources: array

Rules:
- This is a blog post, not a transcript dump.
- Keep the article text visible in semantic HTML later.
- Use the embedded video as supporting media, not the only content.
- Answer first. No long throat-clearing.
- Write in the site owner's practical voice.
- Avoid generic AI-heavy wording, especially "leverage" unless unavoidable.
- Do not invent external facts or stats.
- Create an evergreen lowercase hyphenated slug with no year unless necessary.

Chosen headline: {headline_data.get("chosen_headline")}
Primary intent: {headline_data.get("primary_intent")}
Video title: {video.title}
Video URL: {video.url}
Transcript:
{transcript[:12000]}
"""
    data = openrouter_json(prompt, max_tokens=5200)
    if not data:
        return deterministic_article(video, headline_data, transcript)
    data.setdefault("title", headline_data.get("chosen_headline") or video.title)
    data.setdefault("slug", slugify(data["title"]))
    data["slug"] = slugify(str(data.get("slug") or data["title"]))
    data.setdefault("excerpt", deterministic_article(video, headline_data, transcript)["excerpt"])
    data.setdefault("meta_title", str(data["title"])[:60])
    data.setdefault("meta_description", str(data["excerpt"])[:155])
    data.setdefault("tags", ["AI Agency Strategy", "YouTube Repurposing", "AEO"])
    data.setdefault("sections", deterministic_article(video, headline_data, transcript)["sections"])
    data.setdefault("section_faqs", deterministic_article(video, headline_data, transcript)["section_faqs"])
    data.setdefault("final_faqs", deterministic_article(video, headline_data, transcript)["final_faqs"])
    data.setdefault("sources", ["YouTube transcript from the embedded video."])
    return normalize_article(data, video, headline_data)


def normalize_article(article: dict[str, Any], video: VideoSource, headline_data: dict[str, Any]) -> dict[str, Any]:
    fallback = deterministic_article(video, headline_data, "")
    article["title"] = clean_text(str(article.get("title") or headline_data.get("chosen_headline") or video.title))
    article["slug"] = slugify(str(article.get("slug") or article["title"]))
    article["excerpt"] = clean_text(str(article.get("excerpt") or fallback["excerpt"]))
    article["meta_title"] = clean_text(str(article.get("meta_title") or article["title"]))[:80]
    article["meta_description"] = clean_text(str(article.get("meta_description") or article["excerpt"]))[:180]
    if isinstance(article.get("tags"), str):
        article["tags"] = [t.strip() for t in article["tags"].split(",") if t.strip()]
    if not isinstance(article.get("tags"), list) or not article["tags"]:
        article["tags"] = fallback["tags"]
    for key in ("toc", "sections", "section_faqs", "final_faqs", "sources"):
        if not isinstance(article.get(key), list) or not article[key]:
            article[key] = fallback[key]
    return article


def inline_html(text: str) -> str:
    value = html.escape(clean_text(str(text or "")))
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        value,
    )
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    return value


def para_html(text: str) -> str:
    parts = [clean_text(p) for p in re.split(r"\n\s*\n", str(text or "")) if clean_text(p)]
    lines: list[str] = []
    for part in parts:
        raw_lines = [clean_text(line) for line in part.splitlines() if clean_text(line)]
        if raw_lines and all(line.startswith(("- ", "* ")) for line in raw_lines):
            lines.append('    <ul class="fr-bulleted-list">')
            for line in raw_lines:
                lines.append(f"      <li>{inline_html(line[2:])}</li>")
            lines.append("    </ul>")
        else:
            lines.append(f"    <p>{inline_html(part)}</p>")
    return "\n".join(lines)


def anchor(text: str) -> str:
    return slugify(text, max_words=8)


def render_source_item(source: Any) -> str:
    if isinstance(source, dict):
        title = clean_text(str(source.get("title") or source.get("name") or source.get("url") or "Source"))
        url = source.get("url")
        if url:
            return f'<a href="{html.escape(str(url))}">{html.escape(title)}</a>'
        return html.escape(title)
    return html.escape(clean_text(str(source)))


def render_video_embed(video: VideoSource) -> str:
    title = html.escape(video.title or "YouTube video")
    return f"""
    <figure class="fr-video-embed" id="video">
      <iframe src="https://www.youtube.com/embed/{html.escape(video.video_id)}" title="{title}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
      <figcaption>Video source: <a href="{html.escape(video.url)}">watch on YouTube</a>.</figcaption>
    </figure>
"""


def render_cta_html() -> list[str]:
    cta = load_cta_config()
    lines = [
        '    <section class="fr-systems-cta fr-global-cta">',
        f'      <h2>{inline_html(cta.get("headline", DEFAULT_CTA["headline"]))}</h2>',
        f'      <p>{inline_html(cta.get("body", DEFAULT_CTA["body"]))}</p>',
        '      <div class="fr-cta-actions">',
        f'        <a class="fr-btn" href="{html.escape(cta.get("primary_url", DEFAULT_CTA["primary_url"]))}">{inline_html(cta.get("primary_label", DEFAULT_CTA["primary_label"]))}</a>',
    ]
    secondary_url = cta.get("secondary_url")
    secondary_label = cta.get("secondary_label")
    if secondary_url and secondary_label:
        lines.append(
            f'        <a class="fr-btn fr-btn-secondary" href="{html.escape(secondary_url)}">{inline_html(secondary_label)}</a>'
        )
    lines.extend([
        "      </div>",
        "    </section>",
    ])
    return lines


def render_article_html(video: VideoSource, article: dict[str, Any]) -> str:
    title = clean_text(str(article.get("title") or video.title))
    toc = article.get("toc") or [s.get("heading", "") for s in article.get("sections", [])]
    sections = article.get("sections") or []
    final_faqs = article.get("final_faqs") or []
    section_faqs = article.get("section_faqs") or []
    sources = article.get("sources") or []
    updated = datetime.now().strftime("%B %-d, %Y") if os.name != "nt" else datetime.now().strftime("%B %#d, %Y")

    lines = [
        '<article class="fr-article-shell">',
        '  <header class="fr-authority-header">',
        '    <p class="fr-eyebrow">AI Agency Strategy</p>',
        f'    <p class="fr-content-title">{html.escape(title)}</p>',
        '    <div class="fr-meta-row">',
        f'      <span>By {inline_html(site_author())}</span>',
        f'      <span>Updated {html.escape(updated)}</span>',
        '    </div>',
        '',
        render_video_embed(video).rstrip(),
        '',
        '    <section class="fr-bluf" id="bottom-line">',
        '      <h2>Bottom Line Up Front</h2>',
        f'      <p>{inline_html(article.get("bluf", ""))}</p>',
        '    </section>',
        '',
        '    <nav class="fr-guide-toc" aria-labelledby="guide-heading">',
        '      <h2 id="guide-heading">In This Guide</h2>',
        '      <ol>',
    ]
    toc_seen: set[str] = set()
    for item in toc:
        if "frequently asked" in str(item).lower():
            continue
        item_anchor = anchor(str(item))
        if item_anchor in toc_seen:
            continue
        toc_seen.add(item_anchor)
        lines.append(f'        <li><a href="#{anchor(str(item))}">{html.escape(clean_text(str(item)))}</a></li>')
    lines.extend([
        '        <li><a href="#faq">Frequently asked questions</a></li>',
        '      </ol>',
        '    </nav>',
        '  </header>',
        '',
    ])

    for idx, section in enumerate(sections):
        heading = clean_text(str(section.get("heading", f"Section {idx + 1}")))
        body = str(section.get("body", ""))
        lines.extend([
            f'  <section class="fr-content-section" id="{anchor(heading)}">',
            f'    <h2>{html.escape(heading)}</h2>',
            para_html(body),
        ])
        if idx == 1 and section_faqs:
            lines.extend([
                '    <section class="fr-section-faq">',
                '      <h3>Questions from this section</h3>',
            ])
            for faq in section_faqs[:4]:
                lines.extend([
                    '      <div class="fr-faq-item">',
            f'        <h4>{html.escape(clean_text(str(faq.get("question", ""))))}</h4>',
                    f'        <p>{inline_html(faq.get("answer", ""))}</p>',
                    '      </div>',
                ])
            lines.append('    </section>')
        lines.extend(['  </section>', ''])

    lines.extend([
        '  <section class="fr-final-architecture" id="faq">',
        '    <section class="fr-related-posts">',
        '      <h2>Related reading</h2>',
        '      <ul>',
        '        <li><a href="/meeting-transcripts-market-research-ai-agencies/">Meeting Transcripts Are Market Research for AI Agencies</a></li>',
        '        <li><a href="/glossary/">Your Blog Name Glossary</a></li>',
        '      </ul>',
        '    </section>',
        '',
        '    <section class="fr-final-faq">',
        '      <h2>Frequently Asked Questions</h2>',
    ])
    for faq in final_faqs:
        lines.extend([
            '      <div class="fr-faq-item">',
            f'        <h3>{html.escape(clean_text(str(faq.get("question", ""))))}</h3>',
            f'        <p>{inline_html(faq.get("answer", ""))}</p>',
            '      </div>',
        ])
    lines.extend([
        '    </section>',
        '',
        *render_cta_html(),
        '',
        '    <section class="fr-source-list">',
        '      <h2>Sources and references</h2>',
        '      <ol>',
    ])
    for source in sources:
        lines.append(f'        <li>{render_source_item(source)}</li>')
    lines.extend([
        f'        <li>Embedded YouTube video: <a href="{html.escape(video.url)}">{html.escape(video.url)}</a></li>',
        '      </ol>',
        '    </section>',
        '  </section>',
        '</article>',
        '',
    ])
    return "\n".join(lines)


def write_headline_notes(video: VideoSource, headline_data: dict[str, Any], article: dict[str, Any]) -> Path:
    path = NOTES_ROOT / f"{article['slug']}-headline-notes.md"
    lines = [
        f"# Headline Notes: {article['title']}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Video: {video.url}",
        "",
        "## Chosen Headline",
        "",
        str(headline_data.get("chosen_headline") or article["title"]),
        "",
        "## Primary Intent",
        "",
        str(headline_data.get("primary_intent") or ""),
        "",
        "## Candidates",
        "",
    ]
    for item in headline_data.get("headline_candidates", []):
        lines.extend([
            f"- {item.get('headline', '')}",
            f"  - Score: {item.get('score', 'n/a')}",
            f"  - Reason: {item.get('reason', '')}",
        ])
    lines.extend([
        "",
        "## Notes",
        "",
        str(headline_data.get("notes", "")),
    ])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def run_reddit_research(article: dict[str, Any], draft_path: Path, live: bool) -> Path | None:
    slug = article["slug"]
    topic = article.get("title") or slug.replace("-", " ")
    research_file = BLOG_ROOT / "theme-notes" / "reddit-faq-research" / f"{slug}-reddit-questions.md"
    cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "reddit_question_mining.py"),
        "research",
        "--topic",
        str(topic),
        "--slug",
        slug,
        "--seed-file",
        str(draft_path),
        "--max-results",
        "30",
        "--include-comments",
    ]
    if not live:
        cmd.append("--dry-run")
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
    return research_file if research_file.exists() else None


def run_faq_enrichment(article: dict[str, Any], draft_path: Path, live: bool) -> Path | None:
    slug = article["slug"]
    topic = article.get("title") or slug.replace("-", " ")
    combined_file = BLOG_ROOT / "theme-notes" / "faq-enrichment" / f"{slug}-combined-faqs.md"
    cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "faq_enrichment_pipeline.py"),
        "enrich",
        "--topic",
        str(topic),
        "--slug",
        slug,
        "--seed-file",
        str(draft_path),
        "--include-comments",
    ]
    if live:
        cmd.extend(["--graph-live", "--reddit-live"])
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
    return combined_file if combined_file.exists() else None


def create_ghost_draft(article: dict[str, Any], draft_path: Path) -> tuple[str | None, str | None]:
    cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "ghost_client.py"),
        "create",
        str(article["title"]),
        str(draft_path),
        "--slug",
        str(article["slug"]),
        "--excerpt",
        str(article.get("excerpt", ""))[:300],
        "--meta-title",
        str(article.get("meta_title") or article["title"])[:80],
        "--meta-description",
        str(article.get("meta_description") or article.get("excerpt", ""))[:180],
        "--tags",
        ",".join(article.get("tags") or ["AI Agency Strategy", "AEO"]),
        "--html-card",
        "--code-head-file",
        str(BLOG_ROOT / "theme-assets" / "guided-reading-head.html"),
        "--code-foot-file",
        str(BLOG_ROOT / "theme-assets" / "guided-reading-foot.html"),
    ]
    if article.get("feature_image"):
        cmd.extend(["--feature-image", str(article["feature_image"])])
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True, capture_output=True, text=True)
    print(completed.stdout)
    ghost_url = None
    ghost_id = None
    url_match = re.search(r"URL:\s*(\S+)", completed.stdout)
    id_match = re.search(r"ID:\s*([a-f0-9]+)", completed.stdout)
    if url_match:
        ghost_url = url_match.group(1)
    if id_match:
        ghost_id = id_match.group(1)
    return ghost_url, ghost_id


def process_url(args: argparse.Namespace) -> int:
    ensure_dirs()
    load_environment()
    video_id = video_id_from_url(args.url)
    metadata: dict[str, Any] = {}
    try:
        metadata = fetch_video_metadata(args.url)
    except Exception as exc:
        print(f"Video metadata fetch failed: {type(exc).__name__}", file=sys.stderr)
    video = VideoSource(
        video_id=video_id,
        url=args.url,
        title=args.title or clean_text(str(metadata.get("title") or f"YouTube video {video_id}")),
        duration_seconds=args.duration_seconds or metadata.get("duration"),
        published_at=metadata.get("upload_date") or metadata.get("release_date"),
        description=metadata.get("description"),
        channel=metadata.get("channel") or metadata.get("uploader"),
        thumbnail_url=thumbnail_from_item(metadata),
    )

    if args.transcript_file:
        transcript_path = Path(args.transcript_file)
        transcript = transcript_from_file(transcript_path)
    else:
        transcript, transcript_path = fetch_transcript(video)

    if not transcript:
        raise RuntimeError("Transcript is empty. Provide --transcript-file or verify the Apify transcript actor.")

    if not args.transcript_file:
        transcript_text_path = TRANSCRIPT_ROOT / f"{video_id}.txt"
        transcript_text_path.write_text(transcript, encoding="utf-8")

    headline_data = engineer_headlines(video, transcript, no_llm=args.no_llm)
    article = generate_article(video, headline_data, transcript, no_llm=args.no_llm)
    article["slug"] = args.slug or slugify(str(article.get("slug") or article.get("title") or video.title))
    article["title"] = clean_text(str(article.get("title") or headline_data.get("chosen_headline") or video.title))
    if video.thumbnail_url:
        article["feature_image"] = video.thumbnail_url

    draft_html = render_article_html(video, article)
    draft_path = DRAFT_ROOT / f"{article['slug']}.html"
    draft_path.write_text(draft_html, encoding="utf-8")
    notes_path = write_headline_notes(video, headline_data, article)

    reddit_file = None
    if getattr(args, "faq_dry_run", False) or getattr(args, "faq_live", False):
        reddit_file = run_faq_enrichment(article, draft_path, live=args.faq_live)
    elif args.reddit_dry_run or args.reddit_live:
        reddit_file = run_reddit_research(article, draft_path, live=args.reddit_live)

    ghost_url = None
    ghost_id = None
    status = "local-draft"
    if args.create_draft:
        ghost_url, ghost_id = create_ghost_draft(article, draft_path)
        status = "ghost-draft"

    result = PipelineResult(
        video_id=video.video_id,
        video_url=video.url,
        title=video.title,
        chosen_headline=article["title"],
        slug=article["slug"],
        local_draft=str(draft_path),
        headline_notes=str(notes_path),
        transcript_file=str(transcript_path),
        reddit_research_file=str(reddit_file) if reddit_file else None,
        ghost_url=ghost_url,
        ghost_id=ghost_id,
        feature_image=video.thumbnail_url,
        status=status,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    state = read_state()
    state.setdefault("videos", {})[video.video_id] = asdict(result)
    write_state(state)

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def discover_with_ytdlp(channel_url: str, limit: int) -> list[dict[str, Any]]:
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--playlist-end",
        str(limit),
        channel_url,
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=90)
    data = json.loads(completed.stdout)
    return data.get("entries", []) or []


def discover_with_apify(channel_url: str, limit: int) -> list[dict[str, Any]]:
    payload = {
        "startUrls": [{"url": channel_url}],
        "maxResults": limit,
        "maxVideos": limit,
        "includeShorts": True,
        "includeStreams": False,
    }
    return call_apify_actor(CHANNEL_ACTOR, payload, timeout_seconds=180)


def normalize_discovered(item: dict[str, Any]) -> VideoSource | None:
    url = item.get("url") or item.get("webpage_url") or item.get("videoUrl")
    video_id = item.get("id") or item.get("videoId")
    if not url and video_id:
        url = f"https://www.youtube.com/watch?v={video_id}"
    if not video_id and url:
        try:
            video_id = video_id_from_url(url)
        except ValueError:
            return None
    if not url or not video_id:
        return None
    duration = item.get("duration") or item.get("durationSeconds")
    try:
        duration_int = int(float(duration)) if duration is not None else None
    except (TypeError, ValueError):
        duration_int = None
    return VideoSource(
        video_id=str(video_id),
        url=str(url),
        title=clean_text(str(item.get("title") or f"YouTube video {video_id}")),
        duration_seconds=duration_int,
        published_at=item.get("upload_date") or item.get("publishedAt") or item.get("date"),
        description=item.get("description"),
        channel=item.get("channel") or item.get("channelName"),
        thumbnail_url=thumbnail_from_item(item),
    )


def is_long_form(video: VideoSource, threshold_seconds: int) -> bool:
    if "/shorts/" in video.url:
        return False
    if video.duration_seconds is None:
        return True
    return video.duration_seconds >= threshold_seconds


def discover(args: argparse.Namespace) -> int:
    ensure_dirs()
    items: list[dict[str, Any]]
    if args.use_apify:
        items = discover_with_apify(args.channel_url, args.limit)
    else:
        try:
            items = discover_with_ytdlp(args.channel_url, args.limit)
        except Exception as exc:
            print(f"yt-dlp discovery failed: {exc}", file=sys.stderr)
            print("Retry with --use-apify to use the Apify channel scraper.", file=sys.stderr)
            return 2

    videos = [v for item in items if (v := normalize_discovered(item))]
    state = read_state()
    processed = set(state.get("videos", {}).keys())
    rows = []
    for video in videos:
        rows.append({
            "video_id": video.video_id,
            "title": video.title,
            "url": video.url,
            "duration_seconds": video.duration_seconds,
            "long_form": is_long_form(video, args.long_form_threshold),
            "already_processed": video.video_id in processed,
        })
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def discover_videos(channel_url: str, limit: int, use_apify: bool) -> list[VideoSource]:
    if use_apify:
        items = discover_with_apify(channel_url, limit)
    else:
        items = discover_with_ytdlp(channel_url, limit)
    return [v for item in items if (v := normalize_discovered(item))]


def run_channel(args: argparse.Namespace) -> int:
    ensure_dirs()
    try:
        videos = discover_videos(args.channel_url, args.limit, args.use_apify)
    except Exception as exc:
        if args.use_apify:
            raise
        print(f"yt-dlp discovery failed: {exc}", file=sys.stderr)
        print("Retrying with Apify channel discovery.", file=sys.stderr)
        videos = discover_videos(args.channel_url, args.limit, True)

    state = read_state()
    processed = set(state.get("videos", {}).keys())
    candidates = []
    for video in videos:
        if video.video_id in processed and not args.reprocess:
            continue
        if not args.include_shorts and not is_long_form(video, args.long_form_threshold):
            continue
        candidates.append(video)

    if args.dry_run:
        print(json.dumps([asdict(v) for v in candidates], ensure_ascii=False, indent=2))
        return 0

    failures: list[str] = []
    for video in candidates:
        try:
            print(f"\nProcessing {video.title} ({video.url})")
            process_args = argparse.Namespace(
                url=video.url,
                title=video.title,
                duration_seconds=video.duration_seconds,
                transcript_file=None,
                slug=None,
                no_llm=args.no_llm,
                reddit_dry_run=args.reddit_dry_run,
                reddit_live=args.reddit_live,
                faq_dry_run=args.faq_dry_run,
                faq_live=args.faq_live,
                create_draft=args.create_drafts,
            )
            process_url(process_args)
        except Exception as exc:
            message = f"{video.video_id}: {exc}"
            failures.append(message)
            print(f"Failed: {message}", file=sys.stderr)
            if args.stop_on_error:
                raise

    if failures:
        print("Failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


def status(_: argparse.Namespace) -> int:
    state = read_state()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def print_plan(_: argparse.Namespace) -> int:
    print(textwrap.dedent(f"""
    YouTube to Blog Automation Plan

    1. Detect uploads from {DEFAULT_CHANNEL_URL}.
    2. Classify long-form vs Shorts.
       - Long-form becomes a Ghost draft with embedded video.
       - Shorts are stored as future idea seeds unless explicitly processed.
    3. Pull transcript via Apify actor {TRANSCRIPT_ACTOR}, or accept a local transcript file.
    4. Generate and score headline candidates before article writing.
    5. Generate visible Ghost HTML:
       - embedded video
       - BLUF/direct answer
       - table of contents
       - descriptive H2 sections
       - visible FAQs
       - related links, sources, CTA
    6. Run combined FAQ enrichment before review.
       - --faq-dry-run plans Neo4j + Reddit enrichment
       - --faq-live connects to Neo4j and spends Apify credits for Reddit
    7. Create a Ghost draft only with --create-draft.
    8. Human review happens before publish.

    Typical safe local run:
      python ghost-blog-setup/execution/youtube_blog_pipeline.py from-url --url VIDEO_URL --title "Video title" --transcript-file transcript.txt --faq-dry-run --no-llm

    Production draft run:
      python ghost-blog-setup/execution/youtube_blog_pipeline.py from-url --url VIDEO_URL --title "Video title" --faq-live --create-draft
    """).strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn YouTube videos into Ghost blog draft packages")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Print the automation plan")
    p_plan.set_defaults(func=print_plan)

    p_status = sub.add_parser("status", help="Print processed video state")
    p_status.set_defaults(func=status)

    p_discover = sub.add_parser("discover", help="List recent channel videos without creating posts")
    p_discover.add_argument("--channel-url", default=DEFAULT_CHANNEL_URL)
    p_discover.add_argument("--limit", type=int, default=10)
    p_discover.add_argument("--use-apify", action="store_true", help="Use Apify channel scraper instead of yt-dlp")
    p_discover.add_argument("--long-form-threshold", type=int, default=180)
    p_discover.set_defaults(func=discover)

    p_run = sub.add_parser("run-channel", help="Process new long-form channel uploads into draft packages")
    p_run.add_argument("--channel-url", default=DEFAULT_CHANNEL_URL)
    p_run.add_argument("--limit", type=int, default=5)
    p_run.add_argument("--use-apify", action="store_true", help="Use Apify channel scraper instead of yt-dlp")
    p_run.add_argument("--long-form-threshold", type=int, default=180)
    p_run.add_argument("--include-shorts", action="store_true")
    p_run.add_argument("--reprocess", action="store_true", help="Ignore state and process videos again")
    p_run.add_argument("--dry-run", action="store_true", help="List videos that would be processed")
    p_run.add_argument("--no-llm", action="store_true", help="Use deterministic fallback writing instead of OpenRouter")
    p_run.add_argument("--reddit-dry-run", action="store_true", help="Plan Reddit mining queries without spending credits")
    p_run.add_argument("--reddit-live", action="store_true", help="Run live Reddit mining with Apify credits")
    p_run.add_argument("--faq-dry-run", action="store_true", help="Plan combined Neo4j + Reddit FAQ enrichment")
    p_run.add_argument("--faq-live", action="store_true", help="Run combined Neo4j + Reddit FAQ enrichment")
    p_run.add_argument("--create-drafts", action="store_true", help="Create Ghost drafts for processed videos")
    p_run.add_argument("--stop-on-error", action="store_true")
    p_run.set_defaults(func=run_channel)

    p_url = sub.add_parser("from-url", help="Create a local draft package from one YouTube URL")
    p_url.add_argument("--url", required=True)
    p_url.add_argument("--title", help="Video title if discovery metadata is not available")
    p_url.add_argument("--duration-seconds", type=int)
    p_url.add_argument("--transcript-file", help="Local transcript .txt/.md/.json. If omitted, Apify transcript actor is used.")
    p_url.add_argument("--slug", help="Override the generated slug")
    p_url.add_argument("--no-llm", action="store_true", help="Use deterministic fallback writing instead of OpenRouter")
    p_url.add_argument("--reddit-dry-run", action="store_true", help="Plan Reddit mining queries without spending credits")
    p_url.add_argument("--reddit-live", action="store_true", help="Run live Reddit mining with Apify credits")
    p_url.add_argument("--faq-dry-run", action="store_true", help="Plan combined Neo4j + Reddit FAQ enrichment")
    p_url.add_argument("--faq-live", action="store_true", help="Run combined Neo4j + Reddit FAQ enrichment")
    p_url.add_argument("--create-draft", action="store_true", help="Create a Ghost draft")
    p_url.set_defaults(func=process_url)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    start = time.time()
    try:
        return args.func(args)
    finally:
        elapsed = time.time() - start
        print(f"\nDone in {elapsed:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())


