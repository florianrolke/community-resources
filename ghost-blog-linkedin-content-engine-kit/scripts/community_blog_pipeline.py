#!/usr/bin/env python3
"""
Community, case-study, masterclass, and quote-bank blog draft pipeline.

New community-derived posts are sensitive by default. This script writes local
HTML drafts, runs required Neo4j + Reddit FAQ enrichment when requested, and
only creates Ghost drafts after required enrichment succeeds.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from youtube_blog_pipeline import inline_html, para_html, render_cta_html, slugify


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BLOG_ROOT
DRAFT_ROOT = BLOG_ROOT / "content-drafts"
NOTES_ROOT = BLOG_ROOT / "theme-notes" / "community-pipeline"
LEDGER_PATH = BLOG_ROOT / "theme-notes" / "blog-post-ledger.jsonl"


CONTENT_TYPES = {
    "win": "Community Win",
    "case-study": "Case Study",
    "masterclass": "Masterclass Notes",
    "newsletter-update": "Community Update",
    "quote-bank": "Field Notes",
}


@dataclass
class CommunitySource:
    title: str
    slug: str
    content_type: str
    topic: str
    source_text: str
    source_path: str | None
    source_notes: list[str]
    redactions: list[str]


@dataclass
class PipelineResult:
    title: str
    slug: str
    content_type: str
    local_draft: str
    source_notes: str
    faq_review: str | None
    ghost_url: str | None
    ghost_id: str | None
    status: str


def load_environment() -> None:
    for path in [
        PROJECT_ROOT / ".env",
        BLOG_ROOT / ".env",
    ]:
        if path.exists():
            load_dotenv(path, override=False)


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def public_source_text(text: str) -> str:
    """Strip internal markdown note scaffolding before drafting public copy."""
    housekeeping_fragments = (
        "the public blog post should",
        "the public post should",
        "public-facing posts",
        "review before publishing",
        "unless explicit permission",
        "unless permission",
    )
    category_labels = {
        "community win.",
        "case study.",
        "masterclass notes.",
        "newsletter or community update.",
    }
    public_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.lower() in category_labels:
            continue
        if any(fragment in line.lower() for fragment in housekeeping_fragments):
            continue
        line = re.sub(r"^\s*[-*]\s+", "", line)
        public_lines.append(line)
    return "\n".join(public_lines).strip() or text


def redact_text(text: str, redactions: list[str]) -> str:
    output = text
    output = re.sub(r"\b[\w.+-]+@[\w.-]+\.\w+\b", "[email redacted]", output)
    output = re.sub(r"https?://(?:www\.)?skool\.com/\S+", "[private community link redacted]", output)
    for item in sorted({r.strip() for r in redactions if r.strip()}, key=len, reverse=True):
        output = re.sub(rf"(?<!\w){re.escape(item)}(?!\w)", "[name redacted]", output, flags=re.IGNORECASE)
    return output


def first_sentences(text: str, limit: int = 4) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", clean_text(text))
    chosen = [p for p in parts if len(p.split()) >= 8][:limit]
    return chosen or [clean_text(text)[:400]]


def extract_money(text: str) -> list[str]:
    patterns = [
        r"\$[\d,.]+(?:\s?(?:k|K|m|M|million|thousand))?",
        r"\b\d+(?:\.\d+)?\s?%",
        r"\b\d+\s?(?:clients|customers|appointments|calls|leads|hours|days|weeks|months)\b",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text))
    deduped: list[str] = []
    seen = set()
    for item in found:
        normalized = item.lower()
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(item)
    return deduped[:8]


def extract_questions(text: str) -> list[str]:
    candidates = re.findall(r"([^?]{15,180}\?)", clean_text(text))
    out: list[str] = []
    seen = set()
    for candidate in candidates:
        question = candidate.strip(" -")
        key = re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(question)
    return out[:8]


def source_note_markdown(source: CommunitySource, metrics: list[str], questions: list[str]) -> str:
    lines = [
        f"# Community Source Notes: {source.slug}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Content type: {CONTENT_TYPES.get(source.content_type, source.content_type)}",
        f"Topic: {source.topic}",
        f"Source file: {source.source_path or 'quote-bank/generated'}",
        "",
        "## Redaction Defaults",
        "",
        "- Names, private links, and emails are redacted before public draft generation.",
        "- Business facts such as dollar amounts, timelines, and offer type are preserved when useful.",
        "- Review before publishing because community-derived proof can identify people through context.",
        "",
        "## Detected Proof Points",
        "",
    ]
    if metrics:
        lines.extend([f"- {item}" for item in metrics])
    else:
        lines.append("- No explicit numeric proof points detected.")
    lines.extend(["", "## Detected Questions", ""])
    if questions:
        lines.extend([f"- {item}" for item in questions])
    else:
        lines.append("- No literal questions detected in the source.")
    lines.extend(["", "## Source Notes", ""])
    lines.extend([f"- {note}" for note in source.source_notes] or ["- None."])
    return "\n".join(lines).strip() + "\n"


def article_dict(source: CommunitySource) -> dict[str, Any]:
    text = public_source_text(redact_text(source.source_text, source.redactions))
    proof_points = extract_money(text)
    literal_questions = extract_questions(text)
    lead_points = first_sentences(text, 5)
    type_label = CONTENT_TYPES.get(source.content_type, source.content_type)
    bluf = (
        "The lesson is not the isolated win. The lesson is the pattern behind it: a specific offer, "
        "a real buyer conversation, and enough proof to turn the next conversation into a cleaner decision."
    )
    if source.content_type == "win":
        bluf = (
            "A monetary win becomes useful content when it is anonymized, tied to the offer mechanics, "
            "and turned into a repeatable lesson for the next AI agency owner."
        )
    elif source.content_type == "masterclass":
        bluf = (
            "A masterclass transcript is most valuable when it becomes an answer-first operating note: "
            "what changed, what to do next, and which questions came up from real operators."
        )

    return {
        "title": source.title,
        "slug": source.slug,
        "content_type": type_label,
        "topic": source.topic,
        "bluf": bluf,
        "summary_points": lead_points,
        "proof_points": proof_points,
        "literal_questions": literal_questions,
        "sections": [
            {
                "heading": "What happened",
                "body": " ".join(lead_points[:2]),
            },
            {
                "heading": "Why this matters for AI agency owners",
                "body": (
                    "The practical signal is whether someone can turn attention, trust, and a specific business problem "
                    "into a paid implementation. That is more useful than abstract niche advice because it shows what "
                    "a buyer was willing to act on."
                ),
            },
            {
                "heading": "The pattern to extract",
                "body": (
                    "Look for the trigger, the offer, the proof, the delivery promise, and the follow-up mechanism. "
                    "Those five pieces are what make a community win reusable without copying someone else's private context."
                ),
            },
        ],
        "section_faqs": [
            {
                "question": "Should I publish community wins publicly?",
                "answer": "Yes, but only after anonymizing the person and stripping private context. The public lesson should be the pattern, not the member's identity.",
            },
            {
                "question": "What should stay in the article?",
                "answer": "Keep the offer type, the buyer situation, the result, the mistake avoided, and the lesson. Remove names, private links, and details that make the person easy to identify.",
            },
        ],
        "final_faqs": [
            {
                "question": "How do I turn this into a blog post without sounding generic?",
                "answer": "Start from the real question or win, then write the answer in your voice. The point is to publish field notes from actual operator conversations, not a polished generic SEO article.",
            },
            {
                "question": "Where does Reddit fit in?",
                "answer": "Reddit gives exact market-language questions. The wording can come from Reddit, but the answer should come from the source material and the site owner's point of view.",
            },
            {
                "question": "Where does Neo4j fit in?",
                "answer": "Neo4j should pull adjacent stories, quotes, meetings, and questions so the post compounds existing knowledge instead of becoming an isolated article.",
            },
        ],
        "sources": [
            "Anonymized community, meeting, or quote-bank source material.",
            "Names, handles, emails, and private community links are removed before publication.",
        ],
    }


def render_article_html(article: dict[str, Any]) -> str:
    toc = [section["heading"] for section in article["sections"]]
    lines = [
        '<article class="fr-article fr-normal-post">',
        "  <header class=\"fr-authority-header\">",
        f"    <p class=\"fr-eyebrow\">{inline_html(article['content_type'])}</p>",
        f"    <p class=\"fr-content-title\">{inline_html(article['title'])}</p>",
        "    <div class=\"fr-meta-row\">",
        f"      <span>By {inline_html(os.getenv('SITE_AUTHOR_NAME', 'Your Name'))}</span>",
        "      <span>Updated " + datetime.now().strftime("%B %d, %Y") + "</span>",
        "      <span>Community field note</span>",
        "    </div>",
        "  </header>",
        "  <section class=\"fr-bluf\">",
        "    <h2>Bottom Line Up Front</h2>",
        f"    <p>{inline_html(article['bluf'])}</p>",
        "  </section>",
        "  <section class=\"fr-guide-toc\">",
        "    <h2>In This Guide</h2>",
        "    <ol>",
    ]
    for item in toc:
        lines.append(f"      <li><a href=\"#{slugify(item, max_words=8)}\">{inline_html(item)}</a></li>")
    lines.extend(["    </ol>", "  </section>"])
    if article["proof_points"]:
        lines.extend([
            "  <section class=\"fr-content-section\">",
            "    <h2>Proof Points To Notice</h2>",
            "    <ul>",
        ])
        for item in article["proof_points"]:
            lines.append(f"      <li>{inline_html(item)}</li>")
        lines.extend(["    </ul>", "  </section>"])
    for section in article["sections"]:
        anchor = slugify(section["heading"], max_words=8)
        lines.extend([
            f"  <section id=\"{anchor}\" class=\"fr-content-section\">",
            f"    <h2>{inline_html(section['heading'])}</h2>",
            para_html(section["body"]),
            "  </section>",
        ])
    if article["section_faqs"]:
        lines.extend([
            "  <section class=\"fr-section-faq\">",
            "    <h2>Questions From This Section</h2>",
        ])
        for faq in article["section_faqs"]:
            lines.extend([
                "    <div class=\"fr-faq-item\">",
                f"      <h3>{inline_html(faq['question'])}</h3>",
                f"      <p>{inline_html(faq['answer'])}</p>",
                "    </div>",
            ])
        lines.append("  </section>")
    if article["literal_questions"]:
        lines.extend([
            "  <section class=\"fr-section-faq\">",
            "    <h2>Questions Found In The Source</h2>",
        ])
        for question in article["literal_questions"]:
            lines.extend([
                "    <div class=\"fr-faq-item\">",
                f"      <h3>{inline_html(question)}</h3>",
                "      <p>Answer draft: this should be answered in the site owner's voice during review, using the article thesis and the anonymized source context.</p>",
                "    </div>",
            ])
        lines.append("  </section>")
    lines.extend([
        "  <section class=\"fr-section-faq fr-final-faq\">",
        "    <h2>FAQ</h2>",
    ])
    for faq in article["final_faqs"]:
        lines.extend([
            "    <div class=\"fr-faq-item\">",
            f"      <h3>{inline_html(faq['question'])}</h3>",
            f"      <p>{inline_html(faq['answer'])}</p>",
            "    </div>",
        ])
    lines.append("  </section>")
    lines.extend(render_cta_html())
    lines.extend([
        "  <section class=\"fr-source-list\">",
        "    <h2>Sources And Notes</h2>",
        "    <ul>",
    ])
    for source in article["sources"]:
        lines.append(f"      <li>{inline_html(source)}</li>")
    lines.extend([
        "    </ul>",
        "  </section>",
        "</article>",
    ])
    return "\n".join(lines)


def run_faq_enrichment(source: CommunitySource, draft_path: Path, live: bool, require_reddit: bool) -> Path | None:
    combined = BLOG_ROOT / "theme-notes" / "faq-enrichment" / f"{source.slug}-combined-faqs.md"
    cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "faq_enrichment_pipeline.py"),
        "enrich",
        "--topic",
        source.topic,
        "--slug",
        source.slug,
        "--seed-file",
        str(draft_path),
        "--include-comments",
        "--graph-count",
        "8",
        "--reddit-count",
        "10",
        "--require-graph",
    ]
    if live:
        cmd.extend(["--graph-live", "--reddit-live"])
        if require_reddit:
            cmd.append("--require-reddit")
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
    return combined if combined.exists() else None


def create_ghost_draft(article: dict[str, Any], draft_path: Path) -> tuple[str | None, str | None]:
    cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "ghost_client.py"),
        "create",
        article["title"],
        str(draft_path),
        "--slug",
        article["slug"],
        "--excerpt",
        clean_text(article["bluf"])[:300],
        "--meta-title",
        article["title"][:70],
        "--meta-description",
        clean_text(article["bluf"])[:155],
        "--tags",
        "AI Agency Strategy,Community Field Notes,AEO",
        "--html-card",
        "--code-head-file",
        str(BLOG_ROOT / "theme-assets" / "guided-reading-head.html"),
        "--code-foot-file",
        str(BLOG_ROOT / "theme-assets" / "guided-reading-foot.html"),
    ]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True, capture_output=True, text=True)
    output = proc.stdout
    url_match = re.search(r"https?://[^\s\"']+", output)
    id_match = re.search(r'"id":\s*"([^"]+)"', output)
    return url_match.group(0) if url_match else None, id_match.group(1) if id_match else None


def append_ledger(result: PipelineResult) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = asdict(result)
    record["recorded_at"] = datetime.now(timezone.utc).isoformat()
    record["refresh_cadence"] = "quarterly for wins, annually for evergreen strategy posts"
    record["next_review_date"] = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1).date().isoformat()
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_from_source(source: CommunitySource, *, faq_live: bool, require_reddit: bool, create_draft: bool) -> PipelineResult:
    if create_draft and not faq_live:
        raise RuntimeError("--create-draft requires --faq-live for community posts so Neo4j enrichment is verified first")
    DRAFT_ROOT.mkdir(parents=True, exist_ok=True)
    NOTES_ROOT.mkdir(parents=True, exist_ok=True)
    redacted_text = redact_text(source.source_text, source.redactions)
    source = CommunitySource(
        title=source.title,
        slug=source.slug,
        content_type=source.content_type,
        topic=source.topic,
        source_text=redacted_text,
        source_path=source.source_path,
        source_notes=source.source_notes,
        redactions=source.redactions,
    )
    article = article_dict(source)
    draft_path = DRAFT_ROOT / f"{source.slug}.html"
    notes_path = NOTES_ROOT / f"{source.slug}-source-notes.md"
    draft_path.write_text(render_article_html(article), encoding="utf-8")
    notes_path.write_text(
        source_note_markdown(source, article["proof_points"], article["literal_questions"]),
        encoding="utf-8",
    )
    faq_review = None
    if faq_live:
        faq_review = run_faq_enrichment(source, draft_path, live=True, require_reddit=require_reddit)
    ghost_url = None
    ghost_id = None
    status = "local-draft"
    if create_draft:
        ghost_url, ghost_id = create_ghost_draft(article, draft_path)
        status = "ghost-draft"
    result = PipelineResult(
        title=article["title"],
        slug=article["slug"],
        content_type=source.content_type,
        local_draft=str(draft_path),
        source_notes=str(notes_path),
        faq_review=str(faq_review) if faq_review else None,
        ghost_url=ghost_url,
        ghost_id=ghost_id,
        status=status,
    )
    append_ledger(result)
    return result


def read_source_file(args: argparse.Namespace) -> CommunitySource:
    path = Path(args.source_file).resolve()
    text = path.read_text(encoding="utf-8", errors="replace")
    title = args.title
    slug = args.slug or slugify(title)
    topic = args.topic or title
    return CommunitySource(
        title=title,
        slug=slug,
        content_type=args.content_type,
        topic=topic,
        source_text=text,
        source_path=str(path),
        source_notes=[f"Local source file: {path.name}", f"Content type: {args.content_type}"],
        redactions=args.redact or [],
    )


def quote_bank_files() -> list[Path]:
    root = Path(os.getenv("QUOTE_BANK_ROOT", str(BLOG_ROOT / "quote-bank" / "runs")))
    return sorted(root.glob("*/quote_candidates.jsonl"), reverse=True)


def quote_bank_source(args: argparse.Namespace) -> CommunitySource:
    query_terms = {w for w in re.findall(r"[a-z0-9]+", (args.query or args.title).lower()) if len(w) > 3}
    candidates: list[dict[str, Any]] = []
    for path in quote_bank_files():
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                haystack = " ".join(str(item.get(k, "")) for k in ("quote_text", "meeting_title", "context_summary", "quote_category")).lower()
                overlap = len(query_terms.intersection(set(re.findall(r"[a-z0-9]+", haystack))))
                score = int(item.get("score") or 0) + overlap * 20
                if overlap or score >= args.min_score:
                    item["_combined_score"] = score
                    candidates.append(item)
        if candidates:
            break
    candidates = sorted(candidates, key=lambda x: int(x.get("_combined_score") or 0), reverse=True)[: args.limit]
    if not candidates:
        raise RuntimeError("No quote-bank candidates matched the requested query")
    blocks: list[str] = []
    notes: list[str] = []
    redactions = list(args.redact or [])
    for item in candidates:
        speaker = str(item.get("speaker_name") or "")
        site_author = os.getenv("SITE_AUTHOR_NAME", "").strip().lower()
        if speaker and (not site_author or site_author not in speaker.lower()):
            redactions.append(speaker)
        quote = item.get("quote_text") or ""
        blocks.append(
            f"Source meeting: {item.get('meeting_title', 'unknown')}. "
            f"Speaker: {speaker or 'unknown'}. Quote: {quote}"
        )
        notes.append(
            f"Quote candidate {item.get('quote_id', 'unknown')} from {item.get('source_path', 'unknown')} "
            f"(score {item.get('score', '?')}, category {item.get('quote_category', '?')})"
        )
    return CommunitySource(
        title=args.title,
        slug=args.slug or slugify(args.title),
        content_type="quote-bank",
        topic=args.topic or args.query or args.title,
        source_text="\n\n".join(blocks),
        source_path=None,
        source_notes=notes,
        redactions=redactions,
    )


def run_from_file(args: argparse.Namespace) -> int:
    load_environment()
    result = build_from_source(
        read_source_file(args),
        faq_live=args.faq_live,
        require_reddit=args.require_reddit,
        create_draft=args.create_draft,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def run_from_quote_bank(args: argparse.Namespace) -> int:
    load_environment()
    result = build_from_source(
        quote_bank_source(args),
        faq_live=args.faq_live,
        require_reddit=args.require_reddit,
        create_draft=args.create_draft,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create sensitive community/masterclass/quote-bank Ghost blog drafts")
    sub = parser.add_subparsers(dest="command", required=True)

    p_file = sub.add_parser("from-file", help="Create a draft package from a local transcript, note, or community export")
    p_file.add_argument("--source-file", required=True)
    p_file.add_argument("--title", required=True)
    p_file.add_argument("--slug")
    p_file.add_argument("--topic")
    p_file.add_argument("--content-type", choices=sorted(CONTENT_TYPES.keys()), default="case-study")
    p_file.add_argument("--redact", action="append", help="Name or phrase to redact; repeat as needed")
    p_file.add_argument("--faq-live", action="store_true", help="Run required Neo4j and Reddit enrichment")
    p_file.add_argument(
        "--allow-missing-reddit",
        action="store_false",
        dest="require_reddit",
        default=True,
        help="Allow local/live run to continue if Reddit enrichment fails; Neo4j remains required for Ghost drafts",
    )
    p_file.add_argument("--create-draft", action="store_true", help="Create Ghost draft after required enrichment succeeds")
    p_file.set_defaults(func=run_from_file)

    p_quote = sub.add_parser("from-quote-bank", help="Create a draft package from a quote-bank JSONL export")
    p_quote.add_argument("--query", required=True)
    p_quote.add_argument("--title", required=True)
    p_quote.add_argument("--slug")
    p_quote.add_argument("--topic")
    p_quote.add_argument("--limit", type=int, default=5)
    p_quote.add_argument("--min-score", type=int, default=55)
    p_quote.add_argument("--redact", action="append", help="Name or phrase to redact; repeat as needed")
    p_quote.add_argument("--faq-live", action="store_true", help="Run required Neo4j and Reddit enrichment")
    p_quote.add_argument(
        "--allow-missing-reddit",
        action="store_false",
        dest="require_reddit",
        default=True,
        help="Allow local/live run to continue if Reddit enrichment fails; Neo4j remains required for Ghost drafts",
    )
    p_quote.add_argument("--create-draft", action="store_true", help="Create Ghost draft after required enrichment succeeds")
    p_quote.set_defaults(func=run_from_quote_bank)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


