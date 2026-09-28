#!/usr/bin/env python3
"""
Combined FAQ enrichment pipeline for Ghost blog posts.

For every serious post, we want two FAQ inputs:
  1. Internal graph questions from Neo4j.
  2. External market-language questions from Reddit.

This script runs/plans both and merges any available research markdown into one
review file that can be injected with reddit_question_mining.py inject because
the markdown shape is intentionally compatible.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BLOG_ROOT


def run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)


def write_source_error(slug: str, source: str, command: list[str], error: Exception) -> Path:
    out_dir = BLOG_ROOT / "theme-notes" / "faq-enrichment"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}-{source}-error.md"
    safe_command = " ".join(str(part) for part in command)
    lines = [
        f"# FAQ Enrichment Source Error: {source}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Slug: {slug}",
        "",
        "This source failed during enrichment. Keep this note so the next run can self-anneal instead of silently skipping the source.",
        "",
        "## Error",
        "",
        f"- Type: `{type(error).__name__}`",
        f"- Command: `{safe_command}`",
    ]
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def selected_blocks(markdown: str, source_label: str, max_count: int) -> list[str]:
    blocks = re.split(r"\n###\s+\d+\.\s+", markdown)
    selected: list[str] = []
    for block in blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue
        question = lines[0].strip()
        if not question:
            continue
        body = "\n".join(lines[1:]).strip()
        body = body.replace("**Florian answer draft:**", f"- FAQ source group: {source_label}\n\n**Florian answer draft:**")
        selected.append(f"### {len(selected) + 1}. {question}\n\n{body}".strip())
        if len(selected) >= max_count:
            break
    return selected


def merge_research(slug: str, graph_count: int, reddit_count: int) -> Path | None:
    graph_file = BLOG_ROOT / "theme-notes" / "graph-faq-research" / f"{slug}-graph-questions.md"
    reddit_file = BLOG_ROOT / "theme-notes" / "reddit-faq-research" / f"{slug}-reddit-questions.md"
    combined_file = BLOG_ROOT / "theme-notes" / "faq-enrichment" / f"{slug}-combined-faqs.md"

    blocks: list[str] = []
    if graph_file.exists():
        blocks.extend(selected_blocks(graph_file.read_text(encoding="utf-8"), "internal Neo4j graph", graph_count))
    if reddit_file.exists():
        blocks.extend(selected_blocks(reddit_file.read_text(encoding="utf-8"), "Reddit market language", reddit_count))

    if not blocks:
        return None

    lines = [
        f"# Combined FAQ Enrichment: {slug}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Use this file as the review layer before injecting FAQs into a Ghost article.",
        "",
        "Rules:",
        "",
        "- Keep public questions exact unless a safety/privacy edit is needed.",
        "- Do not publish internal source IDs, Reddit usernames, or Reddit answers.",
        "- Replace every TODO with a site-owner-voice answer from the article thesis.",
        "- Keep private meeting details private; extract the generalizable question.",
        "",
        "## Selected Questions",
        "",
    ]
    renumbered = []
    for i, block in enumerate(blocks, 1):
        renumbered.append(re.sub(r"^###\s+\d+\.", f"### {i}.", block, count=1))
    lines.extend(["\n\n".join(renumbered), ""])
    combined_file.parent.mkdir(parents=True, exist_ok=True)
    combined_file.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return combined_file


def run_enrich(args: argparse.Namespace) -> int:
    graph_ok = True
    reddit_ok = True
    graph_cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "neo4j_question_mining.py"),
        "research",
        "--topic",
        args.topic,
        "--slug",
        args.slug,
        "--select-count",
        str(args.graph_count),
        "--max-nodes",
        str(args.graph_max_nodes),
    ]
    if not args.graph_live:
        graph_cmd.append("--dry-run")
    try:
        run_command(graph_cmd)
    except subprocess.CalledProcessError as exc:
        graph_ok = False
        error_file = write_source_error(args.slug, "neo4j", graph_cmd, exc)
        print(f"Neo4j enrichment failed. Error note: {error_file}", file=sys.stderr)
        if args.require_graph:
            raise RuntimeError("Required Neo4j enrichment failed; stopping before draft publication") from exc

    reddit_cmd = [
        sys.executable,
        str(BLOG_ROOT / "execution" / "reddit_question_mining.py"),
        "research",
        "--topic",
        args.topic,
        "--slug",
        args.slug,
        "--select-count",
        str(args.reddit_count),
        "--max-results",
        str(args.reddit_max_results),
    ]
    if args.seed_file:
        reddit_cmd.extend(["--seed-file", args.seed_file])
    if args.include_comments:
        reddit_cmd.append("--include-comments")
    if not args.reddit_live:
        reddit_cmd.append("--dry-run")
    try:
        run_command(reddit_cmd)
    except subprocess.CalledProcessError as exc:
        reddit_ok = False
        error_file = write_source_error(args.slug, "reddit", reddit_cmd, exc)
        print(f"Reddit enrichment failed. Error note: {error_file}", file=sys.stderr)
        if args.require_reddit:
            raise RuntimeError("Required Reddit enrichment failed; stopping before draft publication") from exc

    combined = merge_research(args.slug, args.graph_count, args.reddit_count)
    graph_file = BLOG_ROOT / "theme-notes" / "graph-faq-research" / f"{args.slug}-graph-questions.md"
    reddit_file = BLOG_ROOT / "theme-notes" / "reddit-faq-research" / f"{args.slug}-reddit-questions.md"
    if args.require_graph and args.graph_live and (not graph_ok or not graph_file.exists()):
        raise RuntimeError("Required Neo4j enrichment did not produce a graph FAQ research file")
    if args.require_reddit and args.reddit_live and (not reddit_ok or not reddit_file.exists()):
        raise RuntimeError("Required Reddit enrichment did not produce a Reddit FAQ research file")
    if combined:
        print(f"Wrote combined FAQ review file: {combined}")
    else:
        print("No combined file written yet. Run with --graph-live and/or --reddit-live to create source research files.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Neo4j + Reddit FAQ enrichment for a Ghost blog post")
    sub = parser.add_subparsers(dest="command", required=True)

    enrich = sub.add_parser("enrich", help="Plan or run graph + Reddit FAQ enrichment")
    enrich.add_argument("--topic", required=True)
    enrich.add_argument("--slug", required=True)
    enrich.add_argument("--seed-file")
    enrich.add_argument("--graph-live", action="store_true", help="Connect to Neo4j and write graph FAQ research")
    enrich.add_argument("--reddit-live", action="store_true", help="Run Apify Reddit mining")
    enrich.add_argument("--include-comments", action="store_true")
    enrich.add_argument("--graph-count", type=int, default=5)
    enrich.add_argument("--reddit-count", type=int, default=10)
    enrich.add_argument("--graph-max-nodes", type=int, default=500)
    enrich.add_argument("--reddit-max-results", type=int, default=30)
    enrich.add_argument("--require-graph", action="store_true", help="Fail if live Neo4j enrichment fails or produces no file")
    enrich.add_argument("--require-reddit", action="store_true", help="Fail if live Reddit enrichment fails or produces no file")
    enrich.set_defaults(func=run_enrich)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


