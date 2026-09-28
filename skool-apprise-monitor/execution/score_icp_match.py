#!/usr/bin/env python3
"""
Heroes Arc ICP Match Scoring - Phase 2b (Local, Zero API Cost)

Combines local categorization data + API enrichment data into
a final Heroes Arc ICP score (0-100) with Tier A/B/C/D assignment.

Usage:
    python execution/score_icp_match.py
    python execution/score_icp_match.py --weights custom_weights.json
    python execution/score_icp_match.py --input .tmp/heroes_arc_enriched.json
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent

# ============================================================================
# DEFAULT SCORING WEIGHTS
# ============================================================================

DEFAULT_WEIGHTS = {
    # Position signals (from categorization)
    "position_owner_founder_ceo": 25,

    # API-enriched signals
    "us_based_confirmed": 10,
    "traditional_industry": 10,
    "revenue_1m_to_100m": 10,
    "headcount_11_to_200": 5,
    "owner_age_50_70": 10,
    "succession_signals": 15,
    "low_tech_maturity": 5,
    "pain_signals_present": 10,  # Increased from 5 — pain intensity correlates with close speed

    # Message/relationship signals
    "has_messages": 10,
    "unreplied_by_florian": 15,
    "has_email": 5,

    # Enrichment quality
    "high_confidence_enrichment": 5,

    # NEW: Phase 3 scoring additions (2026-02-07)
    "years_in_business_15plus": 5,
    "years_in_business_10_14": 3,
    "geographic_priority": 3,       # NY, CA, FL — Chris's primary markets
    "ad_spend_keywords": 8,         # Already spending on marketing = 3-5x more likely to close
    "conversion_pain_keywords": 7,  # Lead volume + low conversion = Chris's exact pitch
    "high_ticket_industry": 5,      # $5K+ deal size makes ROI pitch work
    "faith_based_signals": 10,      # Christian faith = natural trust bridge for Chris + Florian
}

# Normalization base — fixed at 130 (the original core weights) so that
# the new Phase 3 signals (faith, ad spend, years, geo, etc.) act as
# ADDITIVE bonuses that push top leads above the baseline, rather than
# deflating everyone's score by expanding the denominator.
NORMALIZATION_BASE = 130


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def score_position(lead: dict, weights: dict) -> int:
    """Score based on position category."""
    category = lead.get("position_category", "")
    if category in ["owner_founder", "ceo_president", "self_employed"]:
        return weights.get("position_owner_founder_ceo", 25)
    return 0


def score_us_based(enrichment: dict, weights: dict) -> int:
    """Score based on US location confirmation."""
    is_us = enrichment.get("is_us_based")
    if is_us is True:
        return weights.get("us_based_confirmed", 10)

    # Also check location data
    location = enrichment.get("location", {})
    if location:
        country = str(location.get("country", "")).lower()
        state = str(location.get("state", "")).lower()
        if "united states" in country or "usa" in country or "us" in country:
            return weights.get("us_based_confirmed", 10)
        if state and len(state) == 2:
            return weights.get("us_based_confirmed", 10)

    return 0


def score_traditional_industry(enrichment: dict, weights: dict) -> int:
    """Score for traditional (non-tech) industry."""
    if enrichment.get("industry_traditional") is True:
        return weights.get("traditional_industry", 10)
    return 0


def score_revenue(enrichment: dict, weights: dict) -> int:
    """Score for revenue in the ICP range ($500K-$100M)."""
    revenue = str(enrichment.get("estimated_revenue", "")).lower()
    icp_ranges = ["$500k-1m", "$1-5m", "$5-20m", "$20-100m",
                  "1m", "5m", "20m", "million"]
    if any(r in revenue for r in icp_ranges):
        return weights.get("revenue_1m_to_100m", 10)
    return 0


def score_headcount(enrichment: dict, weights: dict) -> int:
    """Score for headcount in the ICP range (11-200)."""
    headcount = str(enrichment.get("estimated_headcount", "")).lower()
    if headcount in ["11-50", "51-200"]:
        return weights.get("headcount_11_to_200", 5)
    return 0


def score_owner_age(enrichment: dict, weights: dict) -> int:
    """Score for owner age in the ICP sweet spot (50-70)."""
    age = str(enrichment.get("owner_age_estimate", "")).lower()
    if age in ["50-60", "60-70"]:
        return weights.get("owner_age_50_70", 10)
    return 0


def score_succession(enrichment: dict, weights: dict) -> int:
    """Score for succession/retirement signals."""
    signals = enrichment.get("succession_signals")
    if signals and isinstance(signals, str) and signals.lower() not in ["null", "none", ""]:
        return weights.get("succession_signals", 15)
    return 0


def score_tech_maturity(enrichment: dict, weights: dict) -> int:
    """Score for low technology maturity (high-value ICP)."""
    maturity = str(enrichment.get("technology_maturity", "")).lower()
    if maturity == "low":
        return weights.get("low_tech_maturity", 5)
    return 0


def score_pain_signals(enrichment: dict, weights: dict) -> int:
    """Score for having pain signals identified."""
    pains = enrichment.get("pain_signals", [])
    if isinstance(pains, list) and len(pains) > 0:
        return weights.get("pain_signals_present", 5)
    return 0


def score_messages(lead: dict, weights: dict) -> int:
    """Score for message history."""
    score = 0
    if lead.get("heroes_arc_flags", {}).get("warm") or lead.get("total_messages", 0) > 0:
        score += weights.get("has_messages", 10)
    if lead.get("unreplied") or lead.get("heroes_arc_flags", {}).get("unreplied"):
        score += weights.get("unreplied_by_florian", 15)
    return score


def score_email(lead: dict, enrichment: dict, weights: dict) -> int:
    """Score for having email address."""
    lead_email = lead.get("email", "")
    enrichment_email = enrichment.get("email")
    if (lead_email and "@" in str(lead_email)) or (enrichment_email and "@" in str(enrichment_email)):
        return weights.get("has_email", 5)
    return 0


def score_enrichment_quality(enrichment: dict, weights: dict) -> int:
    """Score for high-confidence enrichment."""
    if enrichment.get("confidence") == "high":
        return weights.get("high_confidence_enrichment", 5)
    return 0


def score_years_in_business(enrichment: dict, weights: dict) -> int:
    """Score for years in business — longer = more likely near retirement + larger database."""
    yib = enrichment.get("years_in_business")
    if yib is None:
        return 0
    try:
        yib = int(yib)
    except (ValueError, TypeError):
        return 0
    if yib >= 15:
        return weights.get("years_in_business_15plus", 5)
    elif yib >= 10:
        return weights.get("years_in_business_10_14", 3)
    return 0


def score_geographic_priority(enrichment: dict, weights: dict) -> int:
    """Score bonus for leads in Chris's primary markets (NY, CA, FL)."""
    priority_states = {
        "new york", "california", "florida",
        "ny", "ca", "fl"
    }
    location = enrichment.get("location", {})
    if not location:
        return 0
    state = str(location.get("state", "")).lower().strip()
    if state in priority_states:
        return weights.get("geographic_priority", 3)
    return 0


