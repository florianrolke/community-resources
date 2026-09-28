import csv
import subprocess
import sys
from pathlib import Path


def test_rank_opportunities_orders_and_labels(tmp_path):
    input_file = tmp_path / "opportunities.csv"
    output_file = tmp_path / "ranked.csv"
    rows = [
        {
            "event_name": "Generic Expo",
            "category": "other",
            "description": "broad consumer expo",
            "confidence": "weak",
        },
        {
            "event_name": "WMA Convention & Expo",
            "category": "manufactured housing",
            "description": "upcoming manufactured home community owners, sponsors, exhibitors, president and organizer contacts",
            "confidence": "confirmed",
        },
        {
            "event_name": "Association Magazine",
            "category": "manufactured housing",
            "description": "official magazine newsletter advertise sponsor member directory",
            "confidence": "confirmed",
        },
    ]
    with input_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    subprocess.run(
        [sys.executable, "scripts/rank_opportunities.py", "--input", str(input_file), "--output", str(output_file)],
        check=True,
    )

    with output_file.open(newline="", encoding="utf-8") as f:
        ranked = list(csv.DictReader(f))

    assert ranked[0]["event_name"] == "WMA Convention & Expo"
    assert ranked[0]["recommended_action"] == "attend-now"
    assert any(row["recommended_action"] == "sponsor-or-advertise" for row in ranked)
    assert ranked[-1]["recommended_action"] in {"discard", "watchlist"}


def test_rank_opportunities_recognizes_family_law_events(tmp_path):
    input_file = tmp_path / "family-law.csv"
    output_file = tmp_path / "family-law-ranked.csv"
    rows = [
        {
            "event_name": "ABA Family Law Section Fall Conference",
            "date_start": "2026-10-14",
            "category": "national family law conference",
            "description": "confirmed family law CLE conference with attorneys, matrimonial lawyers, sponsors, networking, reception, committee and program",
            "confidence": "confirmed",
        }
    ]
    with input_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    subprocess.run(
        [sys.executable, "scripts/rank_opportunities.py", "--input", str(input_file), "--output", str(output_file)],
        check=True,
    )

    with output_file.open(newline="", encoding="utf-8") as f:
        ranked = list(csv.DictReader(f))

    assert int(ranked[0]["opportunity_score"]) >= 80
    assert ranked[0]["recommended_action"] == "attend-now"
