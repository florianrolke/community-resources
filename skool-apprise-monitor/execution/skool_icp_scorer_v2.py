"""
skool_icp_scorer_v2.py — Heroes Arc ICP Scorer (config-driven wrapper)

Wraps score_icp_match.py without modifying it.
Loads per-tenant ICP thresholds from tenant config.

Heroes Arc ICP dimensions (7 scoring dimensions):
  1. Position (owner/founder/CEO) — 25 pts
  2. US-based confirmed — 10 pts
  3. Traditional industry — 10 pts
  4. Revenue $1M-$100M — 10 pts
  5. Headcount 11-200 — 5 pts
  6. Owner age 50-70 — 10 pts
  7. Succession signals — 15 pts
  + Phase 3 additions: geographic priority, years in business, ad spend, faith-based, etc.

Score: 0-100 (normalized), Tier: A/B/C/D

Usage:
  python execution/skool_icp_scorer_v2.py --input .tmp/test_member.json
"""

import json
import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


def _prepare_icp_input(member: dict, enrichment: dict) -> tuple:
    """
    Convert member + enrichment into the format expected by score_icp_match.py.
    Returns (lead_dict, enrichment_dict) in the right schema.
    """
    # Lead dict format expected by score_icp_match.compute_icp_score
    lead = {
        "name": member.get("name", ""),
        "email": enrichment.get("email", ""),
        "total_messages": member.get("total_messages", 0),
        "unreplied": member.get("unreplied", 0),
        "position_category": _detect_position(member, enrichment),
        "heroes_arc_flags": _extract_heroes_arc_flags(member, enrichment),
        "bio": member.get("bio", ""),
        "linkedin_url": member.get("linkedin") or enrichment.get("linkedin_url", ""),
    }

    # Enrichment dict format
    enrich = {
        "location": {
            "city": enrichment.get("city") or enrichment.get("location", {}).get("city"),
            "country": enrichment.get("country") or enrichment.get("location", {}).get("country"),
        },
        "services": enrichment.get("services", []),
        "industries": enrichment.get("industries", []),
        "pain_signals": enrichment.get("pain_signals", []),
        "revenue_signals": enrichment.get("revenue_signals", ""),
        "employee_count": enrichment.get("employee_count", ""),
        "company_name": enrichment.get("company_name", ""),
        "website": enrichment.get("website", ""),
        "email": enrichment.get("email", ""),
        "confidence": enrichment.get("confidence", "low"),
        "years_in_business": enrichment.get("years_in_business", ""),
    }

    return lead, enrich


def _detect_position(member: dict, enrichment: dict) -> str:
    """Detect position category from bio + enrichment."""
    text = " ".join([
        member.get("bio", ""),
        enrichment.get("bio_summary", ""),
        enrichment.get("role_title", ""),
    ]).lower()

    if any(kw in text for kw in ["owner", "founder", "ceo", "president", "managing director", "principal"]):
        return "owner"
    if any(kw in text for kw in ["partner", "managing partner", "co-founder"]):
        return "partner"
    if any(kw in text for kw in ["vp", "vice president", "director", "head of", "c-suite", "cto", "coo", "cfo"]):
        return "executive"
    if any(kw in text for kw in ["manager", "lead", "senior"]):
        return "manager"
    return "unknown"


def _extract_heroes_arc_flags(member: dict, enrichment: dict) -> dict:
    """
    Extract Heroes Arc specific signals from bio + enrichment.
    Returns a dict (not list) — score_icp_match.py calls .get() on it.
    """
    flags: dict = {
        "warm": False,
        "unreplied": False,
    }
    text = " ".join([
        member.get("bio", ""),
        enrichment.get("bio_summary", ""),
        str(enrichment.get("pain_signals", [])),
    ]).lower()

    succession_keywords = [
        "succession", "exit", "selling business", "transition", "legacy",
        "retirement", "next chapter", "passing the torch", "acquisition"
    ]
    for kw in succession_keywords:
        if kw in text:
            flags[f"succession_signal_{kw.replace(' ', '_')}"] = True

    faith_keywords = ["faith", "christian", "church", "god", "values-based", "faith-based"]
    for kw in faith_keywords:
        if kw in text:
            flags[f"faith_based_{kw.replace('-', '_')}"] = True

    return flags


