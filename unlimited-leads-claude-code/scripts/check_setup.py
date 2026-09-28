#!/usr/bin/env python3
"""
Run this first. It tells you exactly what's working and what to fix.

    python -X utf8 scripts/check_setup.py

Checks Python, dependencies, and which of your API keys are live — with a real
(free) call to each service, so a typo'd key fails here rather than 200 leads
into a run.

It also prints which .env file it loaded. That sounds boring; it isn't. The
usual way to load a .env walks up the directory tree until it finds one, so if
you clone this repo somewhere that has a .env above it, your scripts silently
use those keys. Works on your machine, fails on everyone else's. This repo only
ever reads its own .env, and prints the path so you can confirm.
"""

import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.env import load_env, get, describe, REPO_ROOT

fix_encoding()

OK, WARN, BAD = "[ OK ]", "[WARN]", "[FAIL]"


def header(text: str):
    print(f"\n{text}\n" + "-" * len(text))


def check_python() -> bool:
    header("Python")
    v = sys.version_info
    good = v >= (3, 10)
    print(f"{OK if good else BAD} Python {v.major}.{v.minor}.{v.micro}")
    if not good:
        print("       This repo needs Python 3.10 or newer. Install from python.org.")
    enc = (sys.stdout.encoding or "").lower()
    utf8 = "utf" in enc
    print(f"{OK if utf8 else WARN} Console encoding: {sys.stdout.encoding}")
    if not utf8:
        print("       Run scripts with `python -X utf8` so accented names don't crash.")
    return good


def check_deps() -> bool:
    header("Dependencies")
    required = {
        "requests": "requests", "dotenv": "python-dotenv", "httpx": "httpx",
        "apify_client": "apify-client", "anthropic": "anthropic", "bs4": "beautifulsoup4",
        "html2text": "html2text", "pandas": "pandas",
    }
    optional = {"gspread": "gspread (only for Google Sheets output)"}
    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod)
            print(f"{OK} {pkg}")
        except ImportError:
            print(f"{BAD} {pkg} — not installed")
            missing.append(pkg)
    for mod, pkg in optional.items():
        try:
            __import__(mod)
            print(f"{OK} {pkg}")
        except ImportError:
            print(f"{WARN} {pkg} — not installed (fine unless you use --sheet-url)")
    if missing:
        print("\n       Fix: pip install -r requirements.txt")
    return not missing


def check_env_file() -> bool:
    header("Environment file")
    info = describe()
    print(f"     Repo root: {info['repo_root']}")
    if info["env_exists"]:
        print(f"{OK} Loaded: {info['env_path']}")
        return True
    print(f"{BAD} No .env at {info['env_path']}")
    print("       Fix (Windows):   copy .env.example .env")
    print("       Fix (Mac/Linux): cp .env.example .env")
    print("       Then open it and paste your keys in.")
    return False


