"""
skool_daily_digest_v2.py — End-of-day summary email

Reads today's run logs from the orchestrator, aggregates results, and sends
a formatted email digest to Florian.

Runs at 11pm EST (04:00 UTC) daily via cron on Coolify.

Usage:
  python execution/skool_daily_digest_v2.py --tenant aiautomationsbyjack
  python execution/skool_daily_digest_v2.py --tenant aiautomationsbyjack --dry-run
  python execution/skool_daily_digest_v2.py --tenant aiautomationsbyjack --date 2026-02-21
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


def get_state_dir(tenant: str) -> Path:
    return BASE_DIR / ".tmp" / "intelligence_v2" / tenant


def load_todays_run_logs(state_dir: Path, target_date: str = None) -> list:
    """Load all run logs from today (or specified date). Returns list of dicts."""
    run_log_dir = state_dir / "run_logs"
    if not run_log_dir.exists():
        return []

    if not target_date:
        target_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    else:
        target_date = target_date.replace("-", "")

    logs = []
    for f in sorted(run_log_dir.glob(f"{target_date}_*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            logs.append(json.load(fh))
    return logs


def aggregate_logs(logs: list) -> dict:
    """Aggregate multiple run logs into a daily summary."""
    summary = {
        "run_count": len(logs),
        "total_new_members": 0,
        "total_churn_risk": 0,
        "total_qualified": 0,
        "total_new_qualified": 0,
        "total_churn_qualified": 0,
        "total_wins": 0,
        "total_mentions": 0,
        "all_qualified": [],
        "all_wins": [],
        "all_mentions": [],
        "errors": [],
        "runs": [],
    }

    for log in logs:
        ts = log.get("timestamp", "")[:19]
        mode = log.get("mode", "?")
        elapsed = log.get("elapsed_seconds", 0)

        job_a = log.get("job_a", {})
        job_b = log.get("job_b", {})

        new_count = job_a.get("new_count", 0)
        churn_count = job_a.get("churn_count", 0)
        qualified_count = job_a.get("qualified_count", 0)
        new_qualified = job_a.get("new_qualified", 0)
        churn_qualified = job_a.get("churn_qualified", 0)
        wins_count = job_b.get("wins_count", 0)
        mentions_count = job_b.get("mentions_count", 0)

        summary["total_new_members"] += new_count
        summary["total_churn_risk"] += churn_count
        summary["total_qualified"] += qualified_count
        summary["total_new_qualified"] += new_qualified
        summary["total_churn_qualified"] += churn_qualified
        summary["total_wins"] += wins_count
        summary["total_mentions"] += mentions_count

        # Collect qualified member details
        for m in job_a.get("qualified", []):
            summary["all_qualified"].append(m)

        for w in job_b.get("wins", []):
            summary["all_wins"].append(w)

        for m in job_b.get("mentions", []):
            summary["all_mentions"].append(m)

        summary["runs"].append({
            "timestamp": ts,
            "mode": mode,
            "elapsed": elapsed,
            "new": new_count,
            "churn": churn_count,
            "qualified": qualified_count,
            "wins": wins_count,
            "mentions": mentions_count,
        })

    return summary


def build_digest_email(tenant: str, config: dict, summary: dict, target_date: str) -> tuple:
    """Build HTML + text email body for the daily digest."""
    display_name = config.get("display_name", tenant)

    subject = f"[Daily Digest] {display_name} - {target_date}"

    if summary["run_count"] == 0:
        subject += " (no runs)"

    # Build run timeline
    runs_html = ""
    for run in summary["runs"]:
        runs_html += f"""
        <tr>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">{run['timestamp']}</td>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">{run['mode']}</td>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">{run['new']} new, {run['churn']} churn</td>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">{run['qualified']} qualified</td>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">{run['wins']} wins</td>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">{run['elapsed']:.0f}s</td>
        </tr>"""

    # Build qualified member highlights
    qualified_html = ""
    top_qualified = sorted(
        summary["all_qualified"],
        key=lambda m: max(m.get("financial_score", 0), m.get("icp_score", 0)),
        reverse=True,
    )[:10]

    for m in top_qualified:
        name = m.get("name", m.get("handle", "?"))
        fin_score = m.get("financial_score", "?")
        fin_tier = m.get("financial_tier", "?")
        icp_score = m.get("icp_score", "?")
        icp_tier = m.get("icp_tier", "?")
        bio = (m.get("bio", "") or "")[:120]
        is_churn = m.get("_churn_risk", False)
        badge = "CHURN" if is_churn else "NEW"
        badge_color = "#e74c3c" if is_churn else "#2ecc71"

        qualified_html += f"""
        <tr>
          <td style="padding: 8px 10px; border-bottom: 1px solid #e5e7eb;">
            <span style="background: {badge_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{badge}</span>
            <strong style="margin-left: 6px;">{name}</strong>
            <span style="color: #888; margin-left: 6px;">F:{fin_tier}({fin_score}) ICP:{icp_tier}({icp_score})</span>
            <br><span style="color: #666; font-size: 13px;">{bio}</span>
          </td>
        </tr>"""

    # Build wins highlights
    wins_html = ""
    for w in summary["all_wins"][:5]:
        title = w.get("title", "")[:80]
        author = w.get("authorName", "?")
        wins_html += f"""
        <tr>
          <td style="padding: 6px 10px; border-bottom: 1px solid #e5e7eb;">
            <strong>{author}</strong>: {title}
          </td>
        </tr>"""

    # Compose full email
    html_body = f"""
