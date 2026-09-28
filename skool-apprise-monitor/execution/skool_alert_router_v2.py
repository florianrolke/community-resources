"""
skool_alert_router_v2.py — Alert Routing Engine

Routes alerts to the right people based on signal type and tenant config.

Signal types:
  - new_qualified_member   → member just joined + scored as qualified
  - churn_qualified_member → qualified member hasn't been seen for N days
  - monetary_win           → post detected as monetary win
  - antigravity_mention    → post mentions Anti-Gravity / Florian

Channels:
  - email (via email_notifier.py)
  - desktop push (via Apprise API → ntfy)

Usage:
  python execution/skool_alert_router_v2.py --test --tenant aiautomationsbyjack
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


def _build_member_alert_content(member: dict, signal_type: str) -> tuple:
    """
    Build email subject + HTML body for a member alert.
    Returns (subject, html_body, text_body)
    """
    name = member.get("name", member.get("handle", "Unknown"))
    handle = member.get("handle", "")
    community = member.get("community", "")
    bio = member.get("bio", "")[:200]
    linkedin = member.get("linkedin", "")
    profile_url = member.get("profileUrl", f"https://www.skool.com/@{handle}")

    fin_score = member.get("financial_score", 0)
    fin_tier = member.get("financial_tier", "?")
    icp_score = member.get("icp_score", 0)
    icp_tier = member.get("icp_tier", "?")
    fin_reasons = member.get("financial_reasons", [])[:3]
    icp_reasons = member.get("icp_reasons", [])[:3]

    flag_both = member.get("flag_both", False)
    flag_fin = member.get("flag_financial_only", False)
    flag_icp = member.get("flag_icp_only", False)

    is_churn = signal_type == "churn_qualified_member"
    days_absent = member.get("days_absent", 0) if is_churn else None

    if is_churn:
        emoji = "⚠️"
        action = "CHURN RISK"
        context = f"Has not been seen for {days_absent} days — may be leaving the community."
    else:
        emoji = "🎯"
        action = "NEW MEMBER"
        context = "Just joined the community."

    flag_label = "Financial + ICP" if flag_both else ("Financial" if flag_fin else "ICP")
    subject = f"{emoji} [{flag_label} | Tier {fin_tier}/{icp_tier}] {name} — {community}"

    # Qualification reasons bullets
    reasons_html = ""
    if fin_reasons:
        reasons_html += "<b>Financial signals:</b><ul>" + "".join(f"<li>{r}</li>" for r in fin_reasons) + "</ul>"
    if icp_reasons:
        reasons_html += "<b>ICP signals:</b><ul>" + "".join(f"<li>{r}</li>" for r in icp_reasons) + "</ul>"

    html_body = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: {'#e74c3c' if is_churn else '#2ecc71'};">{emoji} {action}: {name}</h2>
<p><b>Community:</b> {community}<br>
<b>Status:</b> {context}<br>
{'<b>Days absent:</b> ' + str(days_absent) + '<br>' if days_absent else ''}
<b>Profile:</b> <a href="{profile_url}">{profile_url}</a><br>
{'<b>LinkedIn:</b> <a href="' + linkedin + '">' + linkedin + '</a><br>' if linkedin else ''}
</p>

<hr>

<h3>Scores</h3>
<table style="border-collapse: collapse; width: 100%;">
<tr>
  <td style="padding: 8px; background: #f8f9fa;"><b>Financial Qualification</b></td>
  <td style="padding: 8px;">{fin_score}/100 — Tier {fin_tier}</td>
</tr>
<tr>
  <td style="padding: 8px; background: #f8f9fa;"><b>Heroes Arc ICP</b></td>
  <td style="padding: 8px;">{icp_score}/100 — Tier {icp_tier}</td>
</tr>
</table>

<h3>Why They Scored</h3>
{reasons_html if reasons_html else '<p><i>No specific signals detected</i></p>'}

<h3>Bio</h3>
<p style="background: #f8f9fa; padding: 10px; border-radius: 4px;">{bio}</p>

{'<h3>Message Draft</h3><p style="background: #fff3cd; padding: 10px; border-radius: 4px; border-left: 4px solid #ffc107;">' + member.get("_message_draft", "") + '</p>' if member.get("_message_draft") else ''}

<hr>
<p style="color: #888; font-size: 12px;">
Skool Intelligence v2 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
</p>
</body></html>
"""

    text_body = f"""
{emoji} {action}: {name}
Community: {community}
{context}
Profile: {profile_url}
{('LinkedIn: ' + linkedin) if linkedin else ''}

Financial Score: {fin_score}/100 (Tier {fin_tier})
ICP Score: {icp_score}/100 (Tier {icp_tier})

Bio: {bio}
"""
    return subject, html_body, text_body