def score_ad_spend_keywords(enrichment: dict, weights: dict) -> int:
    """Score for ad spend / marketing budget signals in enrichment text."""
    ad_keywords = [
        "google ads", "facebook ads", "ad spend", "advertising",
        "marketing budget", "ppc", "pay per click", "seo",
        "digital marketing", "lead generation", "monthly ad",
        "marketing spend", "answering service", "call center"
    ]
    text = _get_searchable_text(enrichment)
    for kw in ad_keywords:
        if kw in text:
            return weights.get("ad_spend_keywords", 8)
    return 0


def score_conversion_pain_keywords(enrichment: dict, weights: dict) -> int:
    """Score for lead conversion pain — Chris's exact pitch."""
    conversion_keywords = [
        "conversion", "response time", "close rate", "contact rate",
        "follow up", "follow-up", "lost leads", "cold leads",
        "never contacted", "slow response", "missed calls",
        "voicemail", "unreturned", "lead management", "crm"
    ]
    text = _get_searchable_text(enrichment)
    for kw in conversion_keywords:
        if kw in text:
            return weights.get("conversion_pain_keywords", 7)
    return 0


def score_high_ticket_industry(enrichment: dict, weights: dict) -> int:
    """Score bonus for high-ticket industries where AI lead processing has outsized ROI."""
    high_ticket = [
        "construction", "real estate", "mobile home", "hvac",
        "dental", "legal", "law", "attorney", "insurance",
        "roofing", "plumbing", "medical", "chiropractic",
        "funeral", "mortuary", "property"
    ]
    industry = str(enrichment.get("industry", "")).lower()
    company_desc = str(enrichment.get("company_description", "")).lower()
    combined = industry + " " + company_desc
    for ht in high_ticket:
        if ht in combined:
            return weights.get("high_ticket_industry", 5)
    return 0


