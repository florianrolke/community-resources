#!/usr/bin/env python3
"""
Verify emails via the Apify actor `ryanclinton~bulk-email-verifier` (deep SMTP).

This is the fast, hosted alternative to Reacher — one synchronous Apify run
verifies a whole batch. Reads a CSV, verifies every email it finds (either in a
named column or auto-detected across all columns), and writes the same CSV back
with an `apify_verification` column (valid / risky / invalid / catch_all / unknown).

Usage:
    python verify_emails_apify.py --input leads.csv --output leads-verified.csv
    python verify_emails_apify.py --input leads.csv --output out.csv --email-column email
    python verify_emails_apify.py --emails a@x.com b@y.com   # ad-hoc, prints verdicts

Requires: requests, python-dotenv. Reads APIFY_API_TOKEN (rotates _5/_4/_6/_3/_2)
from the nearest .env found by walking up parent directories.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

import requests

ACTOR_URL = "https://api.apify.com/v2/acts/ryanclinton~bulk-email-verifier/run-sync-get-dataset-items"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def load_env() -> None:
    """Walk up from cwd and this file looking for a .env, load the first found."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    starts = [Path.cwd(), Path(__file__).resolve().parent]
    seen: set[Path] = set()
    for start in starts:
        for d in [start, *start.parents]:
            if d in seen:
                continue
            seen.add(d)
            env_file = d / ".env"
            if env_file.exists():
                load_dotenv(env_file, override=False)
                return


def get_apify_token() -> str:
    for suffix in ["_5", "_4", "_6", "_3", "_2", ""]:
        val = os.getenv(f"APIFY_API_TOKEN{suffix}", "")
        if val:
            return val
    return ""


def apify_bulk_verify(emails: list[str]) -> dict[str, dict]:
    """Verify a batch of emails. Returns dict keyed by lowercase email -> result item."""
    unique = sorted({e.lower() for e in emails if EMAIL_RE.fullmatch(e)})
    if not unique:
        return {}
    token = get_apify_token()
    if not token:
        print("ERROR: No APIFY_API_TOKEN found in .env", file=sys.stderr)
        return {}

    payload = {
        "emails": unique,
        "mode": "enrichment-validation",
        "verificationLevel": "deep",
        "maxEmails": 0,
        "smtpTimeout": 20,
        "maxConcurrency": 3,
        "outputProfile": "standard",
    }
    print(f"  Verifying {len(unique)} emails via Apify ryanclinton~bulk-email-verifier...")
    r = requests.post(ACTOR_URL, params={"token": token},
                      headers={"Content-Type": "application/json"},
                      json=payload, timeout=3600)
    if not r.ok:
        print(f"  ERROR: Apify HTTP {r.status_code}: {r.text[:400]}", file=sys.stderr)
        return {}
    body = r.json()
    items = body if isinstance(body, list) else (body.get("items") or body.get("data") or [body])
    out: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("recordType") == "summary":
            continue
        addr = str(item.get("email") or item.get("input") or item.get("address") or "").lower()
        if addr:
            out[addr] = item
    print(f"  Got {len(out)} verification results.")
    return out


def verdict(item: dict) -> str:
    if not item:
        return "unknown"
    status = str(item.get("status") or item.get("smtpStatus") or item.get("verdict") or "").lower()
    is_valid = item.get("isValid")
    if status in {"valid", "deliverable", "safe"} or is_valid is True:
        return "valid"
    if status in {"invalid", "undeliverable", "rejected"} or is_valid is False:
        return "invalid"
    if "catch" in status:
        return "catch_all"
    return status or "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify emails via Apify bulk verifier.")
    ap.add_argument("--input", help="Input CSV")
    ap.add_argument("--output", help="Output CSV (defaults to overwriting input)")
    ap.add_argument("--email-column", help="Column holding the email (default: auto-detect across all columns)")
    ap.add_argument("--emails", nargs="*", help="Ad-hoc emails to verify (skips CSV mode)")
    args = ap.parse_args()

    load_env()

    # Ad-hoc mode
    if args.emails:
        results = apify_bulk_verify(args.emails)
        for em in args.emails:
            print(f"  {em}: {verdict(results.get(em.lower(), {}))}")
        return 0

    if not args.input:
        ap.error("provide --input CSV or --emails")

    with open(args.input, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if "apify_verification" not in fieldnames:
        fieldnames.append("apify_verification")

    # Collect emails
    all_emails: set[str] = set()
    for row in rows:
        cols = [args.email_column] if args.email_column else list(row.keys())
        for col in cols:
            all_emails.update(EMAIL_RE.findall(row.get(col, "") or ""))

    print(f"Found {len(all_emails)} unique emails to verify.")
    results = apify_bulk_verify(list(all_emails))

    out_path = Path(args.output or args.input)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    valid = risky = 0
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            cols = [args.email_column] if args.email_column else list(row.keys())
            found: list[str] = []
            for col in cols:
                found += EMAIL_RE.findall(row.get(col, "") or "")
            v = ""
            if found:
                v = verdict(results.get(found[0].lower(), {}))
                if v == "valid":
                    valid += 1
                elif v == "risky":
                    risky += 1
            row["apify_verification"] = v
            writer.writerow(row)

    print(f"Done -> {out_path}  ({valid} valid / {risky} risky across primary emails)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