def score_heroes_arc_icp(member: dict, enrichment: dict, config: dict) -> dict:
    """
    Score a member against the Heroes Arc ICP.

    Args:
        member: Member dict (name, handle, bio, location, linkedin)
        enrichment: Enrichment dict from skool_enrichment_pipeline_v2
        config: Tenant config dict (for thresholds)

    Returns:
        {
          "icp_score": int (0-100),
          "icp_tier": str ("A"/"B"/"C"/"D"),
          "icp_reasons": list[str],
          "icp_breakdown": dict
        }
    """
    try:
        from score_icp_match import compute_icp_score, assign_tier

        lead, enrich = _prepare_icp_input(member, enrichment)
        weights = {}  # Use default weights from score_icp_match

        score, breakdown = compute_icp_score(lead, enrich, weights)
        tier = assign_tier(score)

        reasons = []
        for dim, pts in breakdown.items():
            if pts > 0:
                reasons.append(f"+{pts} {dim.replace('_', ' ')}")
            elif pts < 0:
                reasons.append(f"{pts} {dim.replace('_', ' ')}")

        return {
            "icp_score": score,
            "icp_tier": tier,
            "icp_reasons": reasons,
            "icp_breakdown": breakdown,
        }

    except (ImportError, Exception) as e:
        print(f"  ICP scorer error: {e}")
        return _fallback_icp_score(member, enrichment, config)


def _fallback_icp_score(member: dict, enrichment: dict, config: dict) -> dict:
    """Basic keyword ICP scoring when score_icp_match unavailable."""
    score = 0
    reasons = []
    text = " ".join([
        member.get("bio", ""),
        enrichment.get("bio_summary", ""),
        str(enrichment.get("services", [])),
        str(enrichment.get("industries", [])),
    ]).lower()

    if any(kw in text for kw in ["owner", "founder", "ceo"]):
        score += 25
        reasons.append("+25 business owner")

    country = str(enrichment.get("country", "") or enrichment.get("location", {}).get("country", "")).lower()
    if "united states" in country or "usa" in country or "us" == country:
        score += 10
        reasons.append("+10 US-based")

    traditional = ["manufacturing", "construction", "distribution", "logistics", "plumbing",
                   "hvac", "dental", "medical", "legal", "accounting", "landscaping"]
    for ind in traditional:
        if ind in text:
            score += 10
            reasons.append(f"+10 traditional industry: {ind}")
            break

    succession = ["succession", "exit", "retirement", "transition", "legacy"]
    for kw in succession:
        if kw in text:
            score += 15
            reasons.append(f"+15 succession signal: {kw}")
            break

    score = min(100, score)
    tier = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"

    return {
        "icp_score": score,
        "icp_tier": tier,
        "icp_reasons": reasons,
        "icp_breakdown": {},
    }


def score_all_members(members_enriched: list, config: dict) -> list:
    """
    Score a list of enriched members on both financial + ICP tracks.

    Args:
        members_enriched: List of enriched member dicts (from enrichment pipeline)
        config: Tenant config dict

    Returns:
        Same list with scoring fields added:
          - financial_score, financial_tier, financial_reasons
          - icp_score, icp_tier, icp_reasons
          - flag_financial_only, flag_icp_only, flag_both, flag_qualified
    """
    from skool_financial_scorer_v2 import score_financial

    fin_threshold = config["scoring"]["financial"]["threshold_alert"]
    icp_threshold = config["scoring"]["heroes_arc_icp"]["threshold_alert"]

    results = []
    for member in members_enriched:
        enrichment = member.get("enrichment", {})

        # Financial scoring
        fin = score_financial(member, enrichment)
        # ICP scoring
        icp = score_heroes_arc_icp(member, enrichment, config)

        fin_qualified = fin["financial_score"] >= fin_threshold
        icp_qualified = icp["icp_score"] >= icp_threshold

        scored = {
            **member,
            **fin,
            **icp,
            "flag_financial_only": fin_qualified and not icp_qualified,
            "flag_icp_only": icp_qualified and not fin_qualified,
            "flag_both": fin_qualified and icp_qualified,
            "flag_qualified": fin_qualified or icp_qualified,
        }
        results.append(scored)

    return results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="ICP Scorer v2")
    parser.add_argument("--input", required=True, help="Path to member JSON (may include enrichment)")
    parser.add_argument("--tenant", default="aiautomationsbyjack")
    args = parser.parse_args()

    tenant_dir = EXECUTION_DIR / "tenants" / args.tenant
    with open(tenant_dir / "config.json", "r") as f:
        config = json.load(f)

    with open(args.input, "r") as f:
        member = json.load(f)

    enrichment = member.get("enrichment", {})
    result = score_heroes_arc_icp(member, enrichment, config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
