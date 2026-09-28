"""
Repo-root-anchored .env loading.

Why this module exists
----------------------
`load_dotenv()` with no arguments walks UP the directory tree until it finds a
`.env`. That is convenient right up until it isn't: if you clone this repo into
a folder that already has a `.env` somewhere above it, every script will
silently pick up those keys. It works on your machine, then fails on someone
else's — the worst kind of bug, because nothing errors.

So: never call bare `load_dotenv()` in this repo. Call `load_env()` from here.
It only ever reads `<repo root>/.env` and tells you exactly which file it used.

Usage
-----
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from scripts.lib.env import load_env, require

    load_env()
    token = require("APIFY_API_TOKEN")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# scripts/lib/env.py -> scripts/lib -> scripts -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

_loaded = False


def load_env(verbose: bool = False) -> Path | None:
    """Load <repo root>/.env and nothing else. Returns the path used, or None."""
    global _loaded
    if _loaded:
        return ENV_PATH if ENV_PATH.exists() else None

    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Error: python-dotenv is not installed. Run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise

    if ENV_PATH.exists():
        # override=False so a real environment variable still wins over the file,
        # which is what you want in CI and in `KEY=x python script.py` one-offs.
        load_dotenv(ENV_PATH, override=False)
        _loaded = True
        if verbose:
            print(f"Loaded environment from: {ENV_PATH}")
        return ENV_PATH

    if verbose:
        print(f"No .env found at {ENV_PATH}")
        print("Copy .env.example to .env and add your keys.")
    _loaded = True
    return None


def get(name: str, default: str | None = None) -> str | None:
    """Read a variable, loading .env first if it hasn't been loaded yet."""
    load_env()
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def require(name: str, hint: str = "") -> str:
    """Read a variable, or exit with a message a beginner can act on."""
    value = get(name)
    if not value:
        print(f"\nError: {name} is not set.", file=sys.stderr)
        print(f"  Expected it in: {ENV_PATH}", file=sys.stderr)
        if hint:
            print(f"  {hint}", file=sys.stderr)
        print("\n  Fix: copy .env.example to .env, then add the key.", file=sys.stderr)
        print("  Then run: python -X utf8 scripts/check_setup.py\n", file=sys.stderr)
        sys.exit(1)
    return value


def describe() -> dict:
    """Diagnostics for check_setup.py."""
    load_env()
    return {
        "repo_root": str(REPO_ROOT),
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
    }
