"""
skool_daily_digest_v3.py — Daily intelligence email + Claude UI batch prep.

Reads today's events from the JSONL log written by skool_apprise_monitor.py,
aggregates all new members, cancellations, wins, and mentions, then:
1. Sends an HTML email digest with clickable links (Skool/LinkedIn/website)
2. Auto-generates Claude UI markdown batches for manual deep research

Data source: {STATE_DIR}/events/{community}_YYYY-MM-DD.jsonl
Written by:  skool_apprise_monitor.py → log_event()

Usage:
  python execution/skool_daily_digest_v3.py --community aiautomationsbyjack
  python execution/skool_daily_digest_v3.py --community aiautomationsbyjack --dry-run
  python execution/skool_daily_digest_v3.py --community aiautomationsbyjack --date 2026-02-22
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Directories
STATE_DIR = Path(os.getenv("STATE_DIR", str(BASE_DIR / ".tmp" / "apprise_state")))
EVENTS_DIR = Path(os.getenv("EVENTS_DIR", str(STATE_DIR / "events")))
BATCH_DIR = BASE_DIR / ".tmp" / "claude_batches"


def load_events(community: str, target_date: str) -> list:
    """Load all events for a given date from the JSONL log."""
    log_path = EVENTS_DIR / f"{community}_{target_date}.jsonl"
    if not log_path.exists():
        return []
    events = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def _is_valid_handle(handle: str) -> bool:
    """Validate that a handle looks like a real Skool handle (anti-hallucination)."""
    import re
    if not handle or not isinstance(handle, str):
        return False
    # Skool handles: lowercase letters, numbers, hyphens, ending with digits
    return bool(re.match(r'^[a-z0-9][a-z0-9-]*[0-9]+$', handle))


def categorize_events(events: list) -> dict:
    """Categorize events by type. Validates member handles to prevent fake data."""
    cats = {
        "new_member": [],
        "cancellation": [],
        "win": [],
        "antigravity": [],
        "mention": [],
    }
    skipped = 0
    for event in events:
        etype = event.get("type", "")
        if etype not in cats:
            continue
        data = event.get("data", {})

        # Anti-hallucination: member events must have valid handles
        if etype in ("new_member", "cancellation"):
            handle = data.get("handle", "")
            if not _is_valid_handle(handle):
                skipped += 1
                continue

        # Post events must have a postId or post_url from actual scrape
        if etype in ("win", "antigravity", "mention"):
            if not data.get("post_url") and not data.get("postId"):
                skipped += 1
                continue

        cats[etype].append(data)

    if skipped:
        print(f"  [ANTI-HALLUCINATION] Skipped {skipped} events with invalid data")
    return cats


def _link(url: str, text: str) -> str:
    """Create an HTML link, or just text if no URL."""
    if url and url.startswith("http"):
        return f'<a href="{url}" style="color: #2563eb; text-decoration: none;">{text}</a>'
    return text


def _member_links_html(data: dict) -> str:
    """Build clickable links row for a member."""
    enrichment = data.get("enrichment", {})
    handle = data.get("handle", "")
    parts = []
    profile_url = data.get("profileUrl", f"https://www.skool.com/@{handle}")
    parts.append(_link(profile_url, "Skool"))
    if enrichment.get("linkedin"):
        parts.append(_link(enrichment["linkedin"], "LinkedIn"))
    if enrichment.get("website"):
        parts.append(_link(enrichment["website"], "Website"))
    return " | ".join(parts)


def build_digest_html(community: str, categories: dict, target_date: str) -> tuple:
    """Build the HTML email digest with clickable links everywhere."""
    new_members = categories["new_member"]
    cancellations = categories["cancellation"]
    wins = categories["win"]
    antigravity = categories["antigravity"]
    mentions = categories["mention"]

    subject = f"[Skool Intelligence] {target_date}"
    parts = []
    if new_members:
        parts.append(f"{len(new_members)} new ICP")
    if cancellations:
        parts.append(f"{len(cancellations)} cancelled")
    if wins:
        parts.append(f"{len(wins)} wins")
    if parts:
        subject += f" — {', '.join(parts)}"

    # --- Section 1: New Members ---
    members_html = ""
    for m in sorted(new_members, key=lambda x: x.get("icp_score", 0), reverse=True):
        name = m.get("name", m.get("handle", "?"))
        tier = m.get("tier", "?")
        score = m.get("icp_score", 0)
        enrichment = m.get("enrichment", {})
        company = enrichment.get("company", "")
        desc = enrichment.get("company_description", "")
        reasons = ", ".join(m.get("match_reasons", []))
        links = _member_links_html(m)

        tier_color = "#e74c3c" if tier == "A" else "#f39c12" if tier == "B" else "#888"

        members_html += f"""
        <tr>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
            <span style="background: {tier_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;">Tier {tier}</span>
            <strong style="margin-left: 8px; font-size: 15px;">{name}</strong>
            <span style="color: #888; margin-left: 6px;">(Score: {score})</span>
            <br>
            {'<span style="color: #555;">' + company + (' — ' + desc if desc else '') + '</span><br>' if company else ''}
            {'<span style="color: #888; font-size: 13px;">Signals: ' + reasons + '</span><br>' if reasons else ''}
            <span style="font-size: 13px;">{links}</span>
          </td>
        </tr>"""

    # --- Section 2: Cancellations ---
    cancel_html = ""
    for c in cancellations:
        name = c.get("name", c.get("handle", "?"))
        tier = c.get("tier", "unknown")
        enrichment = c.get("enrichment", {})
        company = enrichment.get("company", "")
        joined = c.get("joinedAt", "")[:10]
        links = _member_links_html(c)

        cancel_html += f"""
        <tr>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
            <span style="background: #e74c3c; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">CANCELLED</span>
            <strong style="margin-left: 8px;">{name}</strong>
            {'<span style="color: #888;"> — ' + tier + '</span>' if tier != 'unknown' else ''}
            <br>
            {'<span style="color: #555;">' + company + '</span><br>' if company else ''}
            {'<span style="color: #888; font-size: 13px;">Joined: ' + joined + '</span><br>' if joined else ''}
            <span style="font-size: 13px;">{links}</span>
          </td>
        </tr>"""

    # --- Section 3: Monetary Wins ---
    wins_html = ""
    for w in wins:
        author = w.get("author_name", "?")
        title = w.get("title", "")[:80]
        pattern = w.get("money_pattern", "")
        post_url = w.get("post_url", "")
        author_handle = w.get("author_handle", "")

        wins_html += f"""
        <tr>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
            <span style="background: #27ae60; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">{pattern.upper()}</span>
            <strong style="margin-left: 8px;">{author}</strong>
            <br>
            {_link(post_url, title) if title else ''}
            {' | ' + _link(f'https://www.skool.com/@{author_handle}', 'Profile') if author_handle else ''}
          </td>
        </tr>"""

    # --- Section 4: Anti-Gravity Mentions ---
    ag_html = ""
    for ag in antigravity:
        author = ag.get("author_name", "?")
        title = ag.get("post_title", "")[:80]
        post_url = ag.get("post_url", "")
        context = ag.get("context", "")[:150]

        ag_html += f"""
        <tr>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
            <strong>{author}</strong> mentioned anti-gravity
            <br>
            {_link(post_url, title) if title else ''}
            {'<br><span style="color: #666; font-size: 13px;">"' + context + '"</span>' if context else ''}
          </td>
        </tr>"""

    # --- Section 5: Meaningful Tags ---
    meaningful_mentions = [m for m in mentions if m.get("meaningful")]
    tags_html = ""
    for m in meaningful_mentions:
        author = m.get("author_name", "?")
        title = m.get("post_title", "")[:80]
        post_url = m.get("post_url", "")
        context = m.get("context", "")[:150]

        tags_html += f"""
        <tr>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
            <strong>{author}</strong>
            <br>
            {_link(post_url, title)}
            {'<br><span style="color: #666; font-size: 13px;">"' + context + '"</span>' if context else ''}
          </td>
        </tr>"""

    # --- Section 6: Claude UI Batch Status ---
    batch_count = len(new_members)
    batch_note = ""
    if batch_count > 0:
        batch_note = f"""
        <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 12px; margin-top: 16px;">
          <strong>{batch_count} new member{'s' if batch_count != 1 else ''} need deep research.</strong>
          <br>Claude UI batch file: <code>.tmp/claude_batches/pending_{target_date}.md</code>
          <br><span style="color: #666; font-size: 13px;">Paste into Claude.com for 150-300 word enrichment summaries.</span>
        </div>"""

    # --- Full HTML ---
    total_events = sum(len(v) for v in categories.values())

    html = f"""
