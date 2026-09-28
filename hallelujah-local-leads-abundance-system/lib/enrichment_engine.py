"""
Waterfall Enrichment Engine

The core enrichment logic shared across all 4 pillars. Uses a waterfall pattern:
  Perplexity (deep research) -> Exa (LinkedIn/website) -> Tavily (fallback)

Each step tries the best source first, falls back to cheaper alternatives,
and handles rate limits + key rotation automatically.

Production stats:
- 92% LinkedIn hit rate on BNI leads
- 30-66% LinkedIn on chamber leads (depends on platform)
- ~$0.15 per lead fully enriched

Usage:
    from lib.enrichment_engine import EnrichmentEngine

    engine = EnrichmentEngine()  # reads API keys from .env

    # Find a company's website
    website = engine.find_website("Acme Corp", city="Austin")

    # Find LinkedIn profile
    linkedin = engine.find_linkedin("John Smith", "Acme Corp")

    # Full enrichment
    profile = engine.enrich_lead("Acme Corp", city="Austin")
"""

import json
import os
import re
import requests
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv

from lib.api_key_rotation import KeyRotator
from lib.linkedin_validator import extract_linkedin_url, validate_linkedin_for_person
from lib.rate_limiter import RateLimiter

load_dotenv()

# Domains to skip when finding company websites (these are aggregator sites, not company sites)
SKIP_DOMAINS = [
    "linkedin.com", "facebook.com", "yelp.com", "bbb.org",
    "yellowpages.com", "mapquest.com", "google.com",
    "chambermaster.com", "growthzone.com", "twitter.com",
    "instagram.com", "tiktok.com", "pinterest.com",
    "crunchbase.com", "glassdoor.com", "indeed.com",
    "nextdoor.com", "angi.com", "thumbtack.com",
]