<html><body style="font-family: -apple-system, Arial, sans-serif; max-width: 650px; margin: 0 auto; color: #333;">

<div style="background: #1e293b; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
  <h2 style="margin: 0;">Daily Digest: {display_name}</h2>
  <p style="margin: 4px 0 0; opacity: 0.85;">{target_date} | {summary['run_count']} runs today</p>
</div>

<div style="border: 1px solid #e5e7eb; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">

  <!-- Summary Stats -->
  <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
    <tr>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #2ecc71;">{summary['total_new_members']}</div>
        <div style="color: #888; font-size: 13px;">New Members</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #3498db;">{summary['total_qualified']}</div>
        <div style="color: #888; font-size: 13px;">Qualified</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #e74c3c;">{summary['total_churn_risk']}</div>
        <div style="color: #888; font-size: 13px;">Churn Risk</div>
      </td>
      <td style="text-align: center; padding: 12px;">
        <div style="font-size: 28px; font-weight: bold; color: #f39c12;">{summary['total_wins']}</div>
        <div style="color: #888; font-size: 13px;">Wins</div>
      </td>
    </tr>
  </table>

  <!-- Qualified Members -->
  {'<h3 style="margin-top: 0;">Top Qualified Members</h3>' if qualified_html else ''}
  {'<table style="width: 100%; border-collapse: collapse;">' + qualified_html + '</table>' if qualified_html else '<p style="color: #888;">No qualified members today.</p>'}

  <!-- Wins -->
  {'<h3>Monetary Wins</h3>' if wins_html else ''}
  {'<table style="width: 100%; border-collapse: collapse;">' + wins_html + '</table>' if wins_html else ''}

  <!-- Run Timeline -->
  <h3 style="margin-top: 24px;">Run Timeline</h3>
  {'<table style="width: 100%; border-collapse: collapse; font-size: 13px;">' +
   '<tr style="background: #f8f9fa;"><th style="padding: 6px 10px; text-align: left;">Time</th><th style="padding: 6px 10px; text-align: left;">Mode</th><th style="padding: 6px 10px; text-align: left;">Members</th><th style="padding: 6px 10px; text-align: left;">Qualified</th><th style="padding: 6px 10px; text-align: left;">Wins</th><th style="padding: 6px 10px; text-align: left;">Duration</th></tr>' +
   runs_html + '</table>' if runs_html else '<p style="color: #888;">No runs recorded today.</p>'}

  <p style="color: #888; font-size: 12px; margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 12px;">
    Skool Intelligence v2 | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
  </p>
