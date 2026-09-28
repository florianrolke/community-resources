from __future__ import annotations

import argparse
import re
from scripts.common import LINKEDIN_FIELDS, ascii_norm, compact_text, first_value, read_csv, write_csv

PERSON_RE = re.compile(r"https?://(?:[a-z]{2}\.)?linkedin\.com/in/[A-Za-z0-9_%\-]+/?", re.I)
COMPANY_RE = re.compile(r"https?://(?:[a-z]{2}\.)?linkedin\.com/company/[A-Za-z0-9_.%\-]+/?", re.I)


def normalize_linkedin_url(url: str) -> str:
    url = (url or "").strip().split("?")[0].rstrip("/")
    url = re.sub(r"https?://[a-z]{2}\.linkedin\.com", "https://www.linkedin.com", url, flags=re.I)
    url = re.sub(r"https?://(?:www\.)?linkedin\.com", "https://www.linkedin.com", url, flags=re.I)
    return url


def extract_linkedin_urls(text: str, expected_type: str = "") -> list[str]:
    text = text or ""
    urls = PERSON_RE.findall(text) + COMPANY_RE.findall(text)
    if expected_type == "person":
        urls = [u for u in urls if "/in/" in u]
    if expected_type == "company":
        urls = [u for u in urls if "/company/" in u]
    return [normalize_linkedin_url(u) for u in urls]


def score_linkedin_match(name: str, company: str, expected_type: str, url: str, evidence: str) -> tuple[str, str]:
    haystack = ascii_norm(f"{url} {evidence}")
    name_parts = [p for p in ascii_norm(name).split() if len(p) > 2]
    company_norm = ascii_norm(company)
    url_type_ok = (expected_type == "company" and "/company/" in url) or (expected_type != "company" and "/in/" in url)
    name_hits = sum(1 for p in name_parts if p in haystack)
    company_hit = bool(company_norm and company_norm in haystack)
    if url_type_ok and expected_type == "company" and (company_hit or ascii_norm(name) in haystack):
        return "confirmed", "Company LinkedIn URL matches company evidence."
    if url_type_ok and name_parts and name_hits >= min(2, len(name_parts)) and company_hit:
        return "confirmed", "Person LinkedIn URL matches name and company evidence."
    if url_type_ok and name_parts and name_hits >= min(2, len(name_parts)):
        return "probable", "Person LinkedIn URL matches name but lacks strong company evidence."
    if url_type_ok and company_hit:
        return "probable", "LinkedIn URL matches company evidence but not enough person evidence."
    if url:
        return "weak", "LinkedIn URL found, but name/company evidence is incomplete."
    return "needs-manual-verification", "No LinkedIn URL found in supplied evidence."


def match_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        name = first_value(row, "name", "person_name", "company", "organization")
        company = first_value(row, "company", "organization")
        expected_type = first_value(row, "type", "expected_type") or ("company" if not first_value(row, "person_name", "name") and company else "person")
        supplied_url = first_value(row, "linkedin_url", "linkedin", "url")
        evidence = first_value(row, "evidence", "notes", "snippet", "description")
        urls = [normalize_linkedin_url(supplied_url)] if supplied_url else extract_linkedin_urls(evidence, expected_type)
        url = urls[0] if urls else ""
        confidence, notes = score_linkedin_match(name, company, expected_type, url, evidence)
        out.append({
            "name": name,
            "company": company,
            "type": expected_type,
            "linkedin_url": url,
            "match_confidence": confidence,
            "evidence": compact_text(evidence),
            "notes": notes,
        })
    return out


def main():
    parser = argparse.ArgumentParser(description="Normalize and score LinkedIn profile/page matches from evidence rows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_csv(args.output, match_rows(read_csv(args.input)), LINKEDIN_FIELDS)


if __name__ == "__main__":
    main()