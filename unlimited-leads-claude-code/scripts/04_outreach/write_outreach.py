#!/usr/bin/env python3
"""
Write the cold email and the LinkedIn connection request for each researched lead.

This is the payoff script, and it's where the repo makes its argument.

The course's best idea is that AI should write as little as possible. The email
template is fixed — you wrote it, you tested it, it works. The only thing the
model is allowed to produce is one line: the observation about *this* company
that proves you didn't mass-send. Everything else is your copy, unchanged, every
time. Jack called this determinism vs probabilism. It's right, and it's the
reason a 5-email sequence built this way holds up.

The n8n version asked for that discipline in the prompt. This one enforces it in
code. The prompts below are Jack's, word for word (prompts/subject_and_opener.md
and prompts/linkedin_request.md) — they instruct the model to keep the subject
under 11 words, start the body with "I noticed", skip congratulations, and keep
the connection request under 200 characters. A prompt can ask. Only an assert
can guarantee:

    subject must start with "Quick question about {Company}'s"
    subject <= 11 words
    body must start with "I noticed {Company} recently"
    body <= 15 words
    no "Congratulations" / "Congrats" / "amazing" / "great work"
    no dates, no quoted event names
    connection request <= 200 characters, none of the banned filler phrases

Anything that fails gets one retry with the specific failure fed back. Still
failing after that, the lead is flagged rather than shipped. You will never send
a 14-word subject line by accident.

Usage:
    python -X utf8 scripts/04_outreach/write_outreach.py \\
        --input output/researched.json \\
        --out-csv output/outreach.csv \\
        --sender-name "Armin Willis" \\
        --pain "leads going cold because nobody follows up past email one" \\
        --similar-company "a 12-truck HVAC company in Mobile" \\
        --metric "31 extra booked jobs in 60 days"

Cost: about $0.005 per lead.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.env import load_env, get
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import read_any, write_json, write_csv
from scripts.lib.claude import structured, load_prompt, DEFAULT_MODEL

fix_encoding()
load_env()

SUBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
    "additionalProperties": False,
}

LINKEDIN_SCHEMA = {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
    "additionalProperties": False,
}

BANNED_IN_BODY = ["congratulations", "congrats", "amazing", "great work", "impressive", "well done"]
BANNED_IN_LINKEDIN = ["building my network", "expanding my network", "grow my network",
                      "also working in", "i'd love to connect and learn"]

# The n8n `CustomEmail` field, made explicit. Edit this file, not the code.
DEFAULT_TEMPLATE = "templates/email_template.md"


# ----------------------------------------------------------------------------
# Validators. This is the part the canvas couldn't do.
# ----------------------------------------------------------------------------

def check_subject(subject: str, company: str) -> str | None:
    """Return an error string, or None if the subject is good."""
    if not subject.strip():
        return "Subject is empty."
    expected = f"Quick question about {company}'s"
    if not subject.lower().startswith(expected.lower()[:28]):
        return f'Subject must start with "{expected}". You wrote: "{subject}"'
    words = len(subject.split())
    if words > 11:
        return f"Subject is {words} words; the limit is 11. You wrote: \"{subject}\""
    return None


def check_body(body: str, company: str) -> str | None:
    """Return an error string, or None if the opener is good."""
    if not body.strip():
        return "Body is empty."
    low = body.lower()
    if not (low.startswith("i noticed") or low.startswith("saw that") or low.startswith("i saw")):
        return f'Body must start with "I noticed {company} recently ...". You wrote: "{body}"'
    words = len(body.split())
    if words > 15:
        return f"Body is {words} words; the limit is 15. You wrote: \"{body}\""
    for phrase in BANNED_IN_BODY:
        if phrase in low:
            return f'Remove "{phrase}" — no congratulating, no flattery. You wrote: "{body}"'
    if re.search(r"\b(19|20)\d{2}\b", body):
        return f'Remove the year — dates make it read like a mail merge. You wrote: "{body}"'
    if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", low):
        return f'Remove the month. You wrote: "{body}"'
    if '"' in body or "“" in body:
        return f"Remove the quotation marks around the event name. You wrote: \"{body}\""
    return None


def check_linkedin(message: str) -> str | None:
    """Return an error string, or None if the connection request is good."""
    if not message.strip():
        return "Message is empty."
    msg = message.strip()
    if len(msg) > 200:
        return f"Message is {len(msg)} characters; LinkedIn's limit is 200. You wrote: \"{msg}\""
    low = msg.lower()
    for phrase in BANNED_IN_LINKEDIN:
        if phrase in low:
            return f'Remove "{phrase}" — it is the exact filler everyone else sends. You wrote: "{msg}"'
    return None


# ----------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------

def facts_block(lead: dict) -> str:
    """The user-message shape from the n8n node: fact then source, five times."""
    parts = []
    for i in range(1, 6):
        fact = (lead.get(f"fact{i}") or "").strip()
        if not fact:
            continue
        source = (lead.get(f"explanation{i}") or "").strip()
        parts.append(f"{fact}\n{source}" if source else fact)
    return "\n\n".join(parts)


def _generate(system: str, user: str, schema: dict, validator, model: str, retries: int = 1):
    """Generate, validate, and retry once with the specific failure fed back."""
    attempt_user = user
    last_error = None

    for _ in range(retries + 1):
        result = structured(system=system, user=attempt_user, schema=schema, model=model, max_tokens=1024)
        error = validator(result)
        if error is None:
            return result, None
        last_error = error
        attempt_user = (
            f"{user}\n\n"
            f"Your previous attempt was rejected: {error}\n"
            f"Fix exactly that and return the corrected version."
        )

    return result, last_error


def write_for_lead(lead: dict, args, template: str, model: str) -> dict:
    company = lead.get("company") or lead.get("business_name") or ""
    first = lead.get("first_name") or (lead.get("name") or "").split(" ")[0] or "there"
    full_name = lead.get("name") or f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()

    out = dict(lead)

    if lead.get("needs_research") or not facts_block(lead):
        # No trigger event means no honest opener. Say so; don't invent one.
        out.update({
            "EmailSubject": "", "CustomEmail": "", "LinkedIN Req": "",
            "outreach_status": "skipped: no research facts",
        })
        return out

    # --- subject + opener -----------------------------------------------
    sys_subject, _ = load_prompt("subject_and_opener")
    user_subject = f"Company name: {company}\n\n{facts_block(lead)}"

    result, err = _generate(
        sys_subject, user_subject, SUBJECT_SCHEMA,
        lambda r: check_subject(r.get("subject", ""), company) or check_body(r.get("body", ""), company),
        model,
    )
    subject = result.get("subject", "").strip()
    opener = result.get("body", "").strip()

    # --- assemble the email: 100% deterministic, zero AI ------------------
    email = template.format(
        first_name=first,
        opener=opener,
        pain_point=args.pain,
        similar_company=args.similar_company,
        metric=args.metric,
        company=company,
        sender_name=args.sender_name,
    )

    # --- LinkedIn connection request -------------------------------------
    linkedin_msg, li_err = "", None
    if not args.no_linkedin:
        sys_li, _ = load_prompt("linkedin_request")
        user_li = (
            f"Company name: {company}\n"
            f"Prospects name: {full_name}\n\n"
            f"What I know about them:\n{facts_block(lead)}"
        )
        li_result, li_err = _generate(
            sys_li, user_li, LINKEDIN_SCHEMA,
            lambda r: check_linkedin(r.get("message", "")), model,
        )
        linkedin_msg = li_result.get("message", "").strip()

    status = "ok"
    if err:
        status = f"email failed validation: {err[:90]}"
    elif li_err:
        status = f"linkedin failed validation: {li_err[:90]}"

    out.update({
        "EmailSubject": subject if not err else "",
        "EmailOpener": opener if not err else "",
        "CustomEmail": email if not err else "",
        "LinkedIN Req": linkedin_msg if not li_err else "",
        "outreach_status": status,
    })
    return out


# The column order from the n8n Google Sheet, so the output looks familiar.
COLUMNS = [
    "first_name", "last_name", "email", "job_title", "linkedin", "company",
    "company_website", "location", "headline", "company_description",
    "fact1", "fact2", "fact3", "fact4", "fact5",
    "explanation1", "explanation2", "explanation3", "explanation4", "explanation5",
    "EmailSubject", "EmailOpener", "CustomEmail", "LinkedIN Req", "outreach_status",
]


def main():
    parser = argparse.ArgumentParser(
        description="Write cold emails + LinkedIn requests from researched leads (System 1, step 3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The four --pain / --similar-company / --metric / --sender-name values are YOUR
copy. They go into every email unchanged. Write them once, well.

Edit templates/email_template.md to change the email itself — no code changes.
        """,
    )
    parser.add_argument("--input", required=True, help="Researched leads JSON or CSV")
    parser.add_argument("--output", help="Output JSON (default: <input>_outreach.json)")
    parser.add_argument("--out-csv", dest="out_csv", help="Also write a CSV here")
    parser.add_argument("--sender-name", dest="sender_name",
                        default=get("OUTREACH_SENDER_NAME") or "",
                        help="Your name, signed at the bottom (or set OUTREACH_SENDER_NAME in .env)")
    parser.add_argument("--pain", default="leads going cold because nobody follows up past the first email",
                        help="The bottleneck your prospects have")
    parser.add_argument("--similar-company", dest="similar_company", default="a similar company",
                        help="A comparable client you helped (social proof)")
    parser.add_argument("--metric", default="a measurable lift",
                        help="The result you got them, e.g. '31 extra booked jobs'")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help=f"Email template (default: {DEFAULT_TEMPLATE})")
    parser.add_argument("--no-linkedin", dest="no_linkedin", action="store_true",
                        help="Skip the LinkedIn connection requests")
    parser.add_argument("--limit", type=int, help="Only process the first N leads")
    parser.add_argument("--workers", type=int, default=3, help="Parallel leads (default: 3)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Write one lead and print it, so you can check the copy before spending")
    args = parser.parse_args()

    if not args.sender_name:
        print("Error: --sender-name is required (or set OUTREACH_SENDER_NAME in .env)", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(__file__).resolve().parents[2]
    template_path = Path(args.template)
    if not template_path.is_absolute():
        template_path = repo_root / template_path
    if not template_path.exists():
        print(f"Error: template not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    template = template_path.read_text(encoding="utf-8")

    leads = read_any(args.input)
    if args.dry_run:
        leads = leads[:1]
    elif args.limit:
        leads = leads[:args.limit]

    print(f"Writing outreach for {len(leads)} leads...")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(write_for_lead, l, args, template, args.model): l for l in leads}
        for i, fut in enumerate(as_completed(futures), 1):
            lead = futures[fut]
            label = (lead.get("company") or lead.get("name") or "?")[:38]
            try:
                r = fut.result()
                results.append(r)
                mark = "ok" if r["outreach_status"] == "ok" else r["outreach_status"][:52]
                print(f"  [{i}/{len(leads)}] {label} — {mark}")
            except Exception as e:
                print(f"  [{i}/{len(leads)}] {label} — FAILED: {e}")
                results.append({**lead, "outreach_status": f"error: {e}"})

    if args.dry_run:
        r = results[0]
        print("\n" + "=" * 68)
        print("SUBJECT:", r.get("EmailSubject"))
        print("=" * 68)
        print(r.get("CustomEmail"))
        print("=" * 68)
        print("LINKEDIN:", r.get("LinkedIN Req"))
        print("=" * 68)
        print("\nHappy with it? Drop --dry-run and run the whole list.")
        return

    out_path = args.output or args.input.rsplit(".", 1)[0] + "_outreach.json"
    write_json(results, out_path)
    print(f"\nSaved to {out_path}")
    if args.out_csv:
        write_csv(results, args.out_csv, columns=COLUMNS)
        print(f"CSV saved to {args.out_csv}")

    ok = sum(1 for r in results if r.get("outreach_status") == "ok")
    print(f"{ok}/{len(results)} passed every check and are ready to send.")
    bad = [r for r in results if r.get("outreach_status") != "ok"]
    if bad:
        print(f"{len(bad)} were held back — check the outreach_status column for why.")


if __name__ == "__main__":
    main()
