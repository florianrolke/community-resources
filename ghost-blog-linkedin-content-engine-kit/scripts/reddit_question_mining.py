#!/usr/bin/env python3
"""
Reddit question mining for Ghost blog FAQs.

Purpose:
    Pull exact question wording from public Reddit posts/comments, keep source
    metadata internally, and inject selected questions into a Ghost article FAQ
    block for site-owner-voice answers.

Default actor:
    practicaltools/apify-reddit-api
    Chosen for v1 because it returned relevant data reliably in testing, uses
    predictable per-result pricing, and is cheaper than the stable Trudax actor.

Usage:
    python ghost-blog-setup/execution/reddit_question_mining.py research --topic "meeting transcripts market research AI agencies" --slug meeting-transcripts-market-research-ai-agencies --dry-run
    python ghost-blog-setup/execution/reddit_question_mining.py research --topic "meeting transcripts market research AI agencies" --slug meeting-transcripts-market-research-ai-agencies --max-results 30
    python ghost-blog-setup/execution/reddit_question_mining.py select --raw-file ghost-blog-setup/.tmp/reddit-question-mining/SLUG/raw-results.json --topic "..." --slug SLUG
    python ghost-blog-setup/execution/reddit_question_mining.py inject --draft ghost-blog-setup/content-drafts/post.html --faq-file ghost-blog-setup/theme-notes/reddit-faq-research/SLUG-reddit-questions.md --out ghost-blog-setup/content-drafts/post-with-reddit-faq.html
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BLOG_ROOT
DEFAULT_ACTOR = "practicaltools/apify-reddit-api"
FALLBACK_ACTOR = "prodiger/reddit-scraper"
PRACTICALTOOLS_ACTOR = "practicaltools/apify-reddit-api"
TRUDAX_LITE_ACTOR = "trudax/reddit-scraper-lite"

QUESTION_STARTERS = (
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "should",
    "can",
    "could",
    "would",
    "is",
    "are",
    "do",
    "does",
    "did",
    "has",
    "have",
    "anyone",
    "is there",
    "are there",
)

DEFAULT_SUBREDDITS = [
    "Entrepreneur",
    "smallbusiness",
    "marketing",
    "SEO",
    "SaaS",
    "ChatGPT",
    "ArtificialInteligence",
    "agency",
]


@dataclass
class RedditQuestion:
    exact_question: str
    source_type: str
    source_field: str
    subreddit: str | None
    reddit_url: str | None
    post_title: str | None
    score: int | None
    comment_count: int | None
    created_at: str | None
    retrieved_at: str
    actor: str
    query: str
    original_text: str
    selection_score: float = 0.0
    selected: bool = False
    notes: str = ""


def load_tokens() -> list[tuple[str, str]]:
    """Load Apify tokens, preferring the workspace's later rotated keys."""
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(BLOG_ROOT / ".env")
    order = [
        "APIFY_API_TOKEN_5",
        "APIFY_API_TOKEN_4",
        "APIFY_API_TOKEN_3",
        "APIFY_API_TOKEN_2",
        "APIFY_API_TOKEN",
    ]
    tokens: list[tuple[str, str]] = []
    for name in order:
        value = os.getenv(name)
        if value:
            tokens.append((name, value))
    return tokens


def actor_to_path(actor_id: str) -> str:
    return actor_id.replace("/", "~")


def estimate_cost(actor_id: str, max_items: int, queries: int) -> str:
    total_items = max_items * queries
    if actor_id == "santamaria-automations/reddit-scraper":
        estimate = 0.005 * queries + 0.00075 * total_items
        return f"approx ${estimate:.3f} ({total_items} max items at $0.75/1k plus starts)"
    if actor_id == FALLBACK_ACTOR:
        estimate = 0.003 * queries + 0.00115 * total_items
        return f"approx ${estimate:.3f} ({total_items} max posts at free-tier post pricing)"
    if actor_id == PRACTICALTOOLS_ACTOR:
        estimate = 0.002 * total_items
        return f"approx ${estimate:.3f} ({total_items} max items at $2/1k)"
    if actor_id == TRUDAX_LITE_ACTOR:
        estimate = 0.0034 * total_items
        return f"approx ${estimate:.3f} ({total_items} max results at $3.40/1k)"
    return f"unknown actor pricing; {total_items} max items requested"