def score_faith_based(enrichment: dict, lead: dict, weights: dict) -> int:
    """Score for Christian faith-based signals — natural trust bridge for Chris + Florian."""
    faith_keywords = [
        "christian", "faith", "church", "ministry", "god",
        "blessed", "prayer", "servant leader", "stewardship",
        "blessings", "kingdom", "biblical", "scripture",
        "pastor", "chaplain", "deacon", "c12", "cbmc",
        "faith driven", "marketplace leader"
    ]
    # Search enrichment text
    text = _get_searchable_text(enrichment)
    # Also check position and company from lead
    position = str(lead.get("position", "")).lower()
    company = str(lead.get("company", "")).lower()
    combined = text + " " + position + " " + company
    for kw in faith_keywords:
        if kw in combined:
            return weights.get("faith_based_signals", 10)
    return 0


def _get_searchable_text(enrichment: dict) -> str:
    """Combine all text fields from enrichment for keyword searching."""
    parts = []
    for field in ["ai_summary", "company_description", "recent_news"]:
        val = enrichment.get(field)
        if val and isinstance(val, str):
            parts.append(val.lower())
    # Also include pain_signals list
    pains = enrichment.get("pain_signals", [])
    if isinstance(pains, list):
        for p in pains:
            if isinstance(p, str):
                parts.append(p.lower())
    return " ".join(parts)


def compute_icp_score(lead: dict, enrichment: dict, weights: dict) -> tuple:
    """Compute the full ICP score. Returns (normalized_score, breakdown)."""
    breakdown = {
        "position": score_position(lead, weights),
        "us_based": score_us_based(enrichment, weights),
        "traditional_industry": score_traditional_industry(enrichment, weights),
        "revenue": score_revenue(enrichment, weights),
        "headcount": score_headcount(enrichment, weights),
        "owner_age": score_owner_age(enrichment, weights),
        "succession_signals": score_succession(enrichment, weights),
        "low_tech_maturity": score_tech_maturity(enrichment, weights),
        "pain_signals": score_pain_signals(enrichment, weights),
        "messages": score_messages(lead, weights),
        "has_email": score_email(lead, enrichment, weights),
        "enrichment_quality": score_enrichment_quality(enrichment, weights),
        # Phase 3 additions (2026-02-07)
        "years_in_business": score_years_in_business(enrichment, weights),
        "geographic_priority": score_geographic_priority(enrichment, weights),
        "ad_spend_keywords": score_ad_spend_keywords(enrichment, weights),
        "conversion_pain": score_conversion_pain_keywords(enrichment, weights),
        "high_ticket_industry": score_high_ticket_industry(enrichment, weights),
        "faith_based": score_faith_based(enrichment, lead, weights),
    }

    raw_score = sum(breakdown.values())
    # Use fixed base so new signals are additive bonuses, not score diluters
    normalized = round((raw_score / NORMALIZATION_BASE) * 100)
    normalized = min(100, max(0, normalized))

    return normalized, breakdown


