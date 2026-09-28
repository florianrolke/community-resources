"""Generate Google OAuth token JSON for Docs/Drive, Gmail, or Calendar.

Usage:
    python scripts/auth_google.py --client-secret credentials.json --target docs
    python scripts/auth_google.py --client-secret credentials.json --target gmail
    python scripts/auth_google.py --client-secret credentials.json --target calendar
"""

from __future__ import annotations

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = {
    "docs": ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
    "gmail": ["https://www.googleapis.com/auth/gmail.compose"],
    "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Google OAuth token JSON")
    parser.add_argument("--client-secret", required=True, help="OAuth client JSON downloaded from Google Cloud")
    parser.add_argument("--target", choices=sorted(SCOPES), required=True)
    parser.add_argument("--output", help="Optional output token JSON path")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES[args.target])
    creds = flow.run_local_server(port=0)
    token_json = creds.to_json()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(token_json)
        print(f"Wrote {args.output}")
    print(token_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
