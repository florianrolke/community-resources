from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv


API_BASE = "https://api.apify.com/v2"


def load_token(env_name: str = "APIFY_API_TOKEN") -> str:
    load_dotenv()
    token = os.getenv(env_name)
    if not token:
        raise SystemExit(f"{env_name} is not set. Copy .env.example to .env or export it.")
    return token


def apify_json(path: str, token: str, method: str = "GET", body: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    sep = "&" if "?" in path else "?"
    response = requests.request(
        method,
        f"{API_BASE}{path}{sep}token={quote(token)}",
        json=body,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json() if response.text else {}


def start_actor(actor_id: str, token: str, payload: dict[str, Any]) -> str:
    data = apify_json(f"/acts/{actor_id}/runs", token, method="POST", body=payload, timeout=60)
    return data["data"]["id"]


def abort_run(run_id: str, token: str) -> None:
    try:
        apify_json(f"/actor-runs/{run_id}/abort", token, method="POST", timeout=30)
    except Exception as exc:
        print(f"[WARN] Failed to abort run {run_id}: {exc}")


def wait_for_run(run_id: str, token: str, timeout_minutes: int, poll_seconds: int) -> tuple[str, str]:
    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        data = apify_json(f"/actor-runs/{run_id}", token, timeout=30)["data"]
        status = data["status"]
        print(f"run {run_id}: {status}")
        if status == "SUCCEEDED":
            return status, data["defaultDatasetId"]
        if status in {"FAILED", "ABORTED", "TIMED-OUT"}:
            return status, data.get("defaultDatasetId", "")
        time.sleep(poll_seconds)
    abort_run(run_id, token)
    return "ABORTED_BY_WATCHDOG", ""


def fetch_dataset(dataset_id: str, token: str, limit: int = 50000) -> list[dict[str, Any]]:
    data = apify_json(f"/datasets/{dataset_id}/items?format=json&clean=true&limit={limit}", token, timeout=180)
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected dataset response type: {type(data)}")
    return data


def read_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

