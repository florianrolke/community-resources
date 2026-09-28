#!/usr/bin/env python3
"""
Find the LinkedIn profile URL for people you already have names for.

The problem this solves
-----------------------
A conference roster gives you "Cara McNulty, DPA — CEO, Vibrant Emotional
Health". That is a real person you cannot yet contact. The single highest-value
thing you can add is her actual LinkedIn URL, because a connection request
mentioning her session is the warmest opener available before the event.

Two search engines, in order, because they fail differently
----------------------------------------------------------
  1. Exa    — embedding-based. Markedly better at "which profile IS this exact
              person". Free tier, but credits run out.
  2. Tavily — keyword search. Weaker at disambiguation on its own, which is
              exactly why the name check below is not optional. Free tier,
              separate quota, so it keeps working after Exa is dry.

Every candidate URL from either engine goes through the same validation. The
engine only proposes; the name check decides.

The rule that matters: BOTH names must appear in the slug
---------------------------------------------------------
A neural search will happily return a plausible-looking profile for a name it
has never seen. Attaching that URL to a contact is worse than returning
nothing — the row looks complete, so nobody re-checks it, and the outreach
goes to a stranger. Surname alone is not enough either: an uncommon surname is
often an uncommon *family*, so "Alex Nana-Sinkam" matched "brian-nana-sinkam"
— right household, wrong person, and a message that lands as obviously
automated. So: first name AND surname, or the URL is dropped.

An empty cell is honest. A wrong cell is a wrong message.

Usage
-----
    # One person, no file needed — good for spot-checking the matcher
    python -X utf8 -m scripts.enrich_linkedin --name "Cara McNulty" --company "Vibrant Emotional Health"

    # A whole CSV (needs person_name; organization strongly recommended)
    python -X utf8 -m scripts.enrich_linkedin \\
        --input data/speakers.csv --output data/speakers-linkedin.csv

    # Only retry rows that are still missing a URL
    python -X utf8 -m scripts.enrich_linkedin \\
        --input data/speakers-linkedin.csv --output data/speakers-linkedin.csv --only-missing

    # Interrupted? Same command again — it resumes from the checkpoint.
    # Force a clean run instead:
    python -X utf8 -m scripts.enrich_linkedin --input ... --output ... --no-resume

Cost: $0. Both engines are free-tier.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from scripts.common import (
    CONTACT_FIELDS,
    compact_text,
    env_keys,
    load_env,
    read_csv,
    write_csv,
)

from scripts.linkedin_match import best_match, looks_like_person


class KeyPool:
    """
    Rotates API keys and remembers which ones are spent.

    Thread-safe: enrichment runs in a pool, and two workers hitting the same
    dead key must not each burn a separate retry cycle discovering that.
    """

    def __init__(self, label: str, keys: list[str]):
        self.label = label
        self.keys = keys
        self.index = 0
        self.dead: set[int] = set()
        self.lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.keys) and len(self.dead) < len(self.keys)

    def current(self) -> tuple[int, str] | tuple[None, None]:
        with self.lock:
            if not self.available:
                return None, None
            for _ in range(len(self.keys)):
                if self.index not in self.dead:
                    return self.index, self.keys[self.index]
                self.index = (self.index + 1) % len(self.keys)
            return None, None

    def retire(self, idx: int) -> None:
        with self.lock:
            self.dead.add(idx)
            self.index = (idx + 1) % len(self.keys)


def exa_search(pool: KeyPool, person: str, company: str) -> list[dict]:
    """
    Ask Exa for candidates, WITH the profile text.

    The text is the whole point — it is what says where the person actually
    works, and without it there is nothing to verify against but the URL.
    Returns [{url, title, text}]; [] if Exa is unavailable or dry.
    """
    for _ in range(len(pool.keys) or 1):
        idx, key = pool.current()
        if key is None:
            return []
        try:
            r = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={
                    "query": f"{person} {company} LinkedIn".strip(),
                    "numResults": 10,
                    "includeDomains": ["linkedin.com"],
                    "type": "neural",
                    "contents": {"text": {"maxCharacters": 600}},
                },
                timeout=40,
            )
            # 401/403 = bad key, 402 = out of credits, 429 = rate limited.
            if r.status_code in (401, 402, 403, 429):
                pool.retire(idx)
                continue
            r.raise_for_status()
            return [
                {
                    "url": item.get("url", "") or "",
                    "title": item.get("title", "") or "",
                    "text": item.get("text", "") or "",
                }
                for item in r.json().get("results", [])
            ]
        except requests.RequestException:
            return []
    return []


def tavily_search(pool: KeyPool, person: str, company: str) -> list[dict]:
    """
    Ask Tavily for candidates, with each result's snippet.

    Tavily returns a `content` snippet per result; that snippet is what gets
    checked for the person and the employer. Returns [{url, title, text}].
    """
    for _ in range(len(pool.keys) or 1):
        idx, key = pool.current()
        if key is None:
            return []
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": f'"{person}" {company} LinkedIn profile'.strip(),
                    "max_results": 10,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_domains": ["linkedin.com"],
                },
                timeout=30,
            )
            if r.status_code in (401, 403, 429, 432):
                pool.retire(idx)
                continue
            r.raise_for_status()
            payload = r.json()
            return [
                {
                    "url": item.get("url", "") or "",
                    "title": item.get("title", "") or "",
                    "text": item.get("content", "") or "",
                }
                for item in payload.get("results", [])
            ]
        except requests.RequestException:
            return []
    return []


def find_linkedin(exa: KeyPool, tavily: KeyPool, person: str, company: str) -> tuple[str, str, str]:
    """
    Exa first, Tavily second. Returns (url, confidence, source).

    Every candidate is judged on the profile's own text — does it name this
    person, at this company — not on the URL. See scripts/linkedin_match.py.

    ("", "", reason) means nothing was verifiable, which is a real answer
    rather than a failure.
    """
    if not looks_like_person(person):
        return "", "", "skipped-not-a-person"

    last_reason = "no-engine-available"
    for label, search, pool in (("exa", exa_search, exa), ("tavily", tavily_search, tavily)):
        if not pool.available:
            continue
        results = search(pool, person, company)
        url, confidence, reason = best_match(person, company, results)
        last_reason = reason
        if url:
            return url, confidence, label
    return "", "", last_reason


def checkpoint_path(output: str) -> Path:
    return Path(output).with_suffix(".checkpoint.json")


def load_checkpoint(output: str) -> dict[str, dict]:
    path = checkpoint_path(output)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_checkpoint(output: str, done: dict[str, dict]) -> None:
    try:
        checkpoint_path(output).write_text(
            json.dumps(done, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # A failed checkpoint must never kill a working run.


def row_key(row: dict) -> str:
    return f"{(row.get('person_name') or '').strip().lower()}|{(row.get('organization') or '').strip().lower()}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Find LinkedIn profile URLs for people you already have names for (Exa -> Tavily, free).",
    )
    ap.add_argument("--input", help="CSV with person_name (and ideally organization)")
    ap.add_argument("--output", help="Where to write the enriched CSV")
    ap.add_argument("--name", help="Single lookup: the person's full name")
    ap.add_argument("--company", default="", help="Single lookup: their company")
    ap.add_argument("--limit", type=int, help="Only process the first N rows. Use this first.")
    ap.add_argument("--workers", type=int, default=4, help="Parallel lookups (default 4)")
    ap.add_argument("--only-missing", action="store_true",
                    help="Skip rows that already have a linkedin_url")
    ap.add_argument("--no-resume", action="store_true",
                    help="Ignore any existing checkpoint and start clean")
    args = ap.parse_args()

    load_env()
    exa = KeyPool("Exa", env_keys("EXA_API_KEY"))
    tavily = KeyPool("Tavily", env_keys("TAVILY_API_KEY"))

    if not exa.available and not tavily.available:
        print("No EXA_API_KEY or TAVILY_API_KEY found. Both are free:\n"
              "  https://exa.ai   https://tavily.com", file=sys.stderr)
        return 1
    print(f"Engines: Exa {len(exa.keys)} key(s), Tavily {len(tavily.keys)} key(s)")

    # --- single lookup -----------------------------------------------------
    if args.name:
        url, conf, source = find_linkedin(exa, tavily, args.name, args.company)
        if url:
            print(f"{args.name}: {url}   ({conf}, via {source})")
        else:
            print(f"{args.name}: no profile passed the name check "
                  f"({source or 'searched, nothing matched'})")
        return 0

    if not args.input or not args.output:
        ap.error("either --name, or both --input and --output, are required")

    # --- batch -------------------------------------------------------------
    rows = read_csv(args.input)
    if not rows:
        print(f"{args.input} is empty", file=sys.stderr)
        return 1

    targets = [r for r in rows if (r.get("person_name") or "").strip()]
    if args.only_missing:
        targets = [r for r in targets if not (r.get("linkedin_url") or "").strip()]
    if args.limit:
        targets = targets[: args.limit]

    done = {} if args.no_resume else load_checkpoint(args.output)
    if done:
        before = len(targets)
        targets = [r for r in targets if row_key(r) not in done]
        print(f"Resuming: {before - len(targets)} already done, {len(targets)} to go")

    print(f"Looking up {len(targets)} profile(s)\n")
    started = time.time()
    results: dict[str, dict] = dict(done)
    counter = {"n": 0}
    lock = threading.Lock()

    def work(row: dict) -> tuple[str, dict]:
        person = (row.get("person_name") or "").strip()
        company = (row.get("organization") or "").strip()
        url, conf, source = find_linkedin(exa, tavily, person, company)
        return row_key(row), {"linkedin_url": url, "confidence": conf, "source": source}

    if targets:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(work, r): r for r in targets}
            for fut in as_completed(futures):
                row = futures[fut]
                person = (row.get("person_name") or "?")[:34]
                try:
                    key, payload = fut.result()
                except Exception as exc:
                    key, payload = row_key(row), {"linkedin_url": "", "confidence": "", "source": f"error:{str(exc)[:40]}"}
                results[key] = payload
                with lock:
                    counter["n"] += 1
                    n = counter["n"]
                    if n % 10 == 0 or n == len(targets):
                        save_checkpoint(args.output, results)
                mark = payload["linkedin_url"] or (payload["source"] or "-")
                print(f"  [{n}/{len(targets)}] {person:<36} {mark}")

    # Apply results to every row, leaving untouched rows intact.
    hits = 0
    for row in rows:
        payload = results.get(row_key(row))
        if not payload or not payload.get("linkedin_url"):
            continue
        row["linkedin_url"] = payload["linkedin_url"]
        row["confidence"] = payload["confidence"] or row.get("confidence", "")
        row["next_action"] = "outreach"
        row["evidence"] = compact_text(
            f"{row.get('evidence', '')} | LinkedIn matched via {payload['source']}, "
            f"first and last name verified in slug"
        )
        hits += 1

    fieldnames = CONTACT_FIELDS if all(f in rows[0] for f in ("person_name", "linkedin_url")) else None
    write_csv(args.output, rows, fieldnames)

    total_with_url = sum(1 for r in rows if (r.get("linkedin_url") or "").strip())
    save_checkpoint(args.output, results)
    print(f"\n{'=' * 66}")
    print(f"{len(rows)} rows -> {args.output}")
    print(f"  {hits} new profile(s) matched this run")
    print(f"  {total_with_url}/{len(rows)} rows now have a LinkedIn URL")
    print(f"  {time.time() - started:.0f}s, $0.00")
    if not exa.available and exa.keys:
        print("  note: Exa keys are spent — Tavily carried this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
