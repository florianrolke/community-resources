#!/usr/bin/env python3
"""Generate LinkedIn drafts from Ghost posts or AgentZero source packages."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from youtube_blog_pipeline import slugify


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[2]
SOCIAL_ROOT = BLOG_ROOT / "social-drafts" / "linkedin"
LEDGER_PATH = BLOG_ROOT / "theme-notes" / "social-distribution-ledger.jsonl"
DEFAULT_POSTIZ_URL = "https://posts.florianrolke.com"


@dataclass
class LinkedInDraft:
    title: str
    slug: str
    source_type: str
    status: str
    copy: str
    blog_url: str
    image_path: str | None
    ghost_id: str | None
    ghost_status: str | None
    markdown_path: str
    json_path: str
    created_at: str


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(BLOG_ROOT / ".env")


def ghost_headers() -> dict[str, str]:
    import jwt

    admin_key = os.getenv("GHOST_ADMIN_API_KEY", "")
    if ":" not in admin_key:
        raise RuntimeError("GHOST_ADMIN_API_KEY is missing or invalid")
    kid, secret = admin_key.split(":", 1)
    now = int(datetime.now(timezone.utc).timestamp())
    token = jwt.encode(
        {"iat": now, "exp": now + 300, "aud": "/admin/"},
        bytes.fromhex(secret),
        algorithm="HS256",
        headers={"kid": kid, "typ": "JWT", "alg": "HS256"},
    )
    return {
        "Authorization": f"Ghost {token}",
        "Accept-Version": "v5.0",
        "Content-Type": "application/json",
    }


def ghost_post_by_slug(slug: str) -> dict[str, Any]:
    load_environment()
    ghost_url = os.getenv("GHOST_URL", "https://blog.florianrolke.com").rstrip("/")
    resp = requests.get(
        f"{ghost_url}/ghost/api/admin/posts/slug/{slug}/",
        headers=ghost_headers(),
        params={"formats": "html,lexical", "include": "tags,authors"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["posts"][0]


def strip_html(value: str) -> str:
    text = re.sub(r"<(script|style).*?</\1>", " ", value or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def markdown_to_plain(value: str) -> str:
    source = value or ""
    chunks: list[str] = []
    capture = False
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("## main points") or line.lower().startswith("## full transcript"):
            capture = True
            continue
        if line.startswith("## ") and capture:
            capture = False
        if not capture or not line:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        chunks.append(line)
    text = " ".join(chunks) if chunks else source
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^#+\s+", "", text, flags=re.M)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.split()) >= 8]


def extract_section_lines(text: str, limit: int = 5) -> list[str]:
    candidates: list[str] = []
    for sentence in split_sentences(text):
        lower = sentence.lower()
        if any(bad in lower for bad in ["subscribe", "privacy", "cookie", "table of contents"]):
            continue
        if any(good in lower for good in ["mistake", "pattern", "market", "client", "offer", "ai", "workflow", "agency", "owner", "system", "question"]):
            candidates.append(sentence)
    if len(candidates) < 3:
        candidates.extend(split_sentences(text))

    final: list[str] = []
    seen = set()
    for item in candidates:
        clean = re.sub(r"\s+", " ", item).strip()
        clean = re.sub(r"^[-*]\s+", "", clean)
        if clean.lower().startswith(("handoff metadata", "job id:", "received:", "content type:", "topic:", "article angle:", "source video url:")):
            continue
        key = clean[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        final.append(clean)
        if len(final) >= limit:
            break
    return final


def make_linkedin_copy(title: str, source_text: str, blog_url: str) -> str:
    points = extract_section_lines(source_text, limit=5)
    topic = re.sub(r"^(how to|why|new:|the)\s+", "", title, flags=re.I).strip()
    opener = f"I keep coming back to this in {topic}."
    numbered = []
    for idx, point in enumerate(points, start=1):
        point = point.rstrip(".")
        if len(point) > 230:
            point = point[:227].rsplit(" ", 1)[0] + "..."
        numbered.append(f"{idx}. {point}.")
    closing = "The useful signal is usually not the loudest claim. It is the pattern you can turn into the next concrete action."
    if blog_url:
        return "\n\n".join([opener, "\n\n".join(numbered), closing, f"Full post:\n{blog_url}"])
    return "\n\n".join([opener, "\n\n".join(numbered), closing])


def output_paths(slug: str) -> tuple[Path, Path]:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = SOCIAL_ROOT / day
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{slug}.md", out_dir / f"{slug}.json"


def write_draft(
    *,
    title: str,
    slug: str,
    source_type: str,
    source_text: str,
    blog_url: str,
    image_path: str | None,
    ghost_id: str | None = None,
    ghost_status: str | None = None,
) -> LinkedInDraft:
    slug = slugify(slug or title, max_words=12)
    copy = make_linkedin_copy(title, source_text, blog_url)
    md_path, json_path = output_paths(slug)
    created_at = datetime.now(timezone.utc).isoformat()
    draft = LinkedInDraft(
        title=title,
        slug=slug,
        source_type=source_type,
        status="drafted",
        copy=copy,
        blog_url=blog_url,
        image_path=image_path,
        ghost_id=ghost_id,
        ghost_status=ghost_status,
        markdown_path=str(md_path),
        json_path=str(json_path),
        created_at=created_at,
    )
    md_path.write_text(
        "\n".join([
            f"# LinkedIn Draft: {title}",
            "",
            f"- Status: drafted",
            f"- Source type: {source_type}",
            f"- Slug: {slug}",
            f"- Blog URL: {blog_url or 'not published yet'}",
            f"- Image: {image_path or 'none'}",
            "",
            "## Copy",
            "",
            copy,
            "",
        ]),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(asdict(draft), ensure_ascii=False, indent=2), encoding="utf-8")
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "linkedin-draft-created", **asdict(draft)}, ensure_ascii=False) + "\n")
    return draft


def command_draft_ghost(args: argparse.Namespace) -> LinkedInDraft:
    post = ghost_post_by_slug(args.slug)
    text = strip_html(post.get("html") or "")
    title = args.title or post.get("title") or args.slug
    blog_url = args.blog_url or post.get("url") or f"https://blog.florianrolke.com/{post.get('slug', args.slug)}/"
    image = args.image_path or post.get("feature_image")
    return write_draft(
        title=title,
        slug=post.get("slug") or args.slug,
        source_type="ghost-post",
        source_text=text,
        blog_url=blog_url,
        image_path=image,
        ghost_id=post.get("id"),
        ghost_status=post.get("status"),
    )


def command_draft_source(args: argparse.Namespace) -> LinkedInDraft:
    source_file = Path(args.source_file)
    text = markdown_to_plain(source_file.read_text(encoding="utf-8", errors="replace"))
    title = args.title or text[:80] or source_file.stem
    slug = args.slug or slugify(title, max_words=12)
    return write_draft(
        title=title,
        slug=slug,
        source_type=args.source_type,
        source_text=text,
        blog_url=args.blog_url or "",
        image_path=args.image_path,
    )


def command_print(args: argparse.Namespace) -> dict[str, str]:
    draft = json.loads(Path(args.draft_json).read_text(encoding="utf-8"))
    print(draft.get("copy", ""))
    return {"status": "printed", "draft_json": args.draft_json}


def command_schedule(args: argparse.Namespace) -> dict[str, Any]:
    if args.provider in {"native", "native-hosted"}:
        if not args.publish_now and not args.dry_run:
            return {
                "status": "blocked-native-publish-now-required",
                "message": "Native LinkedIn posting publishes immediately. Re-run with --publish-now, or keep provider=postiz for scheduling.",
                "draft_json": args.draft_json,
                "requested_when": args.when,
            }
        import linkedin_native_client

        linkedin_native_client.load_environment()
        if args.provider == "native-hosted":
            return linkedin_native_client.publish_draft_remote(
                args.draft_json,
                dry_run=args.dry_run,
                skip_image=args.skip_image,
            )
        return linkedin_native_client.publish_draft(
            args.draft_json,
            dry_run=args.dry_run,
            skip_image=args.skip_image,
        )

    import postiz_client

    postiz_client.load_environment()
    schedule_args = argparse.Namespace(
        draft_json=args.draft_json,
        when=args.when,
        integration_id=args.integration_id or "",
        post_type=args.post_type,
        transport=args.transport,
        dry_run=args.dry_run,
        skip_image=args.skip_image,
    )
    return postiz_client.command_schedule(schedule_args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate approval-gated LinkedIn drafts")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ghost = sub.add_parser("draft-ghost", help="Create a LinkedIn draft from an existing Ghost post slug")
    p_ghost.add_argument("--slug", required=True)
    p_ghost.add_argument("--title")
    p_ghost.add_argument("--blog-url")
    p_ghost.add_argument("--image-path")
    p_ghost.set_defaults(func=command_draft_ghost)

    p_source = sub.add_parser("draft-source", help="Create a LinkedIn draft from a local source/transcript file")
    p_source.add_argument("--source-file", required=True)
    p_source.add_argument("--title")
    p_source.add_argument("--slug")
    p_source.add_argument("--blog-url")
    p_source.add_argument("--image-path")
    p_source.add_argument("--source-type", default="agentzero-source")
    p_source.set_defaults(func=command_draft_source)

    p_print = sub.add_parser("print", help="Print draft copy for review")
    p_print.add_argument("--draft-json", required=True)
    p_print.set_defaults(func=command_print)

    p_schedule = sub.add_parser("schedule", help="Create/schedule this LinkedIn draft through Postiz or native LinkedIn")
    p_schedule.add_argument("--draft-json", required=True)
    p_schedule.add_argument("--when", required=True)
    p_schedule.add_argument("--provider", choices=["postiz", "native", "native-hosted"], default="postiz")
    p_schedule.add_argument("--integration-id")
    p_schedule.add_argument("--post-type", choices=["draft", "schedule"], default="schedule")
    p_schedule.add_argument("--transport", choices=["auto", "public", "ssh"], default="auto")
    p_schedule.add_argument("--dry-run", action="store_true")
    p_schedule.add_argument("--skip-image", action="store_true")
    p_schedule.add_argument("--publish-now", action="store_true", help="Required for native LinkedIn live posting")
    p_schedule.set_defaults(func=command_schedule)

    args = parser.parse_args()
    result = args.func(args)
    if isinstance(result, LinkedInDraft):
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    elif isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
