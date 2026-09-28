"""
skool_financial_scorer_v2.py — Financial Qualification Scorer (wrapper)

Wraps skool_intelligence_v2/shared/financial_scorer.py without modifying it.
Scores a member on financial capacity/wealth proxy (0-100, tiers A/B/C/D).

Independent from Heroes Arc ICP scoring — these are two separate tracks.

Financial dimensions:
  - Position (business owner/founder/CEO signals)
  - Business (established company, employees, services)
  - Industry (high-value traditional industries)
  - Pain (growth/scale signals → ability to invest in solutions)
  - Reachability (LinkedIn, email, website present)
  - Geographic (US, UK, AU, CA priority markets)
  - AI-agency penalty (-50 if they ARE an AI agency — not a buyer)

Usage:
  python execution/skool_financial_scorer_v2.py --input .tmp/test_member.json
"""

import json
import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent
V2_SHARED_DIR = EXECUTION_DIR / "skool_intelligence_v2" / "shared"

# Import v2 financial scorer without modifying it
sys.path.insert(0, str(V2_SHARED_DIR))
sys.path.insert(0, str(EXECUTION_DIR))


def score_financial(member: dict, enrichment: dict) -> dict:
    """
    Score a member's financial qualification.

    Args:
        member: Raw member dict (name, handle, bio, location, profileUrl)
        enrichment: Enrichment dict (from skool_enrichment_pipeline_v2.py)
                    Can be empty dict if enrichment not yet run.

    Returns:
        {
          "financial_score": int (0-100),
          "financial_tier": str ("A"/"B"/"C"/"D"),
          "financial_reasons": list[str],
          "financial_confidence": str
        }
    """
    try:
        from financial_scorer import score_financial_qualification
        score, tier, breakdown = score_financial_qualification(member, enrichment)
        return {
            "financial_score": score,
            "financial_tier": tier,
            "financial_reasons": breakdown.get("reasons", []),
            "financial_confidence": breakdown.get("confidence", "low"),
            "financial_breakdown": breakdown.get("dimension_scores", {}),
        }
    except ImportError as e:
        print(f"  WARNING: Could not import financial_scorer: {e}")
        # Fallback: very basic keyword scoring from bio + enrichment
        return _fallback_financial_score(member, enrichment)


def _fallback_financial_score(member: dict, enrichment: dict) -> dict:
    """Basic keyword-based financial scoring when v2 scorer unavailable."""
    score = 0
    reasons = []
    bio = (member.get("bio", "") + " " + enrichment.get("bio_summary", "")).lower()

    owner_keywords = ["owner", "founder", "ceo", "president", "managing director", "principal", "partner"]
    for kw in owner_keywords:
        if kw in bio:
            score += 20
            reasons.append(f"Business owner signal: '{kw}'")
            break

    revenue_keywords = ["million", "7-figure", "8-figure", "$1m", "$5m", "$10m", "annual revenue"]
    for kw in revenue_keywords:
        if kw in bio:
            score += 15
            reasons.append(f"Revenue signal: '{kw}'")
            break

    industry_keywords = ["manufacturing", "construction", "distribution", "logistics", "healthcare",
                          "legal", "accounting", "financial", "real estate", "dental", "medical"]
    for kw in industry_keywords:
        if kw in bio:
            score += 10
            reasons.append(f"High-value industry: '{kw}'")
            break

    ai_agency_keywords = ["ai agency", "automation agency", "ai automation", "digital agency"]
    for kw in ai_agency_keywords:
        if kw in bio:
            score -= 30
            reasons.append(f"AI agency penalty: '{kw}'")
            break

    score = max(0, min(100, score))
    if score >= 70: tier = "A"
    elif score >= 45: tier = "B"
    elif score >= 25: tier = "C"
    else: tier = "D"

    return {
        "financial_score": score,
        "financial_tier": tier,
        "financial_reasons": reasons,
        "financial_confidence": "low",
        "financial_breakdown": {},
    }


def score_financial_batch(members_with_enrichment: list) -> list:
    """
    Score a batch of members.

    Args:
        members_with_enrichment: List of dicts with 'member' and 'enrichment' keys

    Returns:
        Same list with financial score fields added to each item
    """
    results = []
    for item in members_with_enrichment:
        member = item.get("member", item)
        enrichment = item.get("enrichment", {})
        scores = score_financial(member, enrichment)
        result = {**member, **scores}
        results.append(result)
    return results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Financial Qualification Scorer v2")
    parser.add_argument("--input", required=True, help="Path to member JSON file")
    parser.add_argument("--enrichment", help="Path to enrichment JSON file (optional)")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        member = json.load(f)

    enrichment = {}
    if args.enrichment:
        with open(args.enrichment, "r") as f:
            enrichment = json.load(f)

    result = score_financial(member, enrichment)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
