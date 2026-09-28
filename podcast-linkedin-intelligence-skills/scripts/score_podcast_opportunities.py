from __future__ import annotations

import argparse

from scripts.common import ascii_norm, read_csv, write_csv

FIELDS = [
    "fit_tier",
    "opportunity_score",
    "podcast_or_series",
    "episode_title",
    "episode_url",
    "guest_or_speaker",
    "detected_themes",
    "pitch_angle",
    "notes",
]

POSITIVE_TERMS = {
    "model risk": 5,
    "model validation": 5,
    "financial engineering": 5,
    "quant": 4,
    "derivatives": 4,
    "risk management": 4,
    "ai governance": 4,
    "ai risk": 4,
    "machine learning": 3,
    "portfolio": 3,
    "volatility": 3,
    "credit risk": 3,
    "bank": 2,
    "finance": 2,
}

NEGATIVE_TERMS = {
    "personal financial": -5,
    "gxp": -4,
    "medical": -4,
    "software validation": -4,
    "chicken": -3,
    "raising capital": -3,
    "sales": -2,
}


def score_row(row: dict) -> dict:
    text = ascii_norm(" ".join([row.get("podcast_or_series", ""), row.get("episode_title", ""), row.get("notes", "")]))
    score = 0
    themes = []
    for term, weight in POSITIVE_TERMS.items():
        if ascii_norm(term) in text:
            score += weight
            themes.append(term)
    for term, weight in NEGATIVE_TERMS.items():
        if ascii_norm(term) in text:
            score += weight
    if "podcast" in text:
        score += 1
    if row.get("guest_or_speaker", "").strip():
        score += 1
    tier = "high" if score >= 8 else "medium" if score >= 5 else "low"
    pitch = ""
    if "model risk" in themes or "model validation" in themes:
        pitch = "Pitch Jonathan on model validation/model risk textbook expertise and practical bank model governance."
    elif "ai governance" in themes or "ai risk" in themes:
        pitch = "Pitch Jonathan on AI governance, institutional model risk, and practical guardrails for finance teams."
    elif "financial engineering" in themes or "quant" in themes or "derivatives" in themes:
        pitch = "Pitch Jonathan as a financial engineering educator bridging quant methods, derivatives, and risk management."
    else:
        pitch = "Review manually; possible adjacent finance/risk fit."
    return {
        "fit_tier": tier,
        "opportunity_score": score,
        "podcast_or_series": row.get("podcast_or_series", ""),
        "episode_title": row.get("episode_title", ""),
        "episode_url": row.get("episode_url", ""),
        "guest_or_speaker": row.get("guest_or_speaker", ""),
        "detected_themes": "; ".join(themes),
        "pitch_angle": pitch,
        "notes": row.get("notes", ""),
    }


def is_real_episode_url(row: dict) -> bool:
    url = row.get("episode_url", "").lower()
    return bool(url) and "google.com/search" not in url


def main() -> int:
    parser = argparse.ArgumentParser(description="Score discovered podcast/interview rows as guest-appearance opportunities.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [score_row(row) for row in read_csv(args.input) if is_real_episode_url(row)]
    rows.sort(key=lambda item: int(item["opportunity_score"]), reverse=True)
    write_csv(args.output, rows, FIELDS)
    print(f"Rows written: {len(rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
