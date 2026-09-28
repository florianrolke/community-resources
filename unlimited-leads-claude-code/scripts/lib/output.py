"""
CSV and JSON writers.

CSV is the default deliverable in this repo. Google Sheets is optional and
lives behind an explicit --sheet-url flag, because OAuth setup is where
beginners drop off and it is not needed to get leads.

Two Windows details are handled here so no caller has to remember them:
  - utf-8-sig (BOM) so Excel opens accented business names correctly instead
    of showing "CafÃ©".
  - newline="" so Excel doesn't get a blank row between every record.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Sequence


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def flatten(record: dict, sep: str = "_") -> dict:
    """Flatten one level of nested dicts and join lists, so a record fits a CSV cell."""
    out: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                out[f"{key}{sep}{sub_key}"] = _scalar(sub_value)
        else:
            out[key] = _scalar(value)
    return out


def _scalar(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def write_csv(
    records: Iterable[dict],
    path: str | Path,
    columns: Sequence[str] | None = None,
) -> Path:
    """Write records to CSV. Returns the path written."""
    rows = [flatten(r) for r in records]
    out_path = ensure_dir(path)

    if not rows:
        out_path.write_text("", encoding="utf-8-sig")
        return out_path

    if columns is None:
        # Stable column order: first-seen wins, then any extras that show up later.
        seen: list[str] = []
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.append(key)
        columns = seen

    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})

    return out_path


def write_json(records: Any, path: str | Path) -> Path:
    out_path = ensure_dir(path)
    out_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out_path


def read_any(path: str | Path) -> list[dict]:
    """Read a .json or .csv lead file into a list of dicts."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")

    if p.suffix.lower() == ".csv":
        with open(p, "r", newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # Tolerate {"leads": [...]} / {"results": [...]} / {"items": [...]} wrappers.
        for key in ("leads", "results", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return data


def write_both(records: list[dict], json_path=None, csv_path=None, columns=None) -> list[Path]:
    """Convenience: write JSON and/or CSV, whichever paths were given."""
    written = []
    if json_path:
        written.append(write_json(records, json_path))
    if csv_path:
        written.append(write_csv(records, csv_path, columns=columns))
    return written