<html><body style="font-family: -apple-system, Arial, sans-serif; max-width: 680px; margin: 0 auto; color: #333;">

<div style="background: #1e293b; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
  <h2 style="margin: 0;">Skool Intelligence — Daily Digest</h2>
  <p style="margin: 4px 0 0; opacity: 0.85;">{community} | {target_date} | {total_events} events</p>
</div>

<div style="border: 1px solid #e5e7eb; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">

  <!-- Summary Stats -->
  <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
    <tr>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #2ecc71;">{len(new_members)}</div>
        <div style="color: #888; font-size: 13px;">New ICP</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #e74c3c;">{len(cancellations)}</div>
        <div style="color: #888; font-size: 13px;">Cancelled</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #f39c12;">{len(wins)}</div>
        <div style="color: #888; font-size: 13px;">Wins</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #9b59b6;">{len(antigravity)}</div>
        <div style="color: #888; font-size: 13px;">AG Mentions</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #3498db;">{len(meaningful_mentions)}</div>
        <div style="color: #888; font-size: 13px;">Tags</div>
      </td>
    </tr>
  </table>

  {'<h3 style="margin-top: 0;">New ICP Members</h3><table style="width: 100%; border-collapse: collapse;">' + members_html + '</table>' if members_html else ''}

  {'<h3 style="color: #e74c3c;">Paid Cancellations ($77/mo)</h3><table style="width: 100%; border-collapse: collapse;">' + cancel_html + '</table>' if cancel_html else ''}

  {'<h3 style="color: #27ae60;">Monetary Wins</h3><table style="width: 100%; border-collapse: collapse;">' + wins_html + '</table>' if wins_html else ''}

  {'<h3 style="color: #9b59b6;">Anti-Gravity Mentions</h3><table style="width: 100%; border-collapse: collapse;">' + ag_html + '</table>' if ag_html else ''}

  {'<h3 style="color: #3498db;">Meaningful Tags (@florian)</h3><table style="width: 100%; border-collapse: collapse;">' + tags_html + '</table>' if tags_html else ''}

  {batch_note}

  <p style="color: #888; font-size: 12px; margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
    Skool Intelligence v3 | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
  </p>