def build_queries(topic: str, seed_questions: list[str], extra_queries: list[str], max_queries: int) -> list[str]:
    topic = " ".join(topic.split())
    queries = [
        topic,
        f'"{topic}"',
    ]
    for seed in seed_questions:
        clean = " ".join(seed.split())
        if clean:
            queries.append(clean)
    for extra in extra_queries:
        clean = " ".join(extra.split())
        if clean:
            queries.append(clean)

    topic_words = [w for w in re.findall(r"[A-Za-z0-9]+", topic.lower()) if len(w) > 3]
    if len(topic_words) >= 3:
        queries.append(" ".join(topic_words[:5]))
    if "ai" in topic.lower():
        queries.extend([
            f"{topic} agency",
            f"{topic} business owner",
        ])

    deduped: list[str] = []
    seen = set()
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped[:max_queries]


def build_actor_input(actor_id: str, query: str, subreddit: str | None, max_results: int, include_comments: bool) -> dict[str, Any]:
    if actor_id == FALLBACK_ACTOR:
        payload: dict[str, Any] = {
            "searchQuery": query,
            "sort": "relevance",
            "timeFilter": "all",
            "maxPostsPerSource": max_results,
            "includeComments": include_comments,
            "maxCommentsPerPost": 20 if include_comments else 1,
            "commentDepth": 1,
        }
        if subreddit:
            payload["searchSubreddit"] = subreddit
        return payload

    if actor_id == PRACTICALTOOLS_ACTOR:
        payload = {
            "searches": [query],
            "searchPosts": True,
            "searchComments": include_comments,
            "fetchPostComments": include_comments,
            "sort": "relevance",
            "time": "all",
            "maxItems": max_results,
        }
        if subreddit:
            payload["startUrls"] = [{"url": f"https://www.reddit.com/r/{subreddit}/"}]
        return payload

    if actor_id == TRUDAX_LITE_ACTOR:
        payload = {
            "maxItems": max_results,
            "maxPostCount": max_results,
            "maxComments": 20 if include_comments else 1,
            "scrollTimeout": 40,
            "proxy": {"useApifyProxy": True},
            "searches": [query],
            "sort": "relevance",
            "time": "all",
            "searchPosts": True,
            "searchComments": include_comments,
            "searchCommunities": False,
            "searchUsers": False,
            "skipComments": not include_comments,
        }
        if subreddit:
            payload["searchCommunityName"] = subreddit
        return payload

    payload = {
        "searchQuery": query,
        "sort": "top",
        "includeComments": include_comments,
        "commentDepth": 1,
        "maxCommentsPerPost": 20 if include_comments else 1,
        "maxResults": max_results,
    }
    if subreddit:
        payload["subreddits"] = [subreddit]
    return payload


def call_actor(actor_id: str, token: str, actor_input: dict[str, Any], timeout_seconds: int) -> list[dict[str, Any]]:
    url = (
        f"https://api.apify.com/v2/acts/{actor_to_path(actor_id)}"
        f"/run-sync-get-dataset-items"
    )
    resp = requests.post(
        url,
        params={"timeout": timeout_seconds},
        headers={"Authorization": f"Bearer {token}"},
        json=actor_input,
        timeout=timeout_seconds + 15,
    )
    if resp.status_code >= 400:
        print(f"Actor input that failed: {json.dumps(actor_input, ensure_ascii=False)}", file=sys.stderr)
        print(f"Apify error body: {resp.text[:1200]}", file=sys.stderr)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    return []


