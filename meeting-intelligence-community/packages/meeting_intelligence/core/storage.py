"""Filesystem state, job, and artifact storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fathom import recording_id, safe_slug


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def processed_ids(settings) -> set[str]:
    return set(read_json(settings.state_dir / "processed_meetings.json", []))


def mark_processed(settings, source_id: str) -> None:
    ids = processed_ids(settings)
    ids.add(source_id)
    write_json(settings.state_dir / "processed_meetings.json", sorted(ids))


def enqueue_payload(settings, payload: dict) -> Path:
    source_id = recording_id(payload)
    path = settings.jobs_dir / f"{safe_slug(source_id)}.json"
    write_json(path, payload)
    return path


def pending_jobs(settings) -> list[Path]:
    return sorted(settings.jobs_dir.glob("*.json"))


def move_job_to_processed(settings, job_path: Path) -> Path:
    target = settings.processed_dir / job_path.name
    job_path.replace(target)
    return target
