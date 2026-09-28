"""
LinkedIn URL Extraction and Validation

Extracts LinkedIn profile URLs from text, normalizes them, and validates
that they match the expected person/company.

Key lessons learned from production:
1. ALWAYS validate URLs — search APIs return false positives frequently
2. Check name tokens appear in the slug (e.g., "john-smith-123abc")
3. Filter out generic slugs like "example", "profile", "company"
4. LinkedIn company pages (linkedin.com/company/) are different from personal profiles (/in/)
5. Chamber websites often have their OWN LinkedIn in headers/footers — filter these out

Usage:
    from lib.linkedin_validator import extract_linkedin_url, validate_linkedin_for_person

    url = extract_linkedin_url("Check out https://linkedin.com/in/john-smith-123")
    # Returns: "https://www.linkedin.com/in/john-smith-123"

    is_valid = validate_linkedin_for_person(url, "John Smith", "Acme Corp")
    # Returns: True (because "john" and "smith" appear in the slug)
"""

import re
from typing import Optional
from urllib.parse import unquote


# Matches LinkedIn personal profile URLs
LINKEDIN_PROFILE_RE = re.compile(
    r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)',
    re.IGNORECASE
)

# Matches LinkedIn company page URLs
LINKEDIN_COMPANY_RE = re.compile(
    r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([a-zA-Z0-9\-_%]+)',
    re.IGNORECASE
)

# Slugs that indicate a template/placeholder URL, not a real profile
GENERIC_SLUGS = {
    "example", "username", "yourname", "profile", "dir", "company",
    "school", "pub", "in", "feed", "jobs", "learning", "null",
    "undefined", "test", "user", "default",
}


def extract_linkedin_url(text: str, url_type: str = "profile") -> Optional[str]:
    """Extract and normalize a LinkedIn URL from text.

    Args:
        text: Text containing a LinkedIn URL
        url_type: "profile" for /in/ URLs, "company" for /company/ URLs

    Returns:
        Normalized LinkedIn URL or None
    """
    if not text:
        return None

    pattern = LINKEDIN_PROFILE_RE if url_type == "profile" else LINKEDIN_COMPANY_RE
    match = pattern.search(str(text))
    if not match:
        return None

    slug = match.group(1).lower().rstrip("/")
    slug = unquote(slug)

    if slug in GENERIC_SLUGS or len(slug) < 3:
        return None

    prefix = "in" if url_type == "profile" else "company"
    return f"https://www.linkedin.com/{prefix}/{slug}"


def validate_linkedin_for_person(url: str, person_name: str,
                                  company_name: str = "") -> bool:
    """Validate that a LinkedIn URL plausibly belongs to the given person/company.

    Checks if name tokens appear in the URL slug. This catches false positives
    where a search API returns an unrelated person's profile.

    Args:
        url: LinkedIn URL to validate
        person_name: Expected person's full name
        company_name: Optional company name for additional matching

    Returns:
        True if the URL plausibly matches the person/company
    """
    if not url:
        return False

    match = LINKEDIN_PROFILE_RE.search(url)
    if not match:
        match = LINKEDIN_COMPANY_RE.search(url)
    if not match:
        return False

    slug = unquote(match.group(1)).lower().replace("-", " ").replace("_", " ")

    # Check person name tokens in slug
    name_parts = [p.lower() for p in person_name.split() if len(p) > 2]
    if name_parts:
        matches = sum(1 for part in name_parts if part in slug)
        if matches >= 1:
            return True

    # Check company name tokens in slug
    if company_name:
        company_parts = [p.lower() for p in company_name.split() if len(p) > 2]
        if company_parts:
            matches = sum(1 for part in company_parts if part in slug)
            if matches >= 1:
                return True

    return False


def is_chamber_linkedin(url: str, chamber_patterns: list[str] = None) -> bool:
    """Check if a LinkedIn URL belongs to the chamber itself (not a member).

    Chamber websites often include their own LinkedIn in headers/footers.
    If this URL is scraped from a member's detail page, it's pollution.

    Args:
        url: LinkedIn URL to check
        chamber_patterns: List of substrings that indicate a chamber's own LinkedIn
                         (e.g., ["kcchamber", "opchamber", "mrcc"])
    """
    if not url or not chamber_patterns:
        return False
    url_lower = url.lower()
    return any(p.lower() in url_lower for p in chamber_patterns)
