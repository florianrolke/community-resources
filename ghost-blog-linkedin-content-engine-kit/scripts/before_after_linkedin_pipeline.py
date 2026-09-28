#!/usr/bin/env python3
"""Create personal before/after LinkedIn draft packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from youtube_blog_pipeline import slugify


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
SOCIAL_ROOT = BLOG_ROOT / "social-drafts" / "linkedin" / "before-after"
LEDGER_PATH = BLOG_ROOT / "theme-notes" / "social-distribution-ledger.jsonl"


@dataclass
class BeforeAfterDraft:
    title: str
    slug: str
    status: str
    before_image: str
    after_image: str | None
    final_image: str | None
    image_prompt_path: str
    copy: str
    markdown_path: str
    json_path: str
    created_at: str


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def make_copy(title: str, lesson: str, turning_point: str, present_day: str) -> str:
    lesson = clean(lesson)
    turning_point = clean(turning_point)
    present_day = clean(present_day)
    lines = [
        f"I have been thinking about the distance between the old version of me and the current one.",
        "",
        f"1. {lesson.rstrip('.')}.",
    ]
    if turning_point:
        lines.extend(["", f"2. The turning point was not dramatic. {turning_point.rstrip('.')}."])
    if present_day:
        lines.extend(["", f"3. What changed by 2026: {present_day.rstrip('.')}."])
    lines.extend([
        "",
        "The honest lesson: identity changes after your calendar, standards, and environment change first.",
    ])
    if title:
        lines.extend(["", title])
    return "\n".join(lines)


def image_prompt(title: str, before_image: str, after_image: str | None) -> str:
    return f"""# Before/After LinkedIn Image Brief

Create a professional LinkedIn personal-brand image in a 16:9 thumbnail format.

Left side:
- Use the provided older personal photo as the reference for the 2019 side.
- Keep it authentic, human, and recognizable.
- Do not over-polish the old version.

Right side:
- Generate the 2026 version in Florian's current office environment.
- Match the actual current call-recording look: elegant suit, tie or dress shirt, office background with certificates, subtle blue accent light, professional camera framing.
- Suit details should come from the supplied current reference/call screenshots when available.

Composition:
- Strong split-screen before/after layout.
- Top banner: "2019 -> 2026".
- Text must look corporate and premium, not cheap.
- Keep Florian's face unobstructed.
- Use no generic money/checkmark icons unless they directly support the story.
- If symbols are used, they should explain the transformation, not decorate it.

Post title/story:
{title}

Source assets:
- Before image: {before_image}
- Current/after reference image: {after_image or "generate from approved current office references"}
"""


def command_draft(args: argparse.Namespace) -> BeforeAfterDraft:
    slug = slugify(args.slug or args.title or "before-after-linkedin-post", max_words=12)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = SOCIAL_ROOT / day / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = out_dir / "image-brief.md"
    md_path = out_dir / "linkedin-draft.md"
    json_path = out_dir / "linkedin-draft.json"

    copy = make_copy(args.title, args.lesson, args.turning_point or "", args.present_day or "")
    prompt = image_prompt(args.title, args.before_image, args.after_image)
    prompt_path.write_text(prompt, encoding="utf-8")

    draft = BeforeAfterDraft(
        title=args.title,
        slug=slug,
        status="drafted",
        before_image=args.before_image,
        after_image=args.after_image,
        final_image=args.final_image,
        image_prompt_path=str(prompt_path),
        copy=copy,
        markdown_path=str(md_path),
        json_path=str(json_path),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    md_path.write_text(
        "\n".join([
            f"# Before/After LinkedIn Draft: {args.title}",
            "",
            f"- Status: drafted",
            f"- Before image: {args.before_image}",
            f"- After/current reference: {args.after_image or 'not supplied'}",
            f"- Final image: {args.final_image or 'not supplied'}",
            f"- Image brief: {prompt_path}",
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
        f.write(json.dumps({"event": "before-after-linkedin-draft-created", **asdict(draft)}, ensure_ascii=False) + "\n")
    return draft


def command_schedule(args: argparse.Namespace) -> dict[str, object]:
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
    parser = argparse.ArgumentParser(description="Create before/after personal LinkedIn draft packages")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("draft")
    p.add_argument("--title", required=True)
    p.add_argument("--slug")
    p.add_argument("--before-image", required=True)
    p.add_argument("--after-image")
    p.add_argument("--final-image")
    p.add_argument("--lesson", required=True)
    p.add_argument("--turning-point")
    p.add_argument("--present-day")
    p.set_defaults(func=command_draft)

    p_schedule = sub.add_parser("schedule", help="Create/schedule this before/after draft through Postiz or native LinkedIn")
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
    if isinstance(result, BeforeAfterDraft):
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