</div>
</body></html>
"""

    text_body = f"""Daily Digest: {display_name} ({target_date})
{summary['run_count']} runs | {summary['total_new_members']} new | {summary['total_qualified']} qualified | {summary['total_churn_risk']} churn | {summary['total_wins']} wins

"""
    for run in summary["runs"]:
        text_body += f"  {run['timestamp']} [{run['mode']}] {run['new']} new, {run['qualified']} qualified, {run['wins']} wins ({run['elapsed']:.0f}s)\n"

    if top_qualified:
        text_body += "\nTop Qualified:\n"
        for m in top_qualified:
            text_body += f"  {m.get('name', '?')} — F:{m.get('financial_tier', '?')}({m.get('financial_score', '?')}) ICP:{m.get('icp_tier', '?')}({m.get('icp_score', '?')})\n"

    return subject, html_body, text_body


def send_digest(to: str, subject: str, html_body: str, text_body: str, dry_run: bool = False):
    """Send the digest email."""
    if dry_run:
        print(f"\n[DRY RUN] Would send digest to {to}")
        print(f"  Subject: {subject}")
        print(f"\n{text_body}")
        return

    try:
        from email_notifier import send_html_email
        result = send_html_email(to, subject, html_body, text_body, from_name="Skool Intelligence")
        if result.get("status") == "sent":
            print(f"  Digest sent to {to}")
        else:
            print(f"  Digest email: {result.get('status')} — {result.get('reason', '')}")
    except Exception as e:
        print(f"  Digest email error: {e}")


def send_digest_push(summary: dict, config: dict, dry_run: bool = False):
    """Send a push notification summary via Apprise."""
    total = summary["total_qualified"]
    wins = summary["total_wins"]
    new = summary["total_new_members"]

    if total == 0 and wins == 0 and new == 0:
        return

    title = f"Daily Digest: {new} new, {total} qualified, {wins} wins"
    body = f"Runs: {summary['run_count']} | Churn risk: {summary['total_churn_risk']}"

    if dry_run:
        print(f"  [DRY RUN] Push: {title}")
        return

    try:
        import requests
        apprise_url = config.get("notifications", {}).get("apprise_url", "")
        if not apprise_url:
            return

        florian_push = config.get("alerts", {}).get("florian", {}).get("desktop_push", "")
        if not florian_push:
            return

        requests.post(
            f"{apprise_url}/notify",
            json={"urls": florian_push, "title": title, "body": body, "type": "info"},
            timeout=10,
            verify=False,
        )
        print(f"  Push sent: {title}")
    except Exception as e:
        print(f"  Push error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Skool Daily Digest v2")
    parser.add_argument("--tenant", required=True, help="Tenant slug")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today UTC")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    config_path = EXECUTION_DIR / "tenants" / args.tenant / "config.json"
    if not config_path.exists():
        print(f"ERROR: No config at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    state_dir = get_state_dir(args.tenant)
    target_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"\nSkool Daily Digest v2")
    print(f"Tenant: {args.tenant}")
    print(f"Date:   {target_date}")
    print(f"Mode:   {'DRY RUN' if args.dry_run else 'LIVE'}")

    # Load and aggregate
    logs = load_todays_run_logs(state_dir, target_date)
    print(f"\nFound {len(logs)} run logs for {target_date}")

    summary = aggregate_logs(logs)

    # Build and send
    subject, html_body, text_body = build_digest_email(args.tenant, config, summary, target_date)

    florian_email = config.get("alerts", {}).get("florian", {}).get("email", "you@example.com")
    send_digest(florian_email, subject, html_body, text_body, dry_run=args.dry_run)

    # Optional push summary
    send_digest_push(summary, config, dry_run=args.dry_run)

    print(f"\nDigest complete.")


if __name__ == "__main__":
    main()
