#!/usr/bin/env python3
"""Install luxury Remotion overlay assets into an existing Remotion project."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS = SKILL_ROOT / "assets" / "remotion"


def copy_file(src: Path, dst: Path, overwrite: bool) -> None:
    if dst.exists() and not overwrite:
        print(f"SKIP existing: {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"COPIED: {dst}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remotion-root", required=True, help="Path to the Remotion project root")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing target files")
    args = parser.parse_args()

    root = Path(args.remotion_root).resolve()
    src_root = root / "src"
    if not src_root.exists():
        raise SystemExit(f"Remotion src folder not found: {src_root}")

    copy_file(
        ASSETS / "components" / "LuxuryOverlayKit.tsx",
        src_root / "components" / "luxury-overlays" / "LuxuryOverlayKit.tsx",
        args.overwrite,
    )
    copy_file(
        ASSETS / "compositions" / "LuxuryTalkingHeadEdit.tsx",
        src_root / "compositions" / "LuxuryTalkingHeadEdit.tsx",
        args.overwrite,
    )

    print()
    print("Next: register LuxuryTalkingHeadEditWrapper in src/Root.tsx.")
    print("Place edited_base.mp4 and SFX files in public/, then render with a manifest props JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
