#!/usr/bin/env python3
"""
Neo4j question mining for Ghost blog FAQs.

Purpose:
    Pull related questions from the site owner's internal Neo4j graph before a blog
    post is finalized. These are internal FAQ seeds from meetings, notes,
    summaries, transcripts, or other graph nodes. They are written in the same
    markdown shape as reddit_question_mining.py so both sources can be merged.

Usage:
    python ghost-blog-setup/execution/neo4j_question_mining.py research --topic "AI agency market mistakes" --slug ai-agency-market-mistakes --dry-run
    python ghost-blog-setup/execution/neo4j_question_mining.py research --topic "AI agency market mistakes" --slug ai-agency-market-mistakes --max-nodes 500
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BLOG_ROOT

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
)

DEFAULT_SCAN_PROPERTIES = [
    "question",
    "questions",
    "faq",
    "faqs",
    "title",
    "name",
    "summary",
    "description",
    "text",
    "content",
    "body",
    "transcript",
    "notes",
]


@dataclass
class GraphQuestion:
    exact_question: str
    source_labels: list[str]
    source_property: str
    source_id: str
    source_title: str | None
    matched_terms: list[str]
    retrieved_at: str
    original_text: str
    selection_score: float = 0.0
    selected: bool = False
    notes: str = ""


def load_environment() -> None:
    env_paths = [
        PROJECT_ROOT / ".env",
        BLOG_ROOT / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)


def neo4j_configs() -> list[tuple[str, str, str, str]]:
    load_environment()
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
    configs = [
        ("NEO4J_URI", os.getenv("NEO4J_URI"), user, os.getenv("NEO4J_PASSWORD")),
        ("NEO4J_SKOOL_URI", os.getenv("NEO4J_SKOOL_URI"), user, os.getenv("NEO4J_SKOOL_PASSWORD") or os.getenv("NEO4J_PASSWORD")),
        (
            "NEO4J_CONTENT_URI",
            os.getenv("NEO4J_CONTENT_URI"),
            os.getenv("NEO4J_CONTENT_USER") or user,
            os.getenv("NEO4J_CONTENT_PASSWORD"),
        ),
    ]
    usable = [(name, uri, cfg_user, password) for name, uri, cfg_user, password in configs if uri and password]
    if not usable:
        raise RuntimeError("Missing Neo4j URI/password config in .env")
    return usable


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def trim_to_question_start(text: str) -> str:
    text = clean_text(text)
    low = text.lower()
    starts = []
    for starter in QUESTION_STARTERS:
        match = re.search(rf"(^|[\s>\-*_(])({re.escape(starter)}\b)", low)
        if match:
            starts.append(match.start(2))
    if starts:
        text = text[min(starts):]
    return clean_text(text)


def is_question_like(text: str) -> bool:
    text = clean_text(text)
    if len(text) < 18 or len(text) > 260:
        return False
    low = text.lower().strip(" \"'([{")
    if not low.startswith(QUESTION_STARTERS):
        return False
    if "?" in text:
        return True
    return len(text.split()) <= 20


def question_spans(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    spans = re.findall(r"([^?]{12,240}\?)", text)
    cleaned = [trim_to_question_start(s) for s in spans]
    cleaned = [s for s in cleaned if is_question_like(s)]
    if cleaned:
        return cleaned
    first = trim_to_question_start(text.split(".", 1)[0])
    return [first] if is_question_like(first) else []


def topic_terms(topic: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", topic.lower())
    terms = [w for w in words if len(w) > 3]
    deduped: list[str] = []
    seen = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            deduped.append(term)
    return deduped[:16]


def value_to_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(value_to_strings(item))
        return parts
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(value_to_strings(item))
        return parts
    return [str(value)]


def dedupe(candidates: list[GraphQuestion]) -> list[GraphQuestion]:
    best: dict[str, GraphQuestion] = {}
    for c in candidates:
        key = re.sub(r"[^a-z0-9]+", " ", c.exact_question.lower()).strip()
        if not key:
            continue
        previous = best.get(key)
        if not previous or c.selection_score > previous.selection_score:
            best[key] = c
    return sorted(best.values(), key=lambda c: c.selection_score, reverse=True)


def build_contains_query(scan_properties: list[str], terms: list[str], limit: int) -> tuple[str, dict[str, Any]]:
    query = """
    MATCH (n)
    WITH n, labels(n) AS labels, properties(n) AS props
    WHERE any(k IN keys(props)
      WHERE k IN $scan_properties
      AND any(term IN $terms WHERE toLower(toString(props[k])) CONTAINS term))
    RETURN elementId(n) AS id, labels, props
    LIMIT $limit
    """
    return query, {"scan_properties": scan_properties, "terms": terms, "limit": limit}


def fetch_nodes(scan_properties: list[str], terms: list[str], limit: int) -> list[dict[str, Any]]:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("The neo4j Python package is not installed. Run `pip install neo4j`.") from exc

    query, params = build_contains_query(scan_properties, terms, limit)
    errors: list[str] = []
    all_rows: list[dict[str, Any]] = []
    for config_name, uri, user, password in neo4j_configs():
        print(f"Trying Neo4j config: {config_name}")
        driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=4)
        try:
            with driver.session() as session:
                rows = session.run(query, **params)
                fetched = [dict(row) | {"config_name": config_name} for row in rows]
                all_rows.extend(fetched)
                print(f"  {config_name} returned {len(fetched)} rows")
        except Exception as exc:
            errors.append(f"{config_name}: {type(exc).__name__}: {exc}")
            print(f"  {config_name} failed: {type(exc).__name__}", file=sys.stderr)
        finally:
            driver.close()
    if all_rows:
        return all_rows
    raise RuntimeError("Could not connect to any Neo4j config. " + " | ".join(errors))


def extract_candidates(rows: list[dict[str, Any]], terms: list[str], scan_properties: list[str]) -> list[GraphQuestion]:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    candidates: list[GraphQuestion] = []
    term_set = set(terms)
    for row in rows:
        props = row.get("props") or {}
        labels = row.get("labels") or []
        source_id = str(row.get("id") or props.get("id") or props.get("uuid") or "")
        source_title = props.get("title") or props.get("name") or props.get("summary")
        for prop in scan_properties:
            if prop not in props:
                continue
            for value in value_to_strings(props.get(prop)):
                text = clean_text(value)
                if not text:
                    continue
                matched = [term for term in terms if term in text.lower()]
                for question in question_spans(text):
                    q_terms = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 3}
                    overlap = len(term_set.intersection(q_terms))
                    score = overlap * 12 + len(matched) * 5 + math.log(len(text.split()) + 1, 2)
                    if prop in ("question", "questions", "faq", "faqs"):
                        score += 20
                    candidates.append(GraphQuestion(
                        exact_question=question,
                        source_labels=[str(label) for label in labels],
                        source_property=prop,
                        source_id=source_id,
                        source_title=clean_text(str(source_title))[:180] if source_title else None,
                        matched_terms=matched,
                        retrieved_at=retrieved_at,
                        original_text=text[:1200],
                        selection_score=score,
                    ))
    return dedupe(candidates)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_markdown(path: Path, title: str, candidates: list[GraphQuestion], selected_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Selected Internal Graph Questions",
        "",
    ]
    for i, c in enumerate(candidates[:selected_count], 1):
        c.selected = True
        lines.extend([
            f"### {i}. {c.exact_question}",
            "",
            "- Published question: keep exact wording unless review flags a safety/privacy issue.",
            "- Source: internal Neo4j graph",
            f"- Labels: {', '.join(c.source_labels) or 'unknown'}",
            f"- Property: `{c.source_property}`",
            f"- Source ID: `{c.source_id or 'unknown'}`",
            f"- Source title: {c.source_title or 'unknown'}",
            f"- Matched terms: {', '.join(c.matched_terms) or 'none'}",
            f"- Selection score: {c.selection_score:.2f}",
            "",
            "**Florian answer draft:** TODO - answer in the site owner's voice from the article thesis, not by exposing private meeting details.",
            "",
        ])
    lines.extend(["## Remaining Candidates", ""])
    for c in candidates[selected_count:]:
        lines.extend([
            f"- {c.exact_question}",
            f"  - Labels: {', '.join(c.source_labels) or 'unknown'}",
            f"  - Score: {c.selection_score:.2f}",
        ])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run_research(args: argparse.Namespace) -> int:
    terms = topic_terms(args.topic)
    scan_properties = [p.strip() for p in args.scan_properties.split(",") if p.strip()]
    print(f"Topic: {args.topic}")
    print(f"Slug: {args.slug}")
    print(f"Terms: {', '.join(terms) or '(none)'}")
    print(f"Scan properties: {', '.join(scan_properties)}")
    print(f"Max nodes: {args.max_nodes}")
    if args.dry_run:
        print("Dry run only. No Neo4j connection attempted.")
        return 0
    if not terms:
        raise RuntimeError("No usable topic terms found")

    rows = fetch_nodes(scan_properties, terms, args.max_nodes)
    candidates = extract_candidates(rows, terms, scan_properties)
    output_dir = BLOG_ROOT / ".tmp" / "neo4j-question-mining" / args.slug
    write_json(output_dir / "raw-nodes.json", rows)
    write_json(output_dir / "question-candidates.json", [asdict(c) for c in candidates])
    research_md = BLOG_ROOT / "theme-notes" / "graph-faq-research" / f"{args.slug}-graph-questions.md"
    write_markdown(research_md, f"Neo4j Question Research: {args.slug}", candidates, args.select_count)
    print(f"Wrote raw nodes: {output_dir / 'raw-nodes.json'}")
    print(f"Wrote candidates: {output_dir / 'question-candidates.json'}")
    print(f"Wrote selected research: {research_md}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine related FAQ questions from Neo4j for Ghost blog posts")
    sub = parser.add_subparsers(dest="command", required=True)

    research = sub.add_parser("research", help="Run Neo4j graph research and extract question candidates")
    research.add_argument("--topic", required=True)
    research.add_argument("--slug", required=True)
    research.add_argument("--max-nodes", type=int, default=500)
    research.add_argument("--select-count", type=int, default=10)
    research.add_argument("--scan-properties", default=",".join(DEFAULT_SCAN_PROPERTIES))
    research.add_argument("--dry-run", action="store_true")
    research.set_defaults(func=run_research)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


