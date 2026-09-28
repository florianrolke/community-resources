"""
skool_weekly_report_v2.py — Weekly CSV report + master CSV updater

Generates two outputs:
  1. Weekly activity CSV — all events from the past 7 days
  2. Master members CSV — updated with latest scores and status

Optionally emails the weekly CSV to Florian.

Usage:
  python execution/skool_weekly_report_v2.py --tenant aiautomationsbyjack
  python execution/skool_weekly_report_v2.py --tenant aiautomationsbyjack --dry-run
  python execution/skool_weekly_report_v2.py --tenant aiautomationsbyjack --days 14
"""

import csv
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


def load_run_logs_for_period(state_dir: Path, days: int = 7) -> list:
    """Load all run logs from the past N days."""
    run_log_dir = state_dir / "run_logs"
    if not run_log_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_prefix = cutoff.strftime("%Y%m%d")

    logs = []
    for f in sorted(run_log_dir.glob("*.json")):
        if f.stem >= cutoff_prefix:
            with open(f, "r", encoding="utf-8") as fh:
                logs.append(json.load(fh))
    return logs


def generate_weekly_csv(logs: list, output_path: Path) -> int:
    """Generate a weekly activity CSV from run logs. Returns row count."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_timestamp", "event_type", "name", "handle", "bio",
        "financial_score", "financial_tier", "icp_score", "icp_tier",
        "linkedin", "email", "alert_sent", "draft_sent", "notes",
    ]

    rows = []
    for log in logs:
        ts = log.get("timestamp", "")[:19]
        job_a = log.get("job_a", {})
        job_b = log.get("job_b", {})

        # Qualified members
        for m in job_a.get("qualified", []):
            is_churn = m.get("_churn_risk", False)
            rows.append({
                "run_timestamp": ts,
                "event_type": "churn_risk" if is_churn else "new_member",
                "name": m.get("name", ""),
                "handle": m.get("handle", ""),
                "bio": (m.get("bio", "") or "")[:200],
                "financial_score": m.get("financial_score", ""),
                "financial_tier": m.get("financial_tier", ""),
                "icp_score": m.get("icp_score", ""),
                "icp_tier": m.get("icp_tier", ""),
                "linkedin": m.get("linkedin", ""),
                "email": m.get("email", ""),
                "alert_sent": "yes" if log.get("mode") == "live" else "dry_run",
                "draft_sent": "yes" if m.get("_message_draft") else "no",
                "notes": "",
            })

        # Monetary wins
        for w in job_b.get("wins", []):
            rows.append({
                "run_timestamp": ts,
                "event_type": "monetary_win",
                "name": w.get("authorName", ""),
                "handle": "",
                "bio": (w.get("title", "") + " — " + (w.get("content", "") or "")[:100]),
                "financial_score": "", "financial_tier": "",
                "icp_score": "", "icp_tier": "",
                "linkedin": "", "email": "",
                "alert_sent": "yes" if log.get("mode") == "live" else "dry_run",
                "draft_sent": "no",
                "notes": ", ".join(w.get("matched_keywords", [])),
            })

        # Anti-gravity mentions
        for m in job_b.get("mentions", []):
            rows.append({
                "run_timestamp": ts,
                "event_type": "antigravity_mention",
                "name": m.get("authorName", ""),
                "handle": "",
                "bio": (m.get("title", "") + " — " + (m.get("content", "") or "")[:100]),
                "financial_score": "", "financial_tier": "",
                "icp_score": "", "icp_tier": "",
                "linkedin": "", "email": "",
                "alert_sent": "yes" if log.get("mode") == "live" else "dry_run",
                "draft_sent": "no",
                "notes": ", ".join(m.get("matched_keywords", [])),
            })

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return len(rows)


def update_master_csv(state_dir: Path, logs: list) -> int:
    """Update master_members.csv with latest data from run logs."""
    master_path = state_dir / "master_members.csv"

    # Load existing master
    existing = {}
    if master_path.exists():
        with open(master_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                handle = row.get("handle", "").strip()
                if handle:
                    existing[handle] = row

    # Update with data from run logs
    updated = 0
    for log in logs:
        job_a = log.get("job_a", {})
        for m in job_a.get("qualified", []):
            handle = m.get("handle", "").strip()
            if not handle:
                continue

            if handle in existing:
                # Update scores
                existing[handle]["financial_score"] = str(m.get("financial_score", ""))
                existing[handle]["financial_tier"] = str(m.get("financial_tier", ""))
                existing[handle]["icp_score"] = str(m.get("icp_score", ""))
                existing[handle]["icp_tier"] = str(m.get("icp_tier", ""))
                existing[handle]["last_seen"] = log.get("timestamp", "")[:19]
                if m.get("linkedin"):
                    existing[handle]["linkedin"] = m["linkedin"]
                if m.get("email"):
                    existing[handle]["email"] = m["email"]
                if m.get("_churn_risk"):
                    existing[handle]["status"] = "churn_risk"
                else:
                    existing[handle]["status"] = "active"
                updated += 1
            else:
                # New member
                existing[handle] = {
                    "handle": handle,
                    "name": m.get("name", ""),
                    "bio": (m.get("bio", "") or "")[:200],
                    "location": m.get("location", ""),
                    "joinDate": m.get("joinDate", ""),
                    "lastActive": "",
                    "profileUrl": m.get("profileUrl", f"https://www.skool.com/@{handle}"),
                    "linkedin": m.get("linkedin", ""),
                    "email": m.get("email", ""),
                    "website": "",
                    "semantic_summary": "",
                    "source": "intelligence_v2",
                    "first_seen": log.get("timestamp", "")[:19],
                    "last_seen": log.get("timestamp", "")[:19],
                    "status": "active",
                    "financial_score": str(m.get("financial_score", "")),
                    "financial_tier": str(m.get("financial_tier", "")),
                    "icp_score": str(m.get("icp_score", "")),
                    "icp_tier": str(m.get("icp_tier", "")),
                }
                updated += 1

    # Save updated master
    fieldnames = [
        "handle", "name", "bio", "location", "joinDate", "lastActive",
        "profileUrl", "linkedin", "email", "website", "semantic_summary",
        "source", "first_seen", "last_seen", "status",
        "financial_score", "financial_tier", "icp_score", "icp_tier",
    ]

    with open(master_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for handle in sorted(existing.keys()):
            writer.writerow(existing[handle])

    return updated


def email_weekly_report(csv_path: Path, tenant: str, config: dict, row_count: int, dry_run: bool = False):
    """Email the weekly CSV to Florian."""
    display_name = config.get("display_name", tenant)
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    subject = f"[Weekly Report] {display_name} — {week_start} to {week_end} ({row_count} events)"

    html_body = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2>Weekly Report: {display_name}</h2>
<p>Period: {week_start} to {week_end}<br>
Total events: {row_count}</p>
<p>The weekly activity CSV is attached below.</p>
<p>CSV saved at: <code>{csv_path.name}</code></p>
<p style="color: #888; font-size: 12px;">Skool Intelligence v2 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
</body></html>
"""

    florian_email = config.get("alerts", {}).get("florian", {}).get("email", "you@example.com")

    if dry_run:
        print(f"\n[DRY RUN] Would email weekly report to {florian_email}")
        print(f"  Subject: {subject}")
        print(f"  CSV: {csv_path} ({row_count} events)")
        return

    try:
        from email_notifier import send_html_email
        result = send_html_email(florian_email, subject, html_body, from_name="Skool Intelligence")
        print(f"  Report email: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"  Report email error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Skool Weekly Report v2")
    parser.add_argument("--tenant", required=True, help="Tenant slug")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--days", type=int, default=7, help="Days to include (default: 7)")
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"\nSkool Weekly Report v2")
    print(f"Tenant: {args.tenant}")
    print(f"Period: last {args.days} days")
    print(f"Mode:   {'DRY RUN' if args.dry_run else 'LIVE'}")

    # Load run logs
    logs = load_run_logs_for_period(state_dir, days=args.days)
    print(f"\nFound {len(logs)} run logs in the past {args.days} days")

    # Generate weekly CSV
    weekly_dir = state_dir / "weekly"
    week_label = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    csv_path = weekly_dir / f"week_{week_label}.csv"

    row_count = generate_weekly_csv(logs, csv_path)
    print(f"Weekly CSV: {csv_path.name} ({row_count} events)")

    # Update master CSV
    updated = update_master_csv(state_dir, logs)
    print(f"Master CSV: {updated} members updated")

    # Email report
    email_weekly_report(csv_path, args.tenant, config, row_count, dry_run=args.dry_run)

    print(f"\nWeekly report complete.")


if __name__ == "__main__":
    main()