def ping_apify(token: str) -> tuple[bool, str]:
    import requests
    try:
        r = requests.get("https://api.apify.com/v2/users/me",
                         headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.status_code == 401:
            return False, "key rejected"
        r.raise_for_status()
        d = r.json().get("data", {})
        plan = (d.get("plan") or {}).get("id", "free")
        return True, f"user {d.get('username','?')}, plan {plan}"
    except Exception as e:
        return False, str(e)[:60]


def ping_anthropic(key: str) -> tuple[bool, str]:
    try:
        import anthropic
        c = anthropic.Anthropic(api_key=key)
        c.messages.create(model="claude-opus-5", max_tokens=1,
                          messages=[{"role": "user", "content": "hi"}])
        return True, "key works"
    except Exception as e:
        msg = str(e)
        if "authentication" in msg.lower() or "401" in msg:
            return False, "key rejected"
        if "credit" in msg.lower() or "billing" in msg.lower():
            return False, "key valid but no credit — add billing at console.anthropic.com"
        return False, msg[:70]


def ping_tavily(key: str) -> tuple[bool, str]:
    import requests
    try:
        r = requests.post("https://api.tavily.com/search",
                          json={"api_key": key, "query": "test", "max_results": 1}, timeout=25)
        if r.status_code in (401, 403):
            return False, "key rejected"
        if r.status_code == 429:
            return False, "monthly quota used up — add TAVILY_API_KEY_2"
        r.raise_for_status()
        return True, "key works"
    except Exception as e:
        return False, str(e)[:60]


def check_keys(skip_live: bool) -> dict:
    header("API keys")
    checks = [
        ("APIFY_API_TOKEN", "Systems 1 and 2 (scraping)", ping_apify,
         "https://console.apify.com -> Settings -> API & Integrations"),
        ("ANTHROPIC_API_KEY", "Research + outreach writing", ping_anthropic,
         "https://console.anthropic.com"),
        ("TAVILY_API_KEY", "Lead research (free: 1,000/month)", ping_tavily,
         "https://tavily.com"),
    ]
    status = {}
    for name, what, ping, where in checks:
        value = get(name)
        if not value:
            print(f"{WARN} {name:<20} missing   — needed for: {what}")
            print(f"       Sign up: {where}")
            status[name] = False
            continue
        if skip_live:
            print(f"{OK} {name:<20} present   — {what}")
            status[name] = True
            continue
        good, detail = ping(value)
        print(f"{OK if good else BAD} {name:<20} {'works' if good else 'FAILED':<9} — {detail}")
        if not good:
            print(f"       Get a new one: {where}")
        status[name] = good

    for optional, what in [("ANYMAILFINDER_API_KEY", "extra email lookups"),
                           ("EXA_API_KEY", "a second research search engine")]:
        print(f"{OK if get(optional) else WARN} {optional:<20} "
              f"{'present' if get(optional) else 'missing'}   — optional: {what}")

    creds = REPO_ROOT / (get("GOOGLE_APPLICATION_CREDENTIALS") or "credentials.json")
    print(f"{OK if creds.exists() else WARN} {'Google Sheets':<20} "
          f"{'configured' if creds.exists() else 'not set up'}   — optional, CSV works without it")
    return status


def summarize(status: dict, env_ok: bool, deps_ok: bool) -> int:
    header("What you can run right now")
    apify = status.get("APIFY_API_TOKEN")
    claude = status.get("ANTHROPIC_API_KEY")
    tavily = status.get("TAVILY_API_KEY")

    rows = [
        ("System 3 — free scraping", deps_ok, "no keys needed"),
        ("System 1 — LinkedIn contacts", deps_ok and apify, "needs Apify"),
        ("System 2 — Google Maps", deps_ok and apify, "needs Apify"),
        ("Lead research", deps_ok and claude and tavily, "needs Anthropic + Tavily"),
        ("Outreach writing", deps_ok and claude, "needs Anthropic"),
    ]
    for label, ready, note in rows:
        print(f"  {'READY    ' if ready else 'not yet  '} {label:<32} ({note})")

    print()
    if deps_ok and not env_ok:
        print("Next: copy .env.example to .env and add at least your Apify key.")
        return 1
    if deps_ok and any([apify, claude]):
        print("Next — start with the free one, it costs nothing:")
        print('  python -X utf8 scripts/03_free_scraping/build_dorks.py --niche "barber" --location "Tuscaloosa AL"')
        if apify:
            print("\nThen your first paid scrape (about 2 cents):")
            print('  python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \\')
            print('      --search "barbers in Tuscaloosa AL" --limit 5 --out-csv output/test.csv')
        return 0
    if deps_ok:
        print("Next: System 3 works with no keys at all — try it:")
        print('  python -X utf8 scripts/03_free_scraping/build_dorks.py --niche "barber"')
        return 1
    print("Next: pip install -r requirements.txt")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Check your setup before running anything else")
    parser.add_argument("--skip-live", dest="skip_live", action="store_true",
                        help="Don't call the APIs, just check the keys are present")
    args = parser.parse_args()

    print("=" * 66)
    print(" UNLIMITED Leads — setup check")
    print("=" * 66)

    py_ok = check_python()
    deps_ok = check_deps()
    env_ok = check_env_file()
    load_env()
    status = check_keys(args.skip_live) if env_ok else {}

    code = summarize(status, env_ok, deps_ok and py_ok)
    print()
    sys.exit(code)


if __name__ == "__main__":
    main()
