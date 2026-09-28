#!/usr/bin/env python3
"""Polish existing Ghost blog HTML drafts and optionally sync them to Ghost."""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BLOG_ROOT
CONTENT_DRAFTS = BLOG_ROOT / "content-drafts"
CODE_HEAD = BLOG_ROOT / "theme-assets" / "guided-reading-head.html"
CODE_FOOT = BLOG_ROOT / "theme-assets" / "guided-reading-foot.html"

sys.path.insert(0, str(SCRIPT_PATH.parent))
import ghost_client  # noqa: E402
import youtube_blog_pipeline as ybp  # noqa: E402


PUBLISHED_SLUGS = [
    "meeting-transcripts-market-research-ai-agencies",
    "two-mistakes-new-ai-agency-owners-make",
    "profitable-ai-agency-market-factors",
    "claude-opus-4-8-performance-issues-codex-comparison",
    "ai-agencies-find-clients-in-person",
    "go-where-business-owners-meet",
    "context-engineering-vs-prompt-engineering",
    "automate-youtube-transcripts-vscode-apify",
    "find-local-business-leads-apify-free-ai-stack",
]


def inline_markdown_to_html(text: str) -> str:
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def render_cta_block() -> str:
    return "\n".join(ybp.render_cta_html())


def polish_html(source: str) -> str:
    content = source
    content = re.sub(r"\n\s*<span>Transcript-based draft</span>", "", content)
    content = content.replace(
        "Transcript-based draft generated from Your Name&#x27;s video:",
        "Article adapted from Your Name&#x27;s video:",
    )
    content = content.replace(
        "Transcript-based draft generated from Your Name's video:",
        "Article adapted from Your Name's video:",
    )
    content = content.replace(
        "A transcript-based Your Blog Name draft",
        "A transcript-based Your Blog Name article",
    )
    content = inline_markdown_to_html(content)

    cta_pattern = re.compile(
        r"    <section class=\"fr-systems-cta(?: fr-global-cta)?\">.*?    </section>",
        re.S,
    )
    content = cta_pattern.sub(render_cta_block(), content, count=1)
    return content


def post_id_for_slug(slug: str) -> str | None:
    for post in ghost_client.list_posts(limit=100, status="all"):
        if post.get("slug") == slug:
            return post.get("id")
    return None


def update_ghost(slug: str, path: Path) -> None:
    post_id = post_id_for_slug(slug)
    if not post_id:
        print(f"SKIP Ghost update: could not find post for slug {slug}", file=sys.stderr)
        return
    ghost_client.update_post(
        post_id,
        html_file=str(path),
        code_head_file=str(CODE_HEAD),
        code_foot_file=str(CODE_FOOT),
        html_card=True,
    )
    print(f"Updated Ghost post: {slug}")


def run(args: argparse.Namespace) -> int:
    changed: list[str] = []
    for slug in args.slug or PUBLISHED_SLUGS:
        path = CONTENT_DRAFTS / f"{slug}.html"
        if not path.exists():
            print(f"Missing local draft: {path}", file=sys.stderr)
            continue
        before = path.read_text(encoding="utf-8")
        after = polish_html(before)
        if before != after:
            path.write_text(after, encoding="utf-8")
            changed.append(slug)
            print(f"Polished local draft: {slug}")
        else:
            print(f"Already polished: {slug}")
        if args.sync:
            update_ghost(slug, path)
    print(f"Changed {len(changed)} local draft(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Polish existing blog posts and optionally sync to Ghost")
    parser.add_argument("--sync", action="store_true", help="Update matching Ghost posts after local polishing")
    parser.add_argument("--slug", action="append", help="Only process this slug; can be passed multiple times")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())