</div>
</body></html>
"""

    return subject, html


def generate_claude_batches(new_members: list, target_date: str) -> str | None:
    """
    Auto-generate Claude UI markdown batches for manual deep research.

    Same proven format from archive/batch_prompts/ that produced 80% LinkedIn coverage.
    Returns path to the generated batch file, or None if no members to batch.
    """
    if not new_members:
        return None

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batch_path = BATCH_DIR / f"pending_{target_date}.md"

    lines = [
        f"# Claude UI Deep Research Batch — {target_date}",
        f"# {len(new_members)} members need 150-300 word enrichment summaries",
        "",
        "**Instructions:** For each lead below, research their website, LinkedIn profile,",
        "and online presence. Write a 150-300 word semantic summary in the 'Original Notes'",
        "field. Include: what they do, who they serve, pricing if visible, company size,",
        "notable achievements, and any pain signals. Keep all other fields — update any that",
        "you find better data for. Return in the exact same markdown table format.",
        "",
        "---",
        "",
    ]

    for i, m in enumerate(new_members, 1):
        enrichment = m.get("enrichment", {})
        name = m.get("name", m.get("handle", "?"))
        handle = m.get("handle", "")
        linkedin = enrichment.get("linkedin", "")
        website = enrichment.get("website", "")
        company = enrichment.get("company", "")
        city = enrichment.get("city", "")
        country = enrichment.get("country", "")
        services = ", ".join(enrichment.get("services", []))
        industries = ", ".join(enrichment.get("industries", []))

        lines.append(f"## LEAD {i}: {name}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| **Name** | {name} |")
        if city or country:
            lines.append(f"| **City** | {city} |")
            lines.append(f"| **Country** | {country} |")
        if website:
            lines.append(f"| **Website** | {website} |")
        if linkedin:
            lines.append(f"| **LinkedIn** | {linkedin} |")
        lines.append(f"| **Skool Profile** | https://www.skool.com/@{handle} |")
        if company:
            lines.append(f"| **Company** | {company} |")
        if services:
            lines.append(f"| **Services** | {services} |")
        if industries:
            lines.append(f"| **Industries** | {industries} |")
        lines.append(f"| **Original Notes** | NEEDS ENRICHMENT - Please research and write 150-300 word summary |")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(batch_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return str(batch_path)


def _send_via_smtp(to: str, subject: str, html_body: str, from_name: str = "Skool Intelligence") -> bool:
    """Send email via SMTP (standalone, no external deps). Uses SMTP_* env vars."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import re as _re

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print(f"  SMTP not configured (SMTP_USER/SMTP_PASS missing)")
        return False

    text_body = _re.sub(r'<[^>]+>', '', html_body)[:5000]

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    print(f"  Digest sent via SMTP to {to}")
    return True


def send_digest(to: str, subject: str, html_body: str, dry_run: bool = False):
    """Send the digest email. Tries email_notifier (Gmail API), falls back to SMTP."""
    if dry_run:
        print(f"\n  [DRY RUN] Would send digest to {to}")
        print(f"  Subject: {subject}")
        return True

    # Try email_notifier (Gmail API) first — available locally
    try:
        from email_notifier import send_html_email
        result = send_html_email(to, subject, html_body, from_name="Skool Intelligence")
        if result.get("status") == "sent":
            print(f"  Digest sent via Gmail API to {to}")
            return True
        print(f"  Gmail API: {result.get('status')} — {result.get('reason', '')}")
    except ImportError:
        print(f"  email_notifier not available, trying SMTP...")
    except Exception as e:
        print(f"  Gmail API error: {e}")

    # Fallback: direct SMTP (works in Docker with SMTP_* env vars)
    try:
        return _send_via_smtp(to, subject, html_body)
    except Exception as e:
        print(f"  SMTP error: {e}")
        return False


def run_digest(community: str, target_date: str = None, dry_run: bool = False,
               email_to: str = "you@example.com"):
    """
    Run the daily digest. Can be called from the daemon loop or standalone.

    Returns True if digest was sent successfully.
    """
    if not target_date:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"DAILY DIGEST v3 — {community}")
    print(f"Date: {target_date}")
    print(f"{'='*60}")

    # Load and categorize events
    events = load_events(community, target_date)
    print(f"  Events loaded: {len(events)}")

    if not events:
        print(f"  No events for {target_date}. Skipping digest.")
        return False

    categories = categorize_events(events)
    for cat, items in categories.items():
        if items:
            print(f"  {cat}: {len(items)}")

    # Build HTML email
    subject, html = build_digest_html(community, categories, target_date)
    print(f"  Subject: {subject}")

    # Generate Claude UI batches
    batch_path = generate_claude_batches(categories["new_member"], target_date)
    if batch_path:
        print(f"  Claude UI batch: {batch_path}")

    # Send email
    sent = send_digest(email_to, subject, html, dry_run=dry_run)

    print(f"\n  Digest {'sent' if sent else 'skipped'}.")
    return sent


def main():
    parser = argparse.ArgumentParser(description="Skool Daily Digest v3")
    parser.add_argument("--community", default="aiautomationsbyjack", help="Community slug")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today UTC")
    parser.add_argument("--email", default="you@example.com", help="Recipient email")
    args = parser.parse_args()

    run_digest(
        community=args.community,
        target_date=args.date,
        dry_run=args.dry_run,
        email_to=args.email,
    )


if __name__ == "__main__":
    main()
