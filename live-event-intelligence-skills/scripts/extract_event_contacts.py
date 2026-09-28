from __future__ import annotations

import argparse
import re
from scripts.common import CONTACT_FIELDS, compact_text, first_value, read_csv, write_csv
from scripts.find_linkedin_profiles import extract_linkedin_urls

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")


def extract_contacts(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        text = " ".join(str(v or "") for v in row.values())
        names = [first_value(row, "person_name", "name", "speaker", "contact_name")]
        org = first_value(row, "organization", "company", "organizer")
        if not any(names) and not org:
            continue
        linkedin = "; ".join(extract_linkedin_urls(text))
        out.append({
            "person_name": names[0],
            "title": first_value(row, "title", "role", "contact_title"),
            "organization": org,
            "role_type": first_value(row, "role_type") or "event_contact",
            "event_name": first_value(row, "event_name", "event"),
            "segment": first_value(row, "segment", "category"),
            "email": "; ".join(sorted(set(EMAIL_RE.findall(text)))),
            "phone": "; ".join(sorted(set(PHONE_RE.findall(text)))),
            "linkedin_url": linkedin,
            "facebook_url": first_value(row, "facebook_url", "facebook"),
            "instagram_url": first_value(row, "instagram_url", "instagram"),
            "website": first_value(row, "website", "url", "source_url"),
            "source": first_value(row, "source") or "manual_extract",
            "confidence": first_value(row, "confidence") or ("probable" if linkedin else "needs-manual-verification"),
            "evidence": compact_text(text, 500),
            "next_action": first_value(row, "next_action") or "Review and verify before outreach",
        })
    return out


def main():
    parser = argparse.ArgumentParser(description="Extract event contact rows from a CSV with mixed event/contact evidence.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_csv(args.output, extract_contacts(read_csv(args.input)), CONTACT_FIELDS)


if __name__ == "__main__":
    main()