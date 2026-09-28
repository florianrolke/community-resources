from __future__ import annotations

import os
import requests
from scripts.common import RotatingKeyClient, env_keys, load_env

RETRY_STATUS = {401, 402, 403, 429, 432}


class TavilySearch(RotatingKeyClient):
    def __init__(self, keys=None):
        super().__init__("Tavily", keys or env_keys("TAVILY_API_KEY", preferred=["5", "6", "4", "3", "2", ""]), 1.0)

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        if not self.available:
            return []
        while self.available:
            self.wait()
            response = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": self.key(), "query": query, "search_depth": "basic", "max_results": max_results, "include_answer": False},
                timeout=30,
            )
            if response.status_code == 200:
                return response.json().get("results", [])
            if response.status_code in RETRY_STATUS and self.mark_exhausted_and_rotate():
                continue
            return []
        return []


class ExaSearch(RotatingKeyClient):
    def __init__(self, keys=None):
        super().__init__("Exa", keys or env_keys("EXA_API_KEY", preferred=["5", "6", "4", "3", "2", ""]), 0.75)

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        if not self.available:
            return []
        while self.available:
            self.wait()
            response = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": self.key(), "Content-Type": "application/json"},
                json={"query": query, "type": "neural", "useAutoprompt": True, "numResults": max_results},
                timeout=30,
            )
            if response.status_code == 200:
                return response.json().get("results", [])
            if response.status_code in RETRY_STATUS and self.mark_exhausted_and_rotate():
                continue
            return []
        return []


def apify_run_sync(actor_id: str, payload: dict, token: str | None = None, dry_run: bool = False):
    load_env()
    token = token or next(iter(env_keys("APIFY_API_TOKEN", preferred=["5", "6", "4", "3", "2", ""])), "")
    if dry_run:
        return {"dry_run": True, "actor_id": actor_id, "payload": payload, "token_present": bool(token)}
    if not token:
        raise RuntimeError("No APIFY_API_TOKEN found")
    actor = actor_id.replace("/", "~")
    response = requests.post(
        f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
        params={"token": token},
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def apify_actor_from_alias(alias: str) -> str:
    load_env()
    mapping = {
        "google-serp": os.getenv("APIFY_GOOGLE_SERP_ACTOR", "scraperlink/google-search-results-serp-scraper"),
        "google-search": os.getenv("APIFY_GOOGLE_SEARCH_ACTOR", "apify/google-search-scraper"),
        "10times": os.getenv("APIFY_10TIMES_ACTOR", "zen-studio/10times-events-scraper"),
        "eventbrite": os.getenv("APIFY_EVENTBRITE_ACTOR", "santamaria-automations/eventbrite-scraper"),
        "meetup": "easyapi/meetup-events-scraper",
        "ticketmaster": "easyapi/ticketmaster-events-scraper",
        "facebook-events": "apify/facebook-events-scraper",
    }
    return mapping.get(alias, alias)