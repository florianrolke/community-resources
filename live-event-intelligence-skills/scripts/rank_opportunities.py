from __future__ import annotations

import argparse
import csv
from pathlib import Path


LABELS = {
    "attend-now": 80,
    "sponsor-or-advertise": 72,
    "scrape-for-leads": 65,
    "speaker-pitch": 70,
    "watchlist": 45,
    "discard": 0,
}

CONFIDENCE_POINTS = {
    "confirmed": 10,
    "probable": 7,
    "historical-reference": 4,
    "needs-manual-verification": 3,
    "weak": 1,
}


def as_int(value: str, default: int = 0) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


def lower(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip().lower()


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def score_row(row: dict[str, str]) -> dict[str, str]:
    text = " ".join(str(v or "").lower() for v in row.values())
    confidence = lower(row, "confidence")

    icp = as_int(row.get("icp_fit", ""), 0)
    if not icp:
        if has_any(text, [
            "owner", "operator", "founder", "ceo", "president", "community", "dealer", "retailer", "advisor",
            "attorney", "lawyer", "matrimonial", "family law", "divorce", "mediator", "judge", "judiciary",
            "custody", "forensic", "valuation", "bar association", "cle",
        ]):
            icp += 18
        if has_any(text, [
            "manufactured", "mobile home", "voice ai", "exit planning", "cpe", "hvac", "plumbing",
            "practice management", "family mediator", "aaml", "afcc", "aba family law",
        ]):
            icp += 7

    access = as_int(row.get("access_quality", ""), 0)
    if not access:
        if has_any(text, [
            "member directory", "exhibitor", "exhibits", "sponsor", "speaker", "attendee", "people",
            "staff directory", "registration", "agenda", "program", "committee", "faculty",
        ]):
            access += 16
        if has_any(text, ["email", "phone", "linkedin", "contact", "calendar"]):
            access += 4

    timeliness = as_int(row.get("timeliness", ""), 0)
    if not timeliness:
        if has_any(text, ["upcoming", "2026", "register", "save the date"]):
            timeliness += 12
        elif has_any(text, ["2025", "past", "recap"]):
            timeliness += 7

    commercial = as_int(row.get("commercial_intent", ""), 0)
    if not commercial:
        if has_any(text, [
            "exhibitor", "exhibits", "sponsor", "advertise", "magazine", "newsletter", "paid",
            "dealer", "hiring", "funding", "registration fees", "industry partners", "business valuation",
            "forensic accounting", "practice", "law firm",
        ]):
            commercial += 12
        if has_any(text, ["conference", "expo", "trade show", "annual meeting"]):
            commercial += 3

    relationship = as_int(row.get("relationship_leverage", ""), 0)
    if not relationship:
        if has_any(text, [
            "executive director", "president", "chair", "organizer", "program", "education", "chapter",
            "podcast host", "section", "committee", "faculty", "moderator", "fellow",
        ]):
            relationship += 13
        if has_any(text, ["roundtable", "lunch", "luncheon", "reception", "breakfast", "webinar", "zoom", "committee"]):
            relationship += 2

    source = CONFIDENCE_POINTS.get(confidence, 0)
    total = min(100, icp + access + timeliness + commercial + relationship + source)

    if total >= 80 and timeliness >= 10:
        label = "attend-now"
    elif has_any(text, ["magazine", "newsletter", "advertise", "sponsor"]):
        label = "sponsor-or-advertise"
    elif access >= 16:
        label = "scrape-for-leads"
    elif relationship >= 13:
        label = "speaker-pitch"
    elif total >= 45:
        label = "watchlist"
    else:
        label = "discard"

    row["opportunity_score"] = str(total)
    row["recommended_action"] = label
    row["score_notes"] = f"icp={icp};access={access};timeliness={timeliness};commercial={commercial};relationship={relationship};source={source}"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank event, association, and conference opportunities by business outcome.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    with input_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    scored = [score_row(dict(row)) for row in rows]
    base_fields = list(rows[0].keys()) if rows else []
    extra_fields = ["opportunity_score", "recommended_action", "score_notes"]
    fields = base_fields + [field for field in extra_fields if field not in base_fields]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(scored, key=lambda row: int(row["opportunity_score"]), reverse=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
