from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from scripts.common import first_value, read_csv


def generate_report(events: list[dict], contacts: list[dict] | None = None, title: str = "Live Event Intelligence Report") -> str:
    contacts = contacts or []
    lines = [f"# {title}", ""]
    lines.append(f"Events reviewed: {len(events)}")
    lines.append(f"Contacts reviewed: {len(contacts)}")
    lines.append("")
    if events:
        lines.append("## Priority Events")
        for event in events[:25]:
            name = first_value(event, "event_name", "name", "title")
            date = first_value(event, "date_start", "date")
            place = ", ".join(v for v in [first_value(event, "venue"), first_value(event, "city"), first_value(event, "state")] if v)
            url = first_value(event, "event_url", "url")
            confidence = first_value(event, "confidence")
            score = first_value(event, "opportunity_score")
            action = first_value(event, "recommended_action")
            ranking = f" | score {score} | {action}" if score or action else ""
            lines.append(f"- {name} | {date} | {place} | {confidence}{ranking} | {url}")
        lines.append("")
    if contacts:
        lines.append("## Contact Map")
        by_conf = Counter(first_value(c, "confidence") or "unknown" for c in contacts)
        lines.append("Confidence counts: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_conf.items())))
        lines.append("")
        for contact in contacts[:30]:
            name = first_value(contact, "person_name", "name")
            org = first_value(contact, "organization", "company")
            linkedin = first_value(contact, "linkedin_url")
            confidence = first_value(contact, "confidence", "match_confidence")
            lines.append(f"- {name} | {org} | {confidence} | {linkedin}")
        lines.append("")
    lines.append("## Source Notes")
    lines.append("Use official event and association pages as canonical. Treat snippets and gated app references as partial evidence.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate a concise Markdown event intelligence report.")
    parser.add_argument("--events", required=True)
    parser.add_argument("--contacts", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="Live Event Intelligence Report")
    args = parser.parse_args()
    events = read_csv(args.events)
    contacts = read_csv(args.contacts) if args.contacts else []
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(generate_report(events, contacts, args.title), encoding="utf-8")


if __name__ == "__main__":
    main()