def normalize_question(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def question_spans(text: str) -> list[str]:
    text = normalize_question(text)
    if not text:
        return []

    spans = re.findall(r"([^?]{12,220}\?)", text)
    cleaned = [trim_to_question_start(s) for s in spans]
    cleaned = [s for s in cleaned if is_question_like(s)]
    if cleaned:
        return cleaned

    first_line = normalize_question(text.split("\n", 1)[0])
    if is_question_like(first_line):
        return [first_line[:220].strip()]
    return []


def trim_to_question_start(text: str) -> str:
    text = normalize_question(text)
    low = text.lower()
    starts = []
    for starter in QUESTION_STARTERS:
        match = re.search(rf"(^|[\s>\-*_(])({re.escape(starter)}\b)", low)
        if match:
            starts.append(match.start(2))
    if starts:
        text = text[min(starts):]
    return normalize_question(text)


def is_question_like(text: str) -> bool:
    text = normalize_question(text)
    if len(text) < 18 or len(text) > 240:
        return False
    if any(bad in text.lower() for bad in ("http://", "https://", "preview.redd.it", "redd.it", "reddit.com/submit")):
        return False
    if text.count("[") + text.count("]") + text.count("(") + text.count(")") > 4:
        return False
    low = text.lower().strip(" \"'([{")
    starts_well = low.startswith(QUESTION_STARTERS)
    return starts_well and ("?" in text or len(text.split()) <= 18)


def item_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    meta = item.get("metadata")
    if isinstance(meta, dict):
        for key in keys:
            value = meta.get(key)
            if value not in (None, ""):
                return value
    return None


def extract_candidates(items: list[dict[str, Any]], actor_id: str, query: str, topic_terms: set[str]) -> list[RedditQuestion]:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    candidates: list[RedditQuestion] = []

    for item in items:
        source_type = str(item_value(item, "type") or "post").lower()
        fields = [
            ("title", item_value(item, "title", "postTitle", "post_title")),
            ("body", item_value(item, "body", "text", "selfText", "selftext")),
        ]

        for field, raw_text in fields:
            if not raw_text or raw_text in ("[deleted]", "[removed]"):
                continue
            for exact in question_spans(str(raw_text)):
                score = parse_int(item_value(item, "score", "upVotes"))
                question_terms = set(re.findall(r"[a-z0-9]+", exact.lower()))
                overlap = len(topic_terms.intersection(question_terms))
                selection_score = overlap * 10 + math.log(max(score or 0, 0) + 1, 2)
                if "?" in exact:
                    selection_score += 3
                if source_type == "post" and field == "title":
                    selection_score += 12
                if field == "body":
                    selection_score -= 8
                if cliche_or_noise(exact):
                    selection_score -= 12

                candidates.append(RedditQuestion(
                    exact_question=exact,
                    source_type=source_type if source_type != "none" else str(item_value(item, "dataType") or "post"),
                    source_field=field,
                    subreddit=item_value(item, "subreddit", "communityName", "parsedCommunityName", "category"),
                    reddit_url=item_value(item, "reddit_url", "url", "permalink"),
                    post_title=item_value(item, "postTitle", "post_title", "title"),
                    score=score,
                    comment_count=parse_int(item_value(item, "numComments", "num_comments", "commentCount", "numberOfComments", "numberOfreplies")),
                    created_at=item_value(item, "createdAt", "created_utc"),
                    retrieved_at=retrieved_at,
                    actor=actor_id,
                    query=query,
                    original_text=normalize_question(str(raw_text)),
                    selection_score=selection_score,
                ))

    return dedupe_candidates(candidates)


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def cliche_or_noise(text: str) -> bool:
    low = text.lower()
    noisy_terms = (
        "gamestop",
        "gme",
        "stock",
        "short squeeze",
        "treasury market",
        "repo",
        "invest in",
        "wallstreetbets",
        "market cap",
        "options market",
    )
    return any(term in low for term in noisy_terms)


def dedupe_candidates(candidates: list[RedditQuestion]) -> list[RedditQuestion]:
    best_by_key: dict[str, RedditQuestion] = {}
    for c in candidates:
        key = re.sub(r"[^a-z0-9]+", " ", c.exact_question.lower()).strip()
        if not key:
            continue
        previous = best_by_key.get(key)
        if not previous or c.selection_score > previous.selection_score:
            best_by_key[key] = c
    return sorted(best_by_key.values(), key=lambda c: c.selection_score, reverse=True)


def read_seed_questions(path: str | None) -> list[str]:
    if not path:
        return []
    text = Path(path).read_text(encoding="utf-8")
    seeds: list[str] = []
    boilerplate = {
        "bottom line up front",
        "in this guide",
        "frequently asked questions",
        "questions from this section",
        "related reading",
        "sources and references",
        "glossary",
    }
    for match in re.findall(r"<h[234][^>]*>(.*?)</h[234]>", text, flags=re.I | re.S):
        clean = normalize_question(re.sub(r"<[^>]+>", " ", match))
        low = clean.lower().strip()
        if not clean or low in boilerplate:
            continue
        if "?" not in clean:
            continue
        seeds.append(clean)
    return seeds[:8]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, title: str, candidates: list[RedditQuestion], selected_count: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Selected Exact Reddit Questions",
        "",
    ]
    for i, c in enumerate(candidates[:selected_count], 1):
        c.selected = True
        lines.extend([
            f"### {i}. {c.exact_question}",
            "",
            "- Published question: keep exact wording unless review flags a safety/privacy issue.",
            f"- Source: {c.reddit_url or 'missing'}",
            f"- Subreddit: {c.subreddit or 'unknown'}",
            f"- Score: {c.score if c.score is not None else 'unknown'}",
            f"- Comments: {c.comment_count if c.comment_count is not None else 'unknown'}",
            f"- Source field: {c.source_type}.{c.source_field}",
            f"- Query: `{c.query}`",
            f"- Selection score: {c.selection_score:.2f}",
            "",
            "**Florian answer draft:** TODO - answer in the site owner's voice from the article thesis, not from Reddit replies.",
            "",
        ])
    lines.extend([
        "## Remaining Candidates",
        "",
    ])
    for c in candidates[selected_count:]:
        lines.extend([
            f"- {c.exact_question}",
            f"  - Source: {c.reddit_url or 'missing'}",
            f"  - Score: {c.selection_score:.2f}",
        ])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run_research(args: argparse.Namespace) -> int:
    seed_questions = read_seed_questions(args.seed_file)
    queries = build_queries(args.topic, seed_questions, args.extra_query or [], args.max_queries)
    subreddits = [s.strip().lstrip("r/") for s in (args.subreddits or "").split(",") if s.strip()]
    actor_id = args.actor
    output_dir = BLOG_ROOT / ".tmp" / "reddit-question-mining" / args.slug
    topic_terms = {w for w in re.findall(r"[a-z0-9]+", args.topic.lower()) if len(w) > 3}

    planned_runs = len(queries) * max(1, len(subreddits) if args.per_subreddit else 1)
    print(f"Actor: {actor_id}")
    print(f"Queries: {len(queries)}")
    print(f"Estimated cost: {estimate_cost(actor_id, args.max_results, planned_runs)}")
    if args.dry_run:
        for q in queries:
            print(f"- {q}")
        return 0

    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No APIFY_API_TOKEN found in .env")

    all_items: list[dict[str, Any]] = []
    all_candidates: list[RedditQuestion] = []
    query_targets = subreddits if args.per_subreddit and subreddits else [None]

    for query in queries:
        for subreddit in query_targets:
            actor_input = build_actor_input(actor_id, query, subreddit, args.max_results, args.include_comments)
            last_error: Exception | None = None
            for token_name, token in tokens:
                try:
                    print(f"Running {actor_id} with {token_name}: query={query!r}, subreddit={subreddit or 'all'}")
                    items = call_actor(actor_id, token, actor_input, args.timeout)
                    for item in items:
                        item["_query"] = query
                        item["_actor"] = actor_id
                    all_items.extend(items)
                    all_candidates.extend(extract_candidates(items, actor_id, query, topic_terms))
                    last_error = None
                    break
                except requests.HTTPError as exc:
                    last_error = exc
                    status = exc.response.status_code if exc.response is not None else "?"
                    print(f"  {token_name} failed with HTTP {status}; trying next token...", file=sys.stderr)
                except requests.RequestException as exc:
                    last_error = exc
                    print(f"  {token_name} request failed: {type(exc).__name__}; trying next token...", file=sys.stderr)
            if last_error:
                raise last_error

    candidates = dedupe_candidates(all_candidates)
    write_json(output_dir / "raw-results.json", all_items)
    write_json(output_dir / "question-candidates.json", [asdict(c) for c in candidates])
    research_md = BLOG_ROOT / "theme-notes" / "reddit-faq-research" / f"{args.slug}-reddit-questions.md"
    write_markdown(research_md, f"Reddit Question Research: {args.slug}", candidates, args.select_count)
    print(f"Wrote raw results: {output_dir / 'raw-results.json'}")
    print(f"Wrote candidates: {output_dir / 'question-candidates.json'}")
    print(f"Wrote selected research: {research_md}")
    return 0


