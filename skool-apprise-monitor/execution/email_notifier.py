#!/usr/bin/env python3
"""
Email Notifier — Send notification emails via SMTP (Gmail).

Reusable email sender for all notification scripts:
- New qualified member alerts
- Intro post alerts
- Churn risk alerts

Usage:
    # As a module:
    from execution.email_notifier import send_email, send_html_email

    send_email(
        to="florian@example.com",
        subject="New Tier A lead: John Smith",
        body="Details here..."
    )

    # Standalone test:
    python execution/email_notifier.py --test

Requires in .env:
    NOTIFY_EMAIL_FROM=you@example.com
    NOTIFY_EMAIL_PASSWORD=your-app-password
    NOTIFY_EMAIL_TO=you@example.com
    NOTIFY_SMTP_HOST=smtp.gmail.com       (optional, defaults to Gmail)
    NOTIFY_SMTP_PORT=587                   (optional, defaults to 587)

Gmail App Password setup:
    1. Enable 2FA on your Google account
    2. Go to https://myaccount.google.com/apppasswords
    3. Create an app password for "Mail"
    4. Use that 16-char password as NOTIFY_EMAIL_PASSWORD
"""

import os
import sys
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

logger = logging.getLogger("email-notifier")

# Defaults
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587

# SAFETY: Only these addresses may receive emails. All others are blocked.
ALLOWED_RECIPIENTS = {"you@example.com", "you@example.com"}


def _check_recipient_allowed(recipient: str) -> bool:
    """Block all email recipients except Florian's own addresses."""
    if recipient.lower().strip() in ALLOWED_RECIPIENTS:
        return True
    logger.warning(f"BLOCKED: email to {recipient} — not in allowed list {ALLOWED_RECIPIENTS}")
    print(f"  [BLOCKED] Email to {recipient} — only {ALLOWED_RECIPIENTS} allowed.")
    return False


def get_config() -> dict:
    """Load email configuration from environment."""
    return {
        "from_email": os.getenv("NOTIFY_EMAIL_FROM", ""),
        "password": os.getenv("NOTIFY_EMAIL_PASSWORD", ""),
        "to_email": os.getenv("NOTIFY_EMAIL_TO", ""),
        "smtp_host": os.getenv("NOTIFY_SMTP_HOST", DEFAULT_SMTP_HOST),
        "smtp_port": int(os.getenv("NOTIFY_SMTP_PORT", DEFAULT_SMTP_PORT)),
    }


def send_email(to: str, subject: str, body: str, from_name: str = "Skool Monitor") -> dict:
    """
    Send a plain-text email via SMTP.

    Args:
        to: Recipient email (overrides NOTIFY_EMAIL_TO if provided)
        subject: Email subject line
        body: Plain text email body
        from_name: Display name for the sender

    Returns:
        dict with status and details
    """
    config = get_config()

    if not config["from_email"] or not config["password"]:
        logger.warning("Email not configured (NOTIFY_EMAIL_FROM / NOTIFY_EMAIL_PASSWORD missing)")
        print(f"  [EMAIL SKIPPED] Would send to {to}: {subject}")
        return {"status": "skipped", "reason": "not_configured"}

    recipient = to or config["to_email"]
    if not recipient:
        return {"status": "error", "reason": "no_recipient"}
    if not _check_recipient_allowed(recipient):
        return {"status": "blocked", "reason": f"recipient {recipient} not in allowed list"}

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"{from_name} <{config['from_email']}>"
    msg["To"] = recipient
    msg["Subject"] = subject

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["from_email"], config["password"])
            server.send_message(msg)

        logger.info(f"Email sent to {recipient}: {subject}")
        return {"status": "sent", "to": recipient, "subject": subject}

    except Exception as e:
        logger.error(f"Email failed: {e}")
        return {"status": "error", "reason": str(e)}


def send_html_email(to: str, subject: str, html_body: str, text_body: str = "",
                    from_name: str = "Skool Monitor") -> dict:
    """
    Send an HTML email with plain-text fallback.

    Args:
        to: Recipient email
        subject: Email subject line
        html_body: HTML email body
        text_body: Plain text fallback (auto-generated if empty)
        from_name: Display name for the sender

    Returns:
        dict with status and details
    """
    config = get_config()

    if not config["from_email"] or not config["password"]:
        logger.warning("Email not configured")
        print(f"  [EMAIL SKIPPED] Would send to {to}: {subject}")
        return {"status": "skipped", "reason": "not_configured"}

    recipient = to or config["to_email"]
    if not recipient:
        return {"status": "error", "reason": "no_recipient"}
    if not _check_recipient_allowed(recipient):
        return {"status": "blocked", "reason": f"recipient {recipient} not in allowed list"}

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{config['from_email']}>"
    msg["To"] = recipient
    msg["Subject"] = subject

    # Plain text part (fallback)
    if not text_body:
        import re
        text_body = re.sub(r'<[^>]+>', '', html_body)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["from_email"], config["password"])
            server.send_message(msg)

        logger.info(f"HTML email sent to {recipient}: {subject}")
        return {"status": "sent", "to": recipient, "subject": subject}

    except Exception as e:
        logger.error(f"Email failed: {e}")
        return {"status": "error", "reason": str(e)}


