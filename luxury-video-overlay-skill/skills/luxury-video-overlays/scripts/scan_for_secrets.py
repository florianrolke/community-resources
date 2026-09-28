#!/usr/bin/env python3
"""Simple public-release secret scan for this package."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


VALUE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*=\s*['\"]?(?!<your-)[^'\"\s<>]{8,}"),
]

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "out", ".tmp"}
SKIP_SUFFIXES = {".mp4", ".mov", ".mp3", ".wav", ".png", ".jpg", ".jpeg", ".webp"}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts) or path.suffix.lower() in SKIP_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="Path to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in VALUE_PATTERNS):
                findings.append(f"{path}:{line_no}: {line[:160]}")

    if findings:
        print("Potential secrets found:")
        for finding in findings:
            print(finding)
        return 1

    print(f"No obvious secrets found in {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
