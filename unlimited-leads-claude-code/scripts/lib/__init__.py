"""
Shared library for the UNLIMITED Leads system.

Small, boring, reusable pieces that every script leans on:

    env             repo-root-anchored .env loading (read env.py — it explains
                    a bug that will bite you if you skip it)
    output          CSV / JSON writers with the Windows-Excel details handled
    windows_compat  fix_encoding() — stops UnicodeEncodeError on Windows
    checkpoint      save every N records so a crash at lead 400 of 1,000
                    doesn't cost you the first 399
    api_key_rotation  rotate across multiple keys when one hits its limit
    rate_limiter    polite delays between requests
    safe_io         atomic JSON read/write (no half-written files)
"""

from scripts.lib.windows_compat import fix_encoding

# Auto-fix Windows console encoding as soon as anything imports the library.
fix_encoding()

__all__ = ["fix_encoding"]
