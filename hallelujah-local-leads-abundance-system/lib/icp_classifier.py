"""
ICP (Ideal Customer Profile) Tier Classification

Classifies businesses into A/B/C/D tiers based on their category keywords.
Default keywords target professional services and high-value local businesses.
Customize by passing your own keyword dict.

Tiers:
  A = High-Value Services (consulting, financial, marketing, agencies, tech)
  B = Professional Services (legal, medical, architecture, engineering)
  C = Local Trades (roofing, plumbing, HVAC, contractors)
  D = Other (restaurants, retail, nonprofits, etc.)
"""

DEFAULT_ICP_KEYWORDS = {
    "A": {
        "label": "High-Value Services",
        "keywords": [
            "consulting", "financial", "insurance", "marketing", "agency",
            "accounting", "cpa", "real estate", "technology", "software",
            "it services", "business coach", "wealth management", "advisory",
            "mortgage", "tax", "digital marketing", "staffing", "recruiting",
            "media", "advertising", "investment", "venture", "capital",
            "saas", "ai", "artificial intelligence", "automation",
            "management consulting", "strategy", "private equity",
        ],
    },
    "B": {
        "label": "Professional Services",
        "keywords": [
            "law", "attorney", "legal", "medical", "dental", "chiropractic",
            "architecture", "engineering", "veterinary", "optometry",
            "physician", "therapist", "healthcare", "clinic", "surgery",
            "orthodont", "dermatolog", "psycholog", "psychiatr",
        ],
    },
    "C": {
        "label": "Local Trades",
        "keywords": [
            "roofing", "plumbing", "hvac", "electrician", "painting",
            "remodeling", "contractor", "landscaping", "flooring",
            "restoration", "cleaning", "pest control", "construction",
            "home improvement", "fence", "garage", "solar", "pool",
            "tree service", "moving", "storage", "demolition",
        ],
    },
}


def classify_business(category: str, custom_keywords: dict = None) -> tuple[str, str]:
    """Classify a business into ICP tiers based on category text.

    Args:
        category: The business category string (e.g., "Financial Services, Insurance")
        custom_keywords: Optional override for DEFAULT_ICP_KEYWORDS

    Returns:
        Tuple of (tier, label) e.g., ("A", "High-Value Services")
    """
    if not category:
        return "D", "Other"

    keywords = custom_keywords or DEFAULT_ICP_KEYWORDS
    cat_lower = category.lower()

    for tier in ["A", "B", "C"]:
        if tier in keywords:
            for kw in keywords[tier]["keywords"]:
                if kw in cat_lower:
                    return tier, keywords[tier]["label"]

    return "D", "Other"