def format_lead_alert(lead: dict) -> tuple:
    """
    Format a single lead into email subject + body for notification.

    Returns:
        (subject, html_body, text_body)
    """
    name = lead.get("name", "Unknown")
    tier = lead.get("tier", "?")
    score = lead.get("icp_score", 0)
    community = lead.get("community", "unknown")

    city = lead.get("city", "")
    country = lead.get("country", "")
    location = f"{city}, {country}".strip(", ") if city or country else "Unknown"

    bio = lead.get("bio", "")[:300]
    linkedin = lead.get("linkedin", "")
    skool_url = lead.get("skool_url", "")
    services = lead.get("services", "")
    industries = lead.get("industries", "")

    subject = f"[Tier {tier}] New member: {name} ({community})"

    text_body = f"""New Qualified Member Alert

Name: {name}
Tier: {tier} (Score: {score}/100)
Community: {community}
Location: {location}
Bio: {bio}
Services: {services}
Industries: {industries}
LinkedIn: {linkedin}
Skool: {skool_url}
"""

    html_body = f"""
<div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: {'#22c55e' if tier == 'A' else '#3b82f6' if tier == 'B' else '#f59e0b'}; color: white; padding: 16px 20px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0;">Tier {tier} — {name}</h2>
    <p style="margin: 4px 0 0; opacity: 0.9;">ICP Score: {score}/100 | {community}</p>
  </div>
  <div style="border: 1px solid #e5e7eb; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
    <table style="width: 100%; border-collapse: collapse;">
      <tr><td style="padding: 6px 0; color: #6b7280;">Location</td><td style="padding: 6px 0;">{location}</td></tr>
      <tr><td style="padding: 6px 0; color: #6b7280;">Services</td><td style="padding: 6px 0;">{services or 'N/A'}</td></tr>
      <tr><td style="padding: 6px 0; color: #6b7280;">Industries</td><td style="padding: 6px 0;">{industries or 'N/A'}</td></tr>
    </table>
    <p style="margin: 16px 0 8px; color: #6b7280; font-size: 13px;">Bio</p>
    <p style="margin: 0; line-height: 1.5;">{bio or 'No bio available'}</p>
    <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
      {f'<a href="{linkedin}" style="color: #3b82f6; text-decoration: none; margin-right: 16px;">LinkedIn</a>' if linkedin else ''}
      {f'<a href="{skool_url}" style="color: #3b82f6; text-decoration: none;">Skool Profile</a>' if skool_url else ''}
    </div>
  </div>
</div>
"""
    return subject, html_body, text_body


def format_digest_alert(leads: list, community: str) -> tuple:
    """
    Format multiple leads into a digest email.

    Returns:
        (subject, html_body, text_body)
    """
    tier_a = [l for l in leads if l.get("tier") == "A"]
    tier_b = [l for l in leads if l.get("tier") == "B"]

    subject = f"[Skool] {len(leads)} new qualified members in {community}"

    rows_html = ""
    for lead in sorted(leads, key=lambda x: x.get("icp_score", 0), reverse=True):
        name = lead.get("name", "Unknown")
        tier = lead.get("tier", "?")
        score = lead.get("icp_score", 0)
        bio_short = (lead.get("bio", "") or "")[:120]
        linkedin = lead.get("linkedin", "")
        color = '#22c55e' if tier == 'A' else '#3b82f6'

        rows_html += f"""
    <tr>
      <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
        <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">Tier {tier}</span>
        <strong style="margin-left: 8px;">{name}</strong>
        <span style="color: #6b7280; margin-left: 8px;">({score}/100)</span>
        {f'<a href="{linkedin}" style="color: #3b82f6; margin-left: 8px; font-size: 13px;">LinkedIn</a>' if linkedin else ''}
        <br><span style="color: #6b7280; font-size: 13px;">{bio_short}</span>
      </td>
    </tr>"""

    text_body = f"New Qualified Members in {community}\n\n"
    text_body += f"Tier A: {len(tier_a)} | Tier B: {len(tier_b)}\n\n"
    for lead in leads:
        text_body += f"[{lead.get('tier', '?')}] {lead.get('name', 'Unknown')} — {lead.get('icp_score', 0)}/100\n"
        text_body += f"    {(lead.get('bio', '') or '')[:120]}\n\n"

    html_body = f"""
<div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #1e293b; color: white; padding: 16px 20px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0;">{len(leads)} New Qualified Members</h2>
    <p style="margin: 4px 0 0; opacity: 0.9;">{community} | Tier A: {len(tier_a)} | Tier B: {len(tier_b)}</p>
  </div>
  <div style="border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
    <table style="width: 100%; border-collapse: collapse;">
      {rows_html}
    </table>
  </div>
</div>
"""
    return subject, html_body, text_body


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test email notifier")
    parser.add_argument("--test", action="store_true", help="Send a test email")
    parser.add_argument("--to", help="Override recipient email")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.test:
        config = get_config()
        recipient = args.to or config["to_email"]

        if not recipient:
            print("ERROR: No recipient. Set NOTIFY_EMAIL_TO in .env or use --to")
            sys.exit(1)

        print(f"Sending test email to {recipient}...")
        result = send_email(
            to=recipient,
            subject="[TEST] Skool Monitor Email Test",
            body="This is a test email from the Skool notification system.\n\nIf you received this, email notifications are working."
        )
        print(f"Result: {result}")
    else:
        print("Use --test to send a test email")
        print(f"Config: from={get_config()['from_email']}, to={get_config()['to_email']}")
        print(f"SMTP: {get_config()['smtp_host']}:{get_config()['smtp_port']}")