def load_candidates(path: Path) -> list[RedditQuestion]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data and isinstance(data[0], dict) and "exact_question" in data[0]:
        return [RedditQuestion(**item) for item in data]
    topic_terms: set[str] = set()
    candidates: list[RedditQuestion] = []
    for item in data:
        candidates.extend(extract_candidates([item], item.get("_actor", DEFAULT_ACTOR), item.get("_query", ""), topic_terms))
    return dedupe_candidates(candidates)


def run_select(args: argparse.Namespace) -> int:
    candidates = load_candidates(Path(args.raw_file))
    if args.topic:
        topic_terms = {w for w in re.findall(r"[a-z0-9]+", args.topic.lower()) if len(w) > 3}
        for c in candidates:
            q_terms = set(re.findall(r"[a-z0-9]+", c.exact_question.lower()))
            c.selection_score += len(topic_terms.intersection(q_terms)) * 10
        candidates = dedupe_candidates(candidates)
    out = Path(args.out) if args.out else BLOG_ROOT / "theme-notes" / "reddit-faq-research" / f"{args.slug}-reddit-questions.md"
    write_markdown(out, f"Reddit Question Research: {args.slug}", candidates, args.count)
    print(f"Wrote selected research: {out}")
    return 0


def parse_selected_questions(markdown: str) -> list[tuple[str, str]]:
    blocks = re.split(r"\n###\s+\d+\.\s+", markdown)
    pairs: list[tuple[str, str]] = []
    for block in blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue
        question = normalize_question(lines[0])
        answer_match = re.search(r"\*\*Florian answer draft:\*\*\s*(.+?)(?=\n###|\n##|\Z)", block, re.S)
        answer = "TODO - answer in the site owner's voice from the article thesis, not from Reddit replies."
        if answer_match:
            answer = normalize_question(answer_match.group(1))
        pairs.append((question, answer))
    return pairs


