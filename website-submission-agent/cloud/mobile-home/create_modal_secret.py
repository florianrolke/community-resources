#!/usr/bin/env python3
"""Create Modal secret for the mobile-home cloud runner without printing values."""

from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / ".env"
TMP_JSON = Path(r"C:\tmp\mobile_home_submission_modal_secret.json")
TOKEN_FILE = Path(r"C:\tmp\mobile_home_submission_agent_auth_token.txt")


def read_env_value(name: str) -> str:
    text = ENV_PATH.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"^{re.escape(name)}=(.+)$", text, re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip('"').strip("'")


def main() -> int:
    capsolver_key = read_env_value("Capsolver_API_KEY") or read_env_value("CAPSOLVER_API_KEY")
    if not capsolver_key:
        print("Missing Capsolver_API_KEY/CAPSOLVER_API_KEY in .env", file=sys.stderr)
        return 1

    auth_token = secrets.token_urlsafe(32)
    TMP_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "CAPSOLVER_API_KEY": capsolver_key,
        "Capsolver_API_KEY": capsolver_key,
        "MOBILE_HOME_AGENT_AUTH_TOKEN": auth_token,
    }
    TMP_JSON.write_text(json.dumps(payload), encoding="utf-8")
    TOKEN_FILE.write_text(auth_token, encoding="utf-8")
    try:
        proc = subprocess.run(
            [
                "modal",
                "secret",
                "create",
                "mobile-home-submission-agent-secrets",
                "--from-json",
                str(TMP_JSON),
                "--force",
            ],
            text=True,
            capture_output=True,
        )
    finally:
        TMP_JSON.unlink(missing_ok=True)

    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode == 0:
        print(f"Auth token saved locally at {TOKEN_FILE}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
