#!/usr/bin/env python3
"""One-command Ghost post to LinkedIn draft/publish workflow.

This is a thin orchestration wrapper around:

- linkedin_post_pipeline.py for turning a Ghost post into a LinkedIn draft
- linkedin_native_client.py for publishing through the official LinkedIn API

It keeps the dangerous action explicit: live native LinkedIn posting requires
`--publish-now`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any


def make_draft(args: argparse.Namespace) -> Any:
    import linkedin_post_pipeline

    draft_args = SimpleNamespace(
        slug=args.slug,
        title=args.title,
        blog_url=args.blog_url,
        image_path=args.image_path,
    )
    return linkedin_post_pipeline.command_draft_ghost(draft_args)


def publish_draft(args: argparse.Namespace, draft_json: str) -> dict[str, Any]:
    import linkedin_post_pipeline

    schedule_args = SimpleNamespace(
        draft_json=draft_json,
        when=args.when,
        provider=args.provider,
        integration_id="",
        post_type="schedule",
        transport="auto",
        dry_run=args.dry_run,
        skip_image=args.skip_image,
        publish_now=args.publish_now,
    )
    return linkedin_post_pipeline.command_schedule(schedule_args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a LinkedIn post from an existing Ghost post slug")
    parser.add_argument("--slug", required=True, help="Ghost post slug, for example ai-agency-first-client")
    parser.add_argument("--title", help="Optional override for the LinkedIn draft title")
    parser.add_argument("--blog-url", help="Optional override for the public blog URL")
    parser.add_argument("--image-path", help="Optional override for the image URL/path")
    parser.add_argument(
        "--provider",
        choices=["native-hosted", "native"],
        default="native-hosted",
        help="native-hosted calls the deployed mini service. native uses a local token file.",
    )
    parser.add_argument("--when", default="now", help="Kept for compatibility. Native LinkedIn posts immediately.")
    parser.add_argument("--review-only", action="store_true", help="Only create and print the LinkedIn draft")
    parser.add_argument("--print-copy", action="store_true", help="Print the generated LinkedIn copy")
    parser.add_argument("--dry-run", action="store_true", help="Build the LinkedIn API payload without publishing")
    parser.add_argument("--skip-image", action="store_true", help="Publish without the feature image")
    parser.add_argument("--publish-now", action="store_true", help="Required for live native LinkedIn posting")
    args = parser.parse_args()

    draft = make_draft(args)
    print(json.dumps(asdict(draft), ensure_ascii=False, indent=2))

    if args.print_copy or args.review_only:
        print("\n--- LinkedIn Copy ---\n")
        print(draft.copy)

    if args.review_only:
        return 0

    result = publish_draft(args, draft.json_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
