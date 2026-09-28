"""
Windows UTF-8 Compatibility

Fixes the cp1252 encoding crash that occurs on Windows when Python scripts
output non-ASCII characters (e.g., business names with accents, unicode symbols).

ALWAYS run scripts with: python -X utf8 script.py
AND call fix_encoding() at the top of every script.

Both are needed — -X utf8 sets the filesystem encoding, fix_encoding() sets stdout/stderr.
"""

import sys


def fix_encoding():
    """Fix Windows stdout/stderr encoding to UTF-8.

    Without this, printing characters like accented names (e.g., "Cafe Acai")
    will crash with: UnicodeEncodeError: 'charmap' codec can't encode character.

    Safe to call on any platform — no-op on Linux/Mac.
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