def _build_post_alert_content(post: dict, signal_type: str) -> tuple:
    """Build email content for post alerts (wins + mentions)."""
    author = post.get("authorName", "Unknown")
    title = post.get("title", "(no title)")
    content = post.get("content", "")[:400]
    post_url = post.get("postUrl", "")
    keywords = post.get("_matched_keywords", [])
    community = post.get("community", "")

    if signal_type == "monetary_win":
        emoji = "💰"
        subject = f"💰 WIN: {author} posted a monetary win in {community}"
    else:
        emoji = "📡"
        subject = f"📡 Anti-Gravity Mention: {author} mentioned you in {community}"

    html_body = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2>{emoji} {subject}</h2>

<p><b>Author:</b> {author}<br>
<b>Post:</b> {title}<br>
{'<b>URL:</b> <a href="' + post_url + '">' + post_url + '</a><br>' if post_url else ''}
<b>Keywords matched:</b> {', '.join(keywords)}<br>
</p>

<h3>Post Content</h3>
<p style="background: #f8f9fa; padding: 10px; border-radius: 4px;">{content}</p>

<hr>
<p style="color: #888; font-size: 12px;">
Skool Intelligence v2 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
</p>
</body></html>
"""
    text_body = f"{emoji} {subject}\n\nAuthor: {author}\n{content}"
    return subject, html_body, text_body


def send_desktop_push(title: str, body: str, ntfy_url: str, notify_type: str = "info", dry_run: bool = False) -> bool:
    """Send desktop push via Apprise API → ntfy."""
    if dry_run:
        print(f"  [DRY RUN] Push: {title}")
        return True
    try:
        from skool_apprise_monitor import send_apprise_notification
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        # Temporarily override APPRISE_URLS env to use the specific ntfy URL
        os.environ["APPRISE_URLS"] = ntfy_url
        result = send_apprise_notification(title, body[:500], notify_type=notify_type)
        return result
    except Exception as e:
        print(f"  Push error: {e}")
        return False


ALLOWED_EMAIL_RECIPIENTS = {"you@example.com", "you@example.com"}


def _is_email_allowed(email: str) -> bool:
    """Only allow sending to Florian's own addresses. Block all others."""
    return email.lower().strip() in ALLOWED_EMAIL_RECIPIENTS


def send_email_alert(to: str, subject: str, html_body: str, text_body: str, dry_run: bool = False) -> bool:
    """Send email alert via email_notifier.py. Only sends to whitelisted addresses."""
    if not _is_email_allowed(to):
        print(f"  [BLOCKED] Email to {to} blocked — not in allowed recipients. Only {ALLOWED_EMAIL_RECIPIENTS} allowed.")
        return False
    if dry_run:
        print(f"  [DRY RUN] Email to {to}: {subject}")
        return True
    try:
        from email_notifier import send_html_email
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        result = send_html_email(to, subject, html_body, text_body)
        success = result.get("status") == "sent"
        if success:
            print(f"  Email sent to {to}")
        else:
            print(f"  Email failed to {to}: {result.get('reason', 'unknown')}")
        return success
    except Exception as e:
        print(f"  Email error to {to}: {e}")
        return False