def build_faq_html(pairs: list[tuple[str, str]]) -> str:
    lines = [
        '    <section class="fr-final-faq">',
        "      <h2>Frequently Asked Questions</h2>",
    ]
    for question, answer in pairs:
        lines.extend([
            '      <div class="fr-faq-item">',
            f"        <h3>{html.escape(question)}</h3>",
            f"        <p>{html.escape(answer)}</p>",
            "      </div>",
        ])
    lines.append("    </section>")
    return "\n".join(lines)


def run_inject(args: argparse.Namespace) -> int:
    draft_path = Path(args.draft)
    faq_path = Path(args.faq_file)
    html_text = draft_path.read_text(encoding="utf-8")
    faq_md = faq_path.read_text(encoding="utf-8")
    pairs = parse_selected_questions(faq_md)[:args.count]
    if len(pairs) < args.count:
        raise RuntimeError(f"Only found {len(pairs)} selected questions in {faq_path}; expected {args.count}")

    faq_html = build_faq_html(pairs)
    pattern = re.compile(r'\s*<section class="fr-final-faq">.*?</section>', re.S)
    if not pattern.search(html_text):
        raise RuntimeError("Could not find existing <section class=\"fr-final-faq\"> block")
    updated = pattern.sub("\n" + faq_html, html_text, count=1)
    out_path = Path(args.out) if args.out else draft_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(updated, encoding="utf-8")
    print(f"Wrote updated draft: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine exact Reddit questions for Ghost blog FAQs")
    sub = parser.add_subparsers(dest="command", required=True)

    research = sub.add_parser("research", help="Run Apify Reddit research and extract question candidates")
    research.add_argument("--topic", required=True)
    research.add_argument("--slug", required=True)
    research.add_argument("--seed-file", help="Optional draft HTML or notes file to derive extra seed questions")
    research.add_argument("--extra-query", action="append", help="Additional exact Reddit search query. Can be repeated.")
    research.add_argument("--actor", default=DEFAULT_ACTOR, choices=[DEFAULT_ACTOR, FALLBACK_ACTOR, PRACTICALTOOLS_ACTOR, TRUDAX_LITE_ACTOR])
    research.add_argument("--max-results", type=int, default=30)
    research.add_argument("--max-queries", type=int, default=4)
    research.add_argument("--select-count", type=int, default=10)
    research.add_argument("--include-comments", action="store_true")
    research.add_argument("--subreddits", default=",".join(DEFAULT_SUBREDDITS))
    research.add_argument("--per-subreddit", action="store_true", help="Run each query separately per subreddit; costs more")
    research.add_argument("--timeout", type=int, default=120)
    research.add_argument("--dry-run", action="store_true")
    research.set_defaults(func=run_research)

    select = sub.add_parser("select", help="Select top questions from raw/candidate JSON")
    select.add_argument("--raw-file", required=True)
    select.add_argument("--topic")
    select.add_argument("--slug", required=True)
    select.add_argument("--count", type=int, default=10)
    select.add_argument("--out")
    select.set_defaults(func=run_select)

    inject = sub.add_parser("inject", help="Replace the final FAQ block in an article HTML file")
    inject.add_argument("--draft", required=True)
    inject.add_argument("--faq-file", required=True)
    inject.add_argument("--out")
    inject.add_argument("--count", type=int, default=10)
    inject.set_defaults(func=run_inject)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