class EnrichmentEngine:
    """Waterfall enrichment engine with API key rotation.

    Reads API keys from environment variables. Supports:
    - Exa (primary): EXA_API_KEY, EXA_API_KEY_2, ..., EXA_API_KEY_6
    - Tavily (fallback): TAVILY_API_KEY, ..., TAVILY_API_KEY_6
    - Perplexity (deep research): PERPLEXITY_API_KEY

    Args:
        exa_start: Which Exa key index to start with (default 0)
        tavily_start: Which Tavily key index to start with (default 0)
    """

    def __init__(self, exa_start: int = 0, tavily_start: int = 0):
        self.exa = KeyRotator("EXA_API_KEY", num_keys=6, start_index=exa_start)
        self.tavily = KeyRotator("TAVILY_API_KEY", num_keys=6, start_index=tavily_start)
        self.limiter = RateLimiter(delay=2.0, pause_every=10, pause_duration=15.0)

    def find_website(self, company_name: str, city: str = "") -> Optional[str]:
        """Find company website via Exa -> Tavily waterfall."""
        query = f"{company_name} {city} official website".strip()

        # Try Exa
        url = self._exa_search(query, filter_domains=True)
        if url:
            return url

        # Fallback: Tavily
        url = self._tavily_search(query, filter_domains=True)
        if url:
            return url

        return None

    def find_linkedin(self, person_name: str, company_name: str = "",
                      city: str = "") -> Optional[str]:
        """Find a person's LinkedIn profile via Exa -> Tavily waterfall.

        Validates that the found URL matches the person/company name.
        """
        query = f'"{person_name}" "{company_name}" site:linkedin.com/in/'.strip()
        if city:
            query += f" {city}"

        # Try Exa with LinkedIn domain filter
        exa_key = self.exa.get_key()
        if exa_key:
            self.limiter.wait()
            try:
                response = requests.post(
                    "https://api.exa.ai/search",
                    json={
                        "query": query,
                        "numResults": 5,
                        "type": "auto",
                        "includeDomains": ["linkedin.com"],
                    },
                    headers={"x-api-key": exa_key, "Content-Type": "application/json"},
                    timeout=15,
                )
                if response.status_code in (429, 432):
                    self.exa.mark_exhausted(exa_key)
                elif response.ok:
                    for r in response.json().get("results", []):
                        url = extract_linkedin_url(r.get("url", ""))
                        if url and validate_linkedin_for_person(url, person_name, company_name):
                            return url
            except Exception as e:
                print(f"    [WARN] Exa LinkedIn search failed: {e}")

        # Fallback: Tavily
        tavily_key = self.tavily.get_key()
        if tavily_key:
            self.limiter.wait()
            try:
                response = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 5,
                        "include_domains": ["linkedin.com"],
                    },
                    timeout=15,
                )
                if response.status_code in (429, 432):
                    self.tavily.mark_exhausted(tavily_key)
                elif response.ok:
                    for r in response.json().get("results", []):
                        url = extract_linkedin_url(r.get("url", ""))
                        if url and validate_linkedin_for_person(url, person_name, company_name):
                            return url
            except Exception as e:
                print(f"    [WARN] Tavily LinkedIn search failed: {e}")

        return None

    def research_company(self, company_name: str, website: str = "",
                         city: str = "") -> dict:
        """Deep research via Perplexity Sonar. Returns structured company data."""
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            return {}

        prompt = f"""Research this business: "{company_name}"
Location: {city or 'unknown'}
Website: {website or 'unknown'}

Return a JSON object with these fields (use null if unknown):
{{
  "description": "1-2 sentence description of what this business does",
  "industry": "primary industry/vertical",
  "estimated_size": "number of employees or size category",
  "years_in_business": "approximate years operating",
  "founders_owners": [
    {{"name": "Full Name", "role": "Owner/Founder/CEO", "linkedin_url": "if found"}}
  ],
  "notable_info": "any awards, recent news, or notable achievements"
}}

Return ONLY the JSON, no markdown formatting."""

        self.limiter.wait()
        try:
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 600,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if response.ok:
                content = response.json()["choices"][0]["message"]["content"]
                parsed = self._parse_json_response(content)
                if parsed:
                    parsed["source"] = "perplexity_sonar"
                    parsed["researched_at"] = datetime.now(timezone.utc).isoformat()
                    return parsed
                return {
                    "description": content[:500],
                    "source": "perplexity_sonar",
                    "researched_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            print(f"    [WARN] Perplexity research failed: {e}")

        return {}

    def enrich_lead(self, company_name: str, city: str = "",
                    person_name: str = "") -> dict:
        """Full enrichment pipeline for a single lead.

        Returns dict with: website, linkedin, company_research, decision_makers
        """
        result = {
            "company": company_name,
            "city": city,
            "website": None,
            "linkedin": None,
            "research": {},
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Step 1: Find website
        result["website"] = self.find_website(company_name, city)

        # Step 2: Research company (if Perplexity available)
        result["research"] = self.research_company(
            company_name, result["website"] or "", city
        )

        # Step 3: Find LinkedIn for decision maker
        if person_name:
            result["linkedin"] = self.find_linkedin(person_name, company_name, city)
        elif result["research"].get("founders_owners"):
            owners = result["research"]["founders_owners"]
            if owners and isinstance(owners, list) and owners[0].get("name"):
                owner_name = owners[0]["name"]
                # Check if Perplexity already found a LinkedIn
                li = owners[0].get("linkedin_url", "")
                if li and "linkedin.com/in/" in str(li):
                    result["linkedin"] = extract_linkedin_url(str(li))
                if not result["linkedin"]:
                    result["linkedin"] = self.find_linkedin(owner_name, company_name, city)

        return result

    def _exa_search(self, query: str, filter_domains: bool = False) -> Optional[str]:
        """Search Exa and return first valid URL."""
        exa_key = self.exa.get_key()
        if not exa_key:
            return None

        self.limiter.wait()
        try:
            response = requests.post(
                "https://api.exa.ai/search",
                json={"query": query, "numResults": 3, "type": "auto"},
                headers={"x-api-key": exa_key, "Content-Type": "application/json"},
                timeout=15,
            )
            if response.status_code in (429, 432):
                self.exa.mark_exhausted(exa_key)
                return None
            if response.ok:
                for r in response.json().get("results", []):
                    url = r.get("url", "")
                    if filter_domains:
                        domain = urlparse(url).netloc.lower()
                        if any(sd in domain for sd in SKIP_DOMAINS):
                            continue
                    return url
        except Exception as e:
            print(f"    [WARN] Exa search failed: {e}")
        return None

    def _tavily_search(self, query: str, filter_domains: bool = False) -> Optional[str]:
        """Search Tavily and return first valid URL."""
        tavily_key = self.tavily.get_key()
        if not tavily_key:
            return None

        self.limiter.wait()
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                },
                timeout=15,
            )
            if response.status_code in (429, 432):
                self.tavily.mark_exhausted(tavily_key)
                return None
            if response.ok:
                for r in response.json().get("results", []):
                    url = r.get("url", "")
                    if filter_domains:
                        domain = urlparse(url).netloc.lower()
                        if any(sd in domain for sd in SKIP_DOMAINS):
                            continue
                    return url
        except Exception as e:
            print(f"    [WARN] Tavily search failed: {e}")
        return None

    @staticmethod
    def _parse_json_response(text: str) -> Optional[dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return None
