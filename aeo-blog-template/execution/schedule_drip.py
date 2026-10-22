"""Schedule queued blog posts to drip-publish twice a week.

Queued posts are content/*.md files with `draft: true` in frontmatter. This
assigns each one a `publishDate` on a 2x/week cadence (default Tue & Fri)
starting from a launch date, and removes the `draft` flag. The build then
includes each page on the first build on or after its publishDate (see the
drip gate in build_site.py / is_published). Configure a scheduled build and
deployment in your host if releases need to happen automatically.

Usage:
    python execution/schedule_drip.py --list                     # show queue + scheduled
    python execution/schedule_drip.py --start 2026-08-04         # dry-run preview
    python execution/schedule_drip.py --start 2026-08-04 --apply # write publishDates
    python execution/schedule_drip.py --start 2026-08-04 --days 1,4 --apply

--days uses Python weekday numbers: Mon=0 ... Sun=6. Default 1,4 = Tue & Fri.

Ordering: posts interleave across sections (a local page, then a topic, then
a local page...) so each week's content varies. Override per-file with an
integer `dripOrder` in frontmatter (lower publishes first).
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import frontmatter

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"


def load_drafts():
    """Return queued (draft) pages and already-scheduled pages."""
    drafts, scheduled = [], []
    for path in sorted(CONTENT.rglob("*.md")):
        post = frontmatter.load(path)
        m = post.metadata
        rel = path.relative_to(CONTENT)
        section = rel.parent.as_posix() if rel.parent.as_posix() != "." else ""
        rec = {"path": path, "section": section, "meta": m,
               "title": m.get("shortTitle", m.get("title", rel.stem)),
               "order": m.get("dripOrder", 999)}
        if m.get("draft"):
            drafts.append(rec)
        elif m.get("publishDate"):
            rec["publishDate"] = m["publishDate"]
            scheduled.append(rec)
    return drafts, scheduled


def interleave(drafts):
    """Round-robin across sections so consecutive posts vary; respect dripOrder."""
    by_section = defaultdict(list)
    for d in drafts:
        by_section[d["section"]].append(d)
    for s in by_section:
        by_section[s].sort(key=lambda d: (d["order"], d["path"].name))
    # sections cycled in a stable, sensible order
    order = ["guides"]
    sections = [s for s in order if s in by_section] + \
               [s for s in by_section if s not in order]
    out, i = [], 0
    remaining = sum(len(v) for v in by_section.values())
    while remaining:
        s = sections[i % len(sections)]
        if by_section[s]:
            out.append(by_section[s].pop(0))
            remaining -= 1
        i += 1
    return out


def drip_dates(start: date, days: list[int], count: int) -> list[date]:
    out, d = [], start
    while len(out) < count:
        if d.weekday() in days and d >= start:
            out.append(d)
        d += timedelta(days=1)
    return out


def main():
    ap = argparse.ArgumentParser(description="Drip-schedule queued posts 2x/week")
    ap.add_argument("--start", help="launch date YYYY-MM-DD (first publish day on/after this)")
    ap.add_argument("--days", default="1,4", help="weekday numbers Mon=0..Sun=6 (default 1,4 = Tue,Fri)")
    ap.add_argument("--apply", action="store_true", help="write publishDate into the files")
    ap.add_argument("--list", action="store_true", help="list the queue and exit")
    args = ap.parse_args()

    drafts, scheduled = load_drafts()

    if args.list or not args.start:
        print(f"QUEUED (draft, unscheduled): {len(drafts)}")
        for d in interleave(drafts):
            print(f"  [{d['section'] or 'root'}] {d['title']}")
        print(f"\nALREADY SCHEDULED: {len(scheduled)}")
        for s in sorted(scheduled, key=lambda x: str(x['publishDate'])):
            print(f"  {s['publishDate']}  [{s['section'] or 'root'}] {s['title']}")
        if not args.start:
            print("\nPass --start YYYY-MM-DD to schedule the queue.")
        return

    try:
        days = [int(x.strip()) for x in args.days.split(",") if x.strip()]
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError
    except ValueError:
        ap.error("--days must contain weekday numbers 0 through 6, for example 1,4")
    start = date.fromisoformat(args.start)
    ordered = interleave(drafts)
    if not ordered:
        print("No queued (draft) posts to schedule.")
        return
    dates = drip_dates(start, days, len(ordered))

    print(f"Scheduling {len(ordered)} posts, 2x/week from {start} (weekdays {days}):\n")
    for d, pub in zip(ordered, dates):
        print(f"  {pub}  [{d['section'] or 'root'}] {d['title']}")
        if args.apply:
            post = frontmatter.load(d["path"])
            post.metadata.pop("draft", None)
            post.metadata["publishDate"] = pub.isoformat()
            d["path"].write_text(frontmatter.dumps(post), encoding="utf-8")

    if args.apply:
        print(f"\nApplied publishDate to {len(ordered)} files. Rebuild + deploy, and the "
              f"next build includes each post once its date arrives. Automate rebuilds separately.")
    else:
        print(f"\nDry run. Re-run with --apply to write these dates.")


if __name__ == "__main__":
    main()
