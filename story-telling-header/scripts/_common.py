"""Shared helpers for the story-telling-header scripts."""
import io, json, os, sys
from pathlib import Path

# UTF-8 stdout on Windows terminals
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
ASSETS_HERO = ROOT / "assets" / "hero"


def hero_dir_for(cfg_path: str = None) -> Path:
    """Where a config's hero media lives: next to the config, else the repo's assets/hero.
    Keeps the normal flow (config at repo root -> assets/hero) while letting the bundled
    examples keep their own media under examples/<name>/assets/hero."""
    if cfg_path:
        d = Path(cfg_path).resolve().parent / "assets" / "hero"
        return d
    return ASSETS_HERO


def load_env():
    """Minimal .env loader (no dependency needed). Also respects real env vars."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def openrouter_key():
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key or key.startswith("sk-or-v1-your-key"):
        sys.exit("ERROR: set OPENROUTER_API_KEY in .env (copy .env.example). "
                 "Get one at https://openrouter.ai/settings/keys")
    return key


def load_config(path: str = None) -> dict:
    """Load story.config.json from repo root (or an explicit path)."""
    p = Path(path) if path else (ROOT / "story.config.json")
    if not p.exists():
        sys.exit(f"ERROR: {p.name} not found. Copy one from examples/, e.g.\n"
                 f"  cp examples/blog/story.config.json story.config.json")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    scenes = cfg.get("hero", {}).get("scenes", [])
    if len(scenes) != 4:
        sys.exit(f"ERROR: hero.scenes must have exactly 4 scenes (found {len(scenes)}).")
    return cfg
