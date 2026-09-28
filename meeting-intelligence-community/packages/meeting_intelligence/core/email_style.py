"""Email body template and first-paragraph wording validation."""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta


DEFAULT_POLICY = {
    "reject_main_points_phrases": [
        "strategic pivot",
        "strategic shift",
        "current business priorities",
        "next steps from the call",
        "opportunity pipeline",
        "recent successes",
        "strategy and tactics",
        "technical requirements",
    ],
    "reject_first_paragraph_phrases": ["game-changer", "game changer", "unlock your", "seamless", "synergy"],
    "watch_phrases": ["strategic", "transition", "scaling", "implementation", "optimization", "framework"],
    "footer_template": "Wishing you much success - I'll see you in our next meeting on {next_meeting_date}!",
    "next_meeting_default_days": 7,
}


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def human_date_without_year(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}"


def next_meeting_label(meeting_date=None, explicit_next=None, days: int = 7) -> str:
    explicit = _parse_date(explicit_next)
    if explicit:
        return human_date_without_year(explicit)
    base = _parse_date(meeting_date) or datetime.now().date()
    return human_date_without_year(base + timedelta(days=days))


def sanitize_dashes(text: str) -> str:
    return (text or "").replace("\u2014", "-").replace("\u2013", "-")


def html_to_plain(text: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", text or "")
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def first_today_paragraph(body_html: str) -> str:
    for paragraph in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", body_html or ""):
        text = html_to_plain(paragraph)
        if re.search(r"\bToday we covered\b", text, flags=re.IGNORECASE):
            return text
    return ""


def validate_first_paragraph(body_html: str, policy: dict | None = None) -> tuple[list[str], list[str]]:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    paragraph = first_today_paragraph(body_html)
    errors: list[str] = []
    warnings: list[str] = []
    if not paragraph:
        return ["Missing required first paragraph starting with 'Today we covered'."], warnings

    for phrase in policy.get("reject_main_points_phrases", []):
        if re.search(re.escape(phrase), paragraph, flags=re.IGNORECASE):
            errors.append(f"Rejected first-paragraph phrase: {phrase}")
    for phrase in policy.get("reject_first_paragraph_phrases", []):
        if re.search(re.escape(phrase), paragraph, flags=re.IGNORECASE):
            errors.append(f"Rejected first-paragraph phrase: {phrase}")
    for phrase in policy.get("watch_phrases", []):
        if re.search(re.escape(phrase), paragraph, flags=re.IGNORECASE):
            warnings.append(f"Watch phrase present in first paragraph: {phrase}")
    return errors, warnings


def generate_email_body(
    participant_name: str,
    doc_url: str,
    main_points: str,
    meeting_date: str,
    policy: dict | None = None,
) -> str:
    policy = {**DEFAULT_POLICY, **(policy or {})}
    first_name = (participant_name or "there").split()[0]
    first_name = first_name[:1].upper() + first_name[1:]
    main_points = sanitize_dashes(main_points or "our recent discussion and next steps")
    next_label = next_meeting_label(meeting_date, days=int(policy.get("next_meeting_default_days", 7)))
    footer = policy.get("footer_template", DEFAULT_POLICY["footer_template"]).format(next_meeting_date=next_label)
    body = f"""
    <div style="font-family: Arial, sans-serif; font-size: 11pt; color: #000000;">
        <p>Hello {first_name},</p>

        <p>Today we covered {main_points}.</p>

        <p>Here is our meeting summary:<br>
        <a href="{doc_url}">{doc_url}</a></p>

        <p>{footer}</p>

        <p>Best regards,<br>
        {policy.get("sender_name", "Your Name")}</p>
    </div>
    """
    return sanitize_dashes(body)
