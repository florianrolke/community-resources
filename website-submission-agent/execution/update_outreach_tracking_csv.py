#!/usr/bin/env python3
"""Merge website submission results back into a lead tracking CSV.

This keeps the source lead list auditable without overwriting it by default.
It matches rows by normalized website domain and adds outreach tracking columns:

- outreach_status
- reached_out
- needs_retry
- retry_reason
- last_contact_url
- last_submission_timestamp
- screenshot_before
- screenshot_after
- extracted_emails
- extracted_phones
- extracted_notes
- calendar_links
"""

import argparse
import csv
from pathlib import Path
from urllib.parse import urlparse


REACHED_STATUSES = {
    "confirmed",
    "submitted",
    "submitted_enter",
    "submitted_unconfirmed",
}

RETRY_STATUSES = {
    "failed_validation",
    "missing_required",
    "no_fillable_fields",
    "captcha_failed",
    "load_error",
    "submit_error",
    "no_submit_button",
    "detection_error",
}

MANUAL_REVIEW_STATUSES = {
    "mailto_only",
    "no_contact_page",
    "no_form",
    "checkout_or_payment_page",
    "page_prefilter_rejected",
    "lead_prefilter_rejected",
}

TRACKING_COLUMNS = [
    "outreach_status",
    "reached_out",
    "needs_retry",
    "retry_reason",
    "last_contact_url",
    "last_submission_timestamp",
    "last_screenshot_before",
    "last_screenshot_after",
    "extracted_emails",
    "extracted_phones",
    "extracted_notes",
    "calendar_links",
]


def normalize_domain(url):
    if not url:
        return ""
    url = str(url).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_latest_results(paths):
    latest = {}
    for path in paths:
        for row in read_csv(path):
            domain = normalize_domain(row.get("website") or row.get("url"))
            if not domain:
                domain = normalize_domain(row.get("contact_url"))
            if not domain:
                continue
            latest[domain] = row
    return latest


def classify_result(row):
    status = (row.get("status") or row.get("retry_status") or "").strip()
    reached = status in REACHED_STATUSES
    retry = status in RETRY_STATUSES
    if status in MANUAL_REVIEW_STATUSES:
        retry = False
    retry_reason = ""
    if retry:
        retry_reason = row.get("note") or row.get("error") or row.get("confirmation_match") or status
    return reached, retry, retry_reason


def merge_tracking(source_rows, result_by_domain):
    output = []
    matched = 0
    for row in source_rows:
        domain = normalize_domain(row.get("website") or row.get("url"))
        result = result_by_domain.get(domain)
        merged = dict(row)

        for col in TRACKING_COLUMNS:
            merged.setdefault(col, "")

        if result:
            matched += 1
            status = result.get("status") or result.get("retry_status") or ""
            reached, needs_retry, retry_reason = classify_result(result)
            merged.update({
                "outreach_status": status,
                "reached_out": "TRUE" if reached else "FALSE",
                "needs_retry": "TRUE" if needs_retry else "FALSE",
                "retry_reason": retry_reason,
                "last_contact_url": result.get("contact_url", ""),
                "last_submission_timestamp": result.get("timestamp", ""),
                "last_screenshot_before": result.get("screenshot_before", ""),
                "last_screenshot_after": result.get("screenshot_after", ""),
                "extracted_emails": result.get("extracted_emails", ""),
                "extracted_phones": result.get("extracted_phones", ""),
                "extracted_notes": result.get("extracted_notes", ""),
                "calendar_links": result.get("calendar_links", "") or result.get("calendar_link", ""),
            })
        else:
            merged["outreach_status"] = merged.get("outreach_status") or "not_attempted"
            merged["reached_out"] = merged.get("reached_out") or "FALSE"
            merged["needs_retry"] = merged.get("needs_retry") or "FALSE"

        output.append(merged)

    return output, matched


def write_csv(path, rows, source_fieldnames):
    fieldnames = list(source_fieldnames)
    for col in TRACKING_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Update outreach tracking columns in a lead CSV from result CSVs")
    parser.add_argument("--source-csv", required=True, help="Original lead CSV to annotate")
    parser.add_argument("--results-csv", required=True, nargs="+", help="One or more website submission result CSVs")
    parser.add_argument("--output-csv", help="Annotated output CSV. Defaults to <source>_with_outreach_status.csv")
    args = parser.parse_args()

    source_path = Path(args.source_csv)
    output_path = Path(args.output_csv) if args.output_csv else source_path.with_name(
        f"{source_path.stem}_with_outreach_status{source_path.suffix}"
    )

    source_rows = read_csv(source_path)
    with open(source_path, "r", encoding="utf-8-sig", newline="") as f:
        source_fieldnames = csv.DictReader(f).fieldnames or []

    result_by_domain = load_latest_results([Path(p) for p in args.results_csv])
    merged, matched = merge_tracking(source_rows, result_by_domain)
    write_csv(output_path, merged, source_fieldnames)

    reached = sum(1 for row in merged if row.get("reached_out") == "TRUE")
    retry = sum(1 for row in merged if row.get("needs_retry") == "TRUE")
    attempted = sum(1 for row in merged if row.get("outreach_status") not in ("", "not_attempted"))

    print(f"Source rows: {len(source_rows)}")
    print(f"Matched result domains: {matched}")
    print(f"Attempted rows: {attempted}")
    print(f"Reached out: {reached}")
    print(f"Needs retry: {retry}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
