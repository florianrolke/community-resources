#!/usr/bin/env python3
"""
Financial Qualification Scorer - Rule-Based 7-Dimension Scoring

Scores members for financial qualification based on enrichment data.

Usage:
    from shared.financial_scorer import score_financial_qualification

    score, tier, breakdown = score_financial_qualification(member, enrichment)
"""

import re
from typing import Dict, Tuple, List


def score_financial_qualification(member: Dict, enrichment: Dict) -> Tuple[int, str, Dict]:
    """
    Score a member for financial qualification based on enrichment data.

    Scoring dimensions:
    1. Position/Authority (0-25): Are they the decision-maker?
    2. Business Signals (0-20): Revenue, employees, years in business
    3. Industry Match (0-15): Traditional/high-ticket industries
    4. Pain/Need Signals (0-15): Active business challenges
    5. Reachability (0-10): LinkedIn, website, email available
    6. Geographic Match (0-10): US-based (Chris's market)
    7. Anti-AI-Agency (0 or -50): Disqualify AI agencies

    Total: 0-95 normalized to 0-100

    Args:
        member: Member dict from Skool scrape
        enrichment: Enrichment dict from Perplexity

    Returns:
        (score, tier, breakdown) tuple
        - score: 0-100 normalized score
        - tier: 'A', 'B', 'C', or 'D'
        - breakdown: Dict with dimension scores and reasons
    """
    scores = {}
    reasons = []

    # Combine all text for keyword matching
    text = " ".join([
        enrichment.get("bio_summary", "") or "",
        enrichment.get("role_title", "") or "",
        enrichment.get("company_name", "") or "",
        " ".join(enrichment.get("services", []) or []),
        " ".join(enrichment.get("industries", []) or []),
        " ".join(enrichment.get("pain_signals", []) or []),
        enrichment.get("revenue_signals", "") or "",
        member.get("bio", "") or "",
    ]).lower()

    # === 1. Position/Authority (0-25) ===
    position_score = 0
    role = (enrichment.get("role_title", "") or "").lower()

    owner_kw = ["owner", "founder", "ceo", "co-founder", "president", "principal", "managing director"]
    exec_kw = ["cmo", "cto", "coo", "vp", "director", "partner", "head of"]
    biz_kw = ["consultant", "coach", "freelancer", "entrepreneur", "self-employed"]

    if any(kw in role or kw in text for kw in owner_kw):
        position_score = 25
        reasons.append(f"Owner/Founder ({role or 'from text'})")
    elif any(kw in role or kw in text for kw in exec_kw):
        position_score = 18
        reasons.append(f"Executive ({role or 'from text'})")
    elif any(kw in role or kw in text for kw in biz_kw):
        position_score = 12
        reasons.append(f"Business professional ({role or 'from text'})")

    scores["position"] = position_score

    # === 2. Business Signals (0-20) ===
    biz_score = 0
    rev = (enrichment.get("revenue_signals", "") or "").lower()
    emp = (enrichment.get("employee_count", "") or "").lower()
    years = enrichment.get("years_in_business", "")

    # Revenue signals
    if any(s in rev or s in text for s in ["million", "$1m", "$2m", "$5m", "$10m", "7 figure", "7-figure", "8 figure"]):
        biz_score += 10
        reasons.append("Revenue $1M+ signals")
    elif any(s in rev or s in text for s in ["six figure", "6 figure", "6-figure", "$100k", "$500k"]):
        biz_score += 6
        reasons.append("Revenue $100K+ signals")

    # Employee count
    if emp:
        try:
            count = int(re.search(r'(\d+)', str(emp)).group(1))
            if 11 <= count <= 200:
                biz_score += 5
                reasons.append(f"Team size: ~{count}")
            elif count > 200:
                biz_score += 3
                reasons.append(f"Large team: ~{count}")
        except (ValueError, AttributeError):
            pass

    # Years in business
    if years:
        try:
            y = int(re.search(r'(\d+)', str(years)).group(1))
            if y >= 15:
                biz_score += 5
                reasons.append(f"Established ({y}+ years)")
            elif y >= 5:
                biz_score += 3
                reasons.append(f"Experienced ({y}+ years)")
        except (ValueError, AttributeError):
            pass

    scores["business"] = min(biz_score, 20)

    # === 3. Industry Match (0-15) ===
    industry_score = 0

    traditional = ["construction", "plumbing", "hvac", "electrical", "roofing",
                   "manufacturing", "contractor", "real estate", "insurance",
                   "landscaping", "dental", "medical", "legal", "accounting",
                   "automotive", "auto repair", "auto body", "restoration", "cleaning"]

    high_ticket = ["saas", "agency", "consulting", "coaching", "finance",
                   "wealth", "investment", "b2b", "enterprise"]

    for kw in traditional:
        if kw in text:
            industry_score = 15
            reasons.append(f"Traditional industry: {kw}")
            break

    if industry_score == 0:
        for kw in high_ticket:
            if kw in text:
                industry_score = 8
                reasons.append(f"High-ticket industry: {kw}")
                break

    scores["industry"] = industry_score

    # === 4. Pain/Need Signals (0-15) ===
    pain_score = 0
    pain_signals = enrichment.get("pain_signals", []) or []

    pain_kw = ["scaling", "leads", "struggling", "need help", "looking for",
               "growth", "automate", "efficiency", "overwhelmed", "bottleneck",
               "hiring", "retention", "conversion", "revenue drop"]

    if pain_signals:
        pain_score += min(len(pain_signals) * 5, 10)
        reasons.append(f"Pain signals: {', '.join(pain_signals[:3])}")

    for kw in pain_kw:
        if kw in text:
            pain_score = min(pain_score + 5, 15)
            if not pain_signals:
                reasons.append(f"Pain keyword: {kw}")
            break

    scores["pain"] = min(pain_score, 15)

    # === 5. Reachability (0-10) ===
    reach_score = 0

    if enrichment.get("linkedin_url") or member.get("linkedin"):
        reach_score += 5
        reasons.append("Has LinkedIn")

    if enrichment.get("website") or member.get("website"):
        reach_score += 3
        reasons.append("Has website")

    if enrichment.get("contact_info") or member.get("email") or "email" in text:
        reach_score += 2
        reasons.append("Has email/contact")

    scores["reachability"] = min(reach_score, 10)

    # === 6. Geographic Match (0-10) ===
    geo_score = 0

    # Use Skool location as fallback (format: "city (country)")
    skool_loc = (member.get("location", "") or "").lower()
    country = (enrichment.get("country", "") or "").lower()
    city = (enrichment.get("city", "") or "").lower()

    if not country and skool_loc:
        # Parse "city (country)" format from Skool
        loc_match = re.search(r'\(([^)]+)\)', skool_loc)
        if loc_match:
            country = loc_match.group(1).strip()
            city = skool_loc.split('(')[0].strip()

    if any(c in country for c in ["united states", "usa", "america"]):
        geo_score = 10
        reasons.append(f"US-based ({city or 'unknown city'})")
        if any(c in city for c in ["new york", "los angeles", "miami", "dallas", "atlanta", "chicago"]):
            reasons.append("Priority city for Chris")
    elif any(c in country for c in ["canada", "united kingdom", "uk", "australia"]):
        geo_score = 6
        reasons.append(f"English-speaking ({country})")
    elif country:
        geo_score = 2
        reasons.append(f"International ({city}, {country})" if city else f"International ({country})")

    scores["geographic"] = geo_score

    # === 7. AI Agency Disqualifier ===
    ai_kw = ["ai agency", "ai automation agency", "ai consultant", "ai solutions",
              "prompt engineer", "chatgpt expert", "llm specialist", "ai integration agency"]

    is_ai_agency = any(kw in text for kw in ai_kw)
    if is_ai_agency:
        scores["ai_agency_penalty"] = -50
        reasons.append("AI AGENCY — Not ICP for Heroes Ark")

    # === TOTAL ===
    raw_score = sum(scores.values())
    normalized = max(0, min(100, int(raw_score * 100 / 95))) if raw_score > 0 else 0

    # Tier assignment
    if normalized >= 70:
        tier = "A"
    elif normalized >= 45:
        tier = "B"
    elif normalized >= 25:
        tier = "C"
    else:
        tier = "D"

    # AI agencies always Tier D
    if is_ai_agency:
        tier = "D"
        normalized = 0

    breakdown = {
        "total_score": normalized,
        "tier": tier,
        "dimension_scores": scores,
        "reasons": reasons,
        "confidence": enrichment.get("confidence", "low"),
    }

    return normalized, tier, breakdown


def get_tier_label(tier: str) -> str:
    """Get human-readable tier label."""
    labels = {
        'A': 'A (highly qualified)',
        'B': 'B (qualified)',
        'C': 'C (maybe qualified)',
        'D': 'D (low qualification)',
    }
    return labels.get(tier, 'Unknown')
