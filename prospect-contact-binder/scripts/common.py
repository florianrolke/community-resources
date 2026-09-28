from __future__ import annotations

import csv
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]
EVENT_FIELDS = [
    "event_name", "date_start", "date_end", "venue", "city", "state", "country",
    "category", "source", "event_url", "organizer", "organizer_url", "cost", "tags",
    "description", "confidence", "evidence",
]
CONTACT_FIELDS = [
    "person_name", "title", "organization", "role_type", "event_name", "segment", "email",
    "phone", "linkedin_url", "facebook_url", "instagram_url", "website", "source",
    "confidence", "evidence", "next_action",
]
ASSOCIATION_FIELDS = [
    "association_name", "segment", "city", "state", "country", "website", "event_calendar_url",
    "member_directory_url", "linkedin_url", "facebook_url", "instagram_url", "contact_name",
    "contact_title", "email", "phone", "source", "confidence", "evidence",
]
LINKEDIN_FIELDS = ["name", "company", "type", "linkedin_url", "match_confidence", "evidence", "notes"]


def load_env() -> None:
    if load_dotenv:
        load_dotenv(ROOT / ".env")


def env_keys(prefix: str, max_number: int = 20, preferred: list[str] | None = None) -> list[str]:
    load_env()
    if preferred:
        names = [f"{prefix}_{suffix}" if suffix else prefix for suffix in preferred]
    else:
        names = [prefix] + [f"{prefix}_{i}" for i in range(2, max_number + 1)]
    out: list[str] = []
    for name in names:
        value = os.getenv(name)
        if value and value not in out:
            out.append(value)
    return out


class RotatingKeyClient:
    def __init__(self, label: str, keys: list[str], min_delay: float = 0.5):
        self.label = label
        self.keys = keys
        self.index = 0
        self.exhausted: set[int] = set()
        self.min_delay = min_delay
        self.last_call = 0.0

    @property
    def available(self) -> bool:
        return bool(self.keys) and len(self.exhausted) < len(self.keys)

    def key(self) -> str:
        if not self.available:
            raise RuntimeError(f"No {self.label} keys available")
        return self.keys[self.index]

    def wait(self) -> None:
        elapsed = time.time() - self.last_call
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_call = time.time()

    def mark_exhausted_and_rotate(self) -> bool:
        self.exhausted.add(self.index)
        for _ in range(len(self.keys)):
            self.index = (self.index + 1) % len(self.keys)
            if self.index not in self.exhausted:
                return True
        return False


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: Iterable[dict], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ascii_norm(text: object) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def compact_text(text: object, max_len: int = 220) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[:max_len]


def slugify(text: object) -> str:
    return re.sub(r"\s+", "-", ascii_norm(text)).strip("-") or "event-campaign"


def first_value(row: dict, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def dedupe_rows(rows: Iterable[dict], key_fields: list[str]) -> list[dict]:
    seen: set[tuple[str, ...]] = set()
    out = []
    for row in rows:
        key = tuple(ascii_norm(row.get(field, "")) for field in key_fields)
        if key in seen or not any(key):
            continue
        seen.add(key)
        out.append(row)
    return out