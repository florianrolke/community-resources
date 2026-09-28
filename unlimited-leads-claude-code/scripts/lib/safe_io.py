"""
Safe JSON I/O

Handles the tricky edge cases of writing JSON on Windows + OneDrive:

1. OneDrive sync conflicts: os.replace() (atomic rename) can fail when OneDrive
   is syncing the target file. Solution: write directly with open(path, 'w').

2. Crash-safe writes: saves to a temp file first, then renames. If rename fails
   (OneDrive), falls back to direct write.

3. Encoding: always UTF-8 with ensure_ascii=False so international business
   names render correctly.

4. Graceful degradation: if the JSON file is corrupted (e.g., from a previous
   crash mid-write), returns None instead of crashing.

Usage:
    from lib.safe_io import safe_json_write, safe_json_read

    safe_json_write("leads/data.json", my_data)
    data = safe_json_read("leads/data.json")
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


def safe_json_write(path: str | Path, data: Any, indent: int = 2):
    """Write JSON data to file safely.

    Tries atomic write (temp file + rename) first, falls back to direct write
    if rename fails (common on OneDrive-synced directories).

    Args:
        path: Output file path
        data: Data to serialize as JSON
        indent: JSON indentation (default 2)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(".tmp")
    content = json.dumps(data, indent=indent, ensure_ascii=False)

    try:
        # Try atomic write: write to temp, then rename
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(str(tmp_path), str(path))
    except OSError:
        # Fallback: direct write (OneDrive may block os.replace)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        # Clean up temp file if it exists
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def safe_json_read(path: str | Path) -> Optional[Any]:
    """Read JSON data from file, returning None if file is missing or corrupted.

    Args:
        path: Input file path

    Returns:
        Parsed JSON data, or None if file doesn't exist or is invalid
    """
    path = Path(path)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"  [WARN] Corrupted JSON at {path}: {e}")
        return None