def assign_tier(score: int) -> str:
    """Assign final tier letter."""
    if score >= 80:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 40:
        return "C"
    else:
        return "D"


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Heroes Arc ICP Scoring")
    parser.add_argument("--input", "-i",
                        default=str(BASE_DIR / ".tmp" / "heroes_arc_enriched.json"),
                        help="Input enriched leads JSON")
    parser.add_argument("--output", "-o",
                        default=str(BASE_DIR / ".tmp" / "heroes_arc_scored.json"),
                        help="Output scored leads JSON")
    parser.add_argument("--csv-out",
                        default=str(BASE_DIR / ".tmp" / "heroes_arc_scored.csv"),
                        help="Output summary CSV")
    parser.add_argument("--weights", "-w",
                        default=None,
                        help="Custom weights JSON file (optional)")

    args = parser.parse_args()

    print("=" * 60)
    print("HEROES ARC ICP SCORING")
    print("=" * 60)

    # Load weights
    weights = DEFAULT_WEIGHTS.copy()
    if args.weights:
        with open(args.weights, "r", encoding="utf-8") as f:
            custom = json.load(f)
        weights.update(custom)
        print(f"Loaded custom weights from: {args.weights}")

    # Load enriched leads
    print(f"\nLoading: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    enriched_leads = data.get("leads", data if isinstance(data, list) else [])
    print(f"Loaded {len(enriched_leads)} enriched leads")

    # Score all leads
    scored = []
    for entry in enriched_leads:
        lead = entry.get("lead", entry)
        enrichment = entry.get("enrichment", {})

        icp_score, breakdown = compute_icp_score(lead, enrichment, weights)
        final_tier = assign_tier(icp_score)

        # Merge email from enrichment if lead doesn't have one
        best_email = lead.get("email", "")
        if not best_email or "@" not in str(best_email):
            best_email = enrichment.get("email") or ""

        scored_lead = {
            "full_name": lead.get("full_name", ""),
            "first_name": lead.get("first_name", ""),
            "last_name": lead.get("last_name", ""),
            "linkedin_url": lead.get("linkedin_url", ""),
            "email": best_email,
            "company": lead.get("company", ""),
            "position": lead.get("position", ""),
            "icp_score": icp_score,
            "icp_tier": final_tier,
            "score_breakdown": breakdown,
            "categorization_score": lead.get("score", 0),
            "categorization_tier": lead.get("tier", None),
            "position_category": lead.get("position_category", ""),
            # Enrichment data
            "location": enrichment.get("location", {}),
            "is_us_based": enrichment.get("is_us_based"),
            "industry": enrichment.get("industry"),
            "industry_traditional": enrichment.get("industry_traditional"),
            "estimated_headcount": enrichment.get("estimated_headcount"),
            "estimated_revenue": enrichment.get("estimated_revenue"),
            "years_in_business": enrichment.get("years_in_business"),
            "owner_age_estimate": enrichment.get("owner_age_estimate"),
            "succession_signals": enrichment.get("succession_signals"),
            "technology_maturity": enrichment.get("technology_maturity"),
            "pain_signals": enrichment.get("pain_signals", []),
            "company_website": enrichment.get("company_website"),
            "company_description": enrichment.get("company_description"),
            "phone": enrichment.get("phone"),
            "recent_news": enrichment.get("recent_news"),
            "ai_summary": enrichment.get("ai_summary"),
            # Message data
            "total_messages": lead.get("total_messages", 0),
            "unreplied": lead.get("unreplied", False),
            "enrichment_confidence": enrichment.get("confidence", "none"),
            "sources_used": enrichment.get("sources_used", []),
        }

        scored.append(scored_lead)

    # Sort by ICP score descending
    scored.sort(key=lambda x: (-x["icp_score"], -x.get("total_messages", 0)))

    # Statistics
    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for s in scored:
        tier_counts[s["icp_tier"]] = tier_counts.get(s["icp_tier"], 0) + 1

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"\nTotal scored: {len(scored)}")
    print(f"\nICP Tier Distribution:")
    print(f"  Tier A (80-100): {tier_counts['A']:>4} leads  - Perfect ICP match")
    print(f"  Tier B (60-79):  {tier_counts['B']:>4} leads  - Strong match")
    print(f"  Tier C (40-59):  {tier_counts['C']:>4} leads  - Possible match")
    print(f"  Tier D (0-39):   {tier_counts['D']:>4} leads  - Not ICP")

    # Top leads
    print(f"\n{'='*60}")
    print("TOP 20 ICP MATCHES")
    print(f"{'='*60}")
    for i, s in enumerate(scored[:20], 1):
        flags = []
        if s.get("unreplied"):
            flags.append("UNREPLIED")
        if s.get("is_us_based"):
            flags.append("US")
        if s.get("industry_traditional"):
            flags.append("TRAD")
        if s.get("succession_signals"):
            flags.append("SUCCESSION")
        if s.get("owner_age_estimate") in ["50-60", "60-70"]:
            flags.append(f"AGE:{s['owner_age_estimate']}")
        flag_str = " [" + ", ".join(flags) + "]" if flags else ""

        print(f"  {i:2d}. [T{s['icp_tier']} {s['icp_score']:3d}] {s['full_name']:<28s} | {s['position'][:25]:<25s} | {s['company'][:20]:<20s}{flag_str}")

    # Save JSON
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "source": args.input,
        "weights_used": weights,
        "total_scored": len(scored),
        "tier_distribution": tier_counts,
        "leads": scored,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved JSON: {args.output}")

    # Save CSV
    csv_fields = [
        "icp_score", "icp_tier", "full_name", "position", "company",
        "email", "is_us_based", "industry", "industry_traditional",
        "estimated_revenue", "estimated_headcount", "owner_age_estimate",
        "succession_signals", "technology_maturity",
        "total_messages", "unreplied", "enrichment_confidence",
        "company_website", "linkedin_url",
    ]
    with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for s in scored:
            row = {k: s.get(k, "") for k in csv_fields}
            # Flatten lists
            if isinstance(row.get("pain_signals"), list):
                row["pain_signals"] = "; ".join(row["pain_signals"])
            writer.writerow(row)
    print(f"Saved CSV: {args.csv_out}")

    print(f"\nDone at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