def route_alert(signal_type: str, data: dict, config: dict, dry_run: bool = False) -> int:
    """
    Route a single alert to all configured recipients.

    Args:
        signal_type: "new_qualified_member" | "churn_qualified_member" | "monetary_win" | "antigravity_mention"
        data: member dict or post dict
        config: Tenant config
        dry_run: Don't actually send

    Returns:
        Number of notifications sent
    """
    is_member_signal = signal_type in ("new_qualified_member", "churn_qualified_member")
    is_post_signal = signal_type in ("monetary_win", "antigravity_mention")

    if is_member_signal:
        subject, html_body, text_body = _build_member_alert_content(data, signal_type)
    elif is_post_signal:
        subject, html_body, text_body = _build_post_alert_content(data, signal_type)
    else:
        print(f"  Unknown signal type: {signal_type}")
        return 0

    sent_count = 0
    apprise_url = config.get("notifications", {}).get("apprise_url", "https://notify.florianrolke.com")

    for recipient_id, recipient in config.get("alerts", {}).items():
        if signal_type not in recipient.get("receives", []):
            continue

        print(f"  Alerting {recipient_id} ({recipient.get('email', '')})")

        # Email
        email = recipient.get("email", "")
        if email:
            if send_email_alert(email, subject, html_body, text_body, dry_run=dry_run):
                sent_count += 1

        # Desktop push (ntfy) — only if configured
        ntfy_url = recipient.get("desktop_push", "")
        if ntfy_url and is_member_signal:
            name = data.get("name", data.get("handle", "?"))
            fin_tier = data.get("financial_tier", "?")
            icp_tier = data.get("icp_tier", "?")
            push_body = f"Tier {fin_tier}/{icp_tier} | {data.get('bio', '')[:120]}"
            notify_type = "warning" if data.get("flag_both") else "info"
            send_desktop_push(f"🎯 {name} joined", push_body, ntfy_url,
                              notify_type=notify_type, dry_run=dry_run)

    return sent_count


def route_all_alerts(
    new_qualified: list,
    churn_qualified: list,
    monetary_wins: list,
    antigravity_mentions: list,
    config: dict,
    dry_run: bool = False,
) -> int:
    """
    Route all alert types for a single run.
    Returns total notifications sent.
    """
    total = 0

    for member in new_qualified:
        print(f"\n  → New qualified: {member.get('name', '?')}")
        total += route_alert("new_qualified_member", member, config, dry_run=dry_run)

    for member in churn_qualified:
        print(f"\n  → Churn qualified: {member.get('name', '?')}")
        total += route_alert("churn_qualified_member", member, config, dry_run=dry_run)

    for post in monetary_wins:
        print(f"\n  → Monetary win: {post.get('authorName', '?')}")
        total += route_alert("monetary_win", post, config, dry_run=dry_run)

    for post in antigravity_mentions:
        print(f"\n  → Anti-Gravity mention: {post.get('authorName', '?')}")
        total += route_alert("antigravity_mention", post, config, dry_run=dry_run)

    return total


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Alert Router v2")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--test", action="store_true", help="Send test alerts to all recipients")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    tenant_dir = EXECUTION_DIR / "tenants" / args.tenant
    with open(tenant_dir / "config.json", "r") as f:
        config = json.load(f)

    if args.test:
        # Send a test alert for each recipient
        test_member = {
            "name": "TEST Member",
            "handle": "test-member",
            "bio": "CEO of a $5M manufacturing company. Looking to automate operations.",
            "community": config["community_slug"],
            "profileUrl": "https://www.skool.com/@test-member",
            "linkedin": "",
            "financial_score": 72,
            "financial_tier": "A",
            "icp_score": 65,
            "icp_tier": "B",
            "financial_reasons": ["+25 business owner", "+15 manufacturing industry", "+10 revenue signal"],
            "icp_reasons": ["+25 owner signal", "+10 US-based"],
            "flag_both": True,
            "flag_financial_only": False,
            "flag_icp_only": False,
            "flag_qualified": True,
        }
        count = route_alert("new_qualified_member", test_member, config, dry_run=args.dry_run)
        print(f"\nTest sent {count} notifications")


if __name__ == "__main__":
    main()
