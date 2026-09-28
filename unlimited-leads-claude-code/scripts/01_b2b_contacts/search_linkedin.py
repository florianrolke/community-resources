#!/usr/bin/env python3
"""
SYSTEM 1 — Find B2B contacts by searching LinkedIn directly.

Why this exists instead of the course's actor
---------------------------------------------
The course used `code_crafter/leads-finder`, an "Apollo/ZoomInfo alternative"
that queries a scraped contact database. That whole category has aged badly —
on Apify today those actors sit at 2.1 to 3.9 stars, and the complaints are all
the same: stale records, bounced emails, people who left two jobs ago.

`harvestapi/linkedin-profile-search` searches LinkedIn itself, live, and rates
4.8. You're reading profiles as they exist right now rather than a copy someone
took months ago.

It also hands you the thing the course spent an entire AI agent trying to find.
The video's research step exists to dig up a "trigger event" — something that
recently changed, so your opener isn't generic. This actor has that as a filter:

    --recently-changed-jobs      people who just started a new role
    --recently-posted            people active on LinkedIn right now

Filter on those and every lead arrives with a trigger event already attached.

Before you run this: it needs a paid Apify plan
-----------------------------------------------
This actor allows free Apify accounts **10 runs total**, then returns nothing.
If you're on the free plan and just want leads today, use System 2 (Google Maps
has no such cap) or System 3 (no Apify account at all). Both are cheaper anyway.

The video's original actor is still here, but it has its own first-run step:
Apify makes you approve full-account permissions for it in the browser once.

    python -X utf8 scripts/01_b2b_contacts/scrape_apify.py --help

Usage
-----
    # Cheapest: names, titles, companies, profile URLs
    python -X utf8 scripts/01_b2b_contacts/search_linkedin.py \\
        --titles "Owner" "Founder" --locations "Alabama" --limit 25 \\
        --out-csv output/leads.csv

    # With emails, and only people who just changed jobs
    python -X utf8 scripts/01_b2b_contacts/search_linkedin.py \\
        --titles "Marketing Director" --locations "United States" \\
        --headcount "51-200" --recently-changed-jobs \\
        --mode email --limit 50 --out-csv output/warm_leads.csv

Cost: about $0.004 per profile in short mode, $0.014 with email lookup.
Always run a 25-profile test first and check the results are actually your ICP.
"""

import os
import sys
import json
import argparse
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.env import load_env, require
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import write_csv, write_json

fix_encoding()
load_env()

from apify_client import ApifyClient

ACTOR_ID = "harvestapi/linkedin-profile-search"

# What you get, and roughly what it costs per profile.
MODES = {
    "short": "Short",                  # name, title, company, URL   ~$0.004
    "full": "Full",                    # + experience, education      ~$0.008
    "email": "Full + email search",    # + email address              ~$0.014
}


def search_linkedin(
    query: str = None,
    titles: list[str] | None = None,
    locations: list[str] | None = None,
    companies: list[str] | None = None,
    headcount: list[str] | None = None,
    industries: list[str] | None = None,
    limit: int = 25,
    mode: str = "short",
    recently_changed_jobs: bool = False,
    recently_posted: bool = False,
    exclude_titles: list[str] | None = None,
) -> list[dict]:
    """Search LinkedIn profiles and return them as a list of dicts."""
    api_token = require(
        "APIFY_API_TOKEN",
        hint="Get one at https://console.apify.com -> Settings -> API & Integrations",
    )
    client = ApifyClient(api_token)

    if not any([query, titles, companies, industries]):
        print(
            "Error: give the search something to go on — at least one of\n"
            "  --query, --titles, --companies, or --industries",
            file=sys.stderr,
        )
        sys.exit(1)

    run_input: dict = {
        "profileScraperMode": MODES.get(mode, MODES["short"]),
        "maxItems": int(limit),
    }
    if query:
        run_input["searchQuery"] = query
    if titles:
        run_input["currentJobTitles"] = titles
    if locations:
        run_input["locations"] = locations
    if companies:
        run_input["currentCompanies"] = companies
    if headcount:
        run_input["companyHeadcount"] = headcount
    if industries:
        run_input["industryIds"] = industries
    if exclude_titles:
        run_input["excludeCurrentJobTitles"] = exclude_titles
    if recently_changed_jobs:
        run_input["recentlyChangedJobs"] = True
    if recently_posted:
        run_input["recentlyPostedOnLinkedIn"] = True

    per_profile = {"short": 0.004, "full": 0.008, "email": 0.014}[mode]
    print(f"Searching LinkedIn ({mode} mode, limit {limit})...")
    print(f"Estimated cost: ~${limit * per_profile:.2f}")
    print(f"Filters: {json.dumps({k: v for k, v in run_input.items() if k != 'profileScraperMode'}, indent=2)}")

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception as e:
        print(f"Error running actor: {e}", file=sys.stderr)
        return []

    if not run:
        print("Error: actor run failed to start", file=sys.stderr)
        return []

    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    # An actor can report SUCCEEDED and still hand back nothing, because a plan
    # limit stopped it before it did any work. Without this check the caller sees
    # "0 profiles" and goes off tuning filters that were never the problem.
    if not results:
        msg = (run.get("statusMessage") or "").lower()
        if "run limit" in msg or "upgrade" in msg or "limit reached" in msg:
            print(
                "\n" + "=" * 68 + "\n"
                "This actor caps free Apify accounts at 10 runs, and yours has\n"
                "reached it. Your filters are fine — the run never started.\n\n"
                "Three ways forward:\n"
                "  1. Use System 2 instead. Google Maps has no such cap and works\n"
                "     on the free plan:\n"
                "     python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \\\n"
                '         --search "roofers in Mobile AL" --limit 10 --contacts\n\n'
                "  2. Use System 3. Free, no Apify account needed at all:\n"
                '     python -X utf8 scripts/03_free_scraping/build_dorks.py --niche "roofer"\n\n'
                "  3. Upgrade Apify (from $39/mo) if you want LinkedIn search specifically.\n"
                + "=" * 68,
                file=sys.stderr,
            )
            return []
        if msg:
            print(f"\nThe actor finished but returned nothing. It reported: {run.get('statusMessage')}",
                  file=sys.stderr)

    print(f"Found {len(results)} profiles")
    return results


def normalize(profiles: list[dict]) -> list[dict]:
    """
    Flatten LinkedIn profiles into this repo's standard lead shape, so the
    research and outreach steps can read them without special-casing.
    """
    out = []
    for p in profiles:
        exp = (p.get("experience") or [{}])
        current = exp[0] if exp else {}
        company = p.get("currentCompany") or current.get("companyName") or ""
        if isinstance(company, dict):
            company = company.get("name", "")

        out.append({
            "first_name": p.get("firstName", ""),
            "last_name": p.get("lastName", ""),
            "name": f"{p.get('firstName','')} {p.get('lastName','')}".strip(),
            "job_title": p.get("headline") or current.get("position") or "",
            "company": company,
            "company_website": p.get("companyWebsite") or "",
            "email": p.get("email") or "",
            "linkedin": p.get("linkedinUrl") or p.get("publicIdentifier") or "",
            "location": p.get("location", {}).get("linkedinText", "") if isinstance(p.get("location"), dict) else (p.get("location") or ""),
            "headline": p.get("headline", ""),
            "company_description": p.get("about") or "",
            "_source": "linkedin-search",
        })
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Find B2B contacts by searching LinkedIn (System 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tip: run 25 first and read the results before scaling up. If fewer than 20 of
them are the kind of person you meant, fix your filters — don't scrape 1,000
of the wrong people faster.
        """,
    )
    parser.add_argument("--query", help="Free-text search (e.g. 'Founder')")
    parser.add_argument("--titles", nargs="+", help='Job titles, e.g. --titles Owner Founder "General Manager"')
    parser.add_argument("--locations", nargs="+", help='Locations, e.g. --locations "Alabama" "Georgia"')
    parser.add_argument("--companies", nargs="+", help="Current companies")
    parser.add_argument("--headcount", nargs="+", help='Company size bands, e.g. --headcount "11-50" "51-200"')
    parser.add_argument("--industries", nargs="+", help="LinkedIn industry IDs")
    parser.add_argument("--exclude-titles", dest="exclude_titles", nargs="+", help="Job titles to exclude")
    parser.add_argument("--recently-changed-jobs", dest="recently_changed_jobs", action="store_true",
                        help="Only people who recently started a new role (built-in trigger event)")
    parser.add_argument("--recently-posted", dest="recently_posted", action="store_true",
                        help="Only people who recently posted on LinkedIn (they're active)")
    parser.add_argument("--limit", type=int, default=25, help="Max profiles (default: 25)")
    parser.add_argument("--mode", choices=list(MODES.keys()), default="short",
                        help="short = cheapest, full = + experience, email = + email address")
    parser.add_argument("--output", help="Output JSON path (default: output/linkedin_TIMESTAMP.json)")
    parser.add_argument("--out-csv", dest="out_csv", help="Also write a CSV here")
    parser.add_argument("--raw", action="store_true", help="Keep the actor's raw fields instead of normalizing")

    args = parser.parse_args()

    profiles = search_linkedin(
        query=args.query, titles=args.titles, locations=args.locations,
        companies=args.companies, headcount=args.headcount, industries=args.industries,
        limit=args.limit, mode=args.mode,
        recently_changed_jobs=args.recently_changed_jobs,
        recently_posted=args.recently_posted,
        exclude_titles=args.exclude_titles,
    )

    if not profiles:
        print("No profiles found. Try broadening your filters.")
        sys.exit(1)

    records = profiles if args.raw else normalize(profiles)

    out = args.output or f"output/linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    write_json(records, out)
    print(f"Saved to {out}")
    if args.out_csv:
        write_csv(records, args.out_csv)
        print(f"CSV saved to {args.out_csv}")

    print("\nNext: research each lead ->")
    print(f"  python -X utf8 scripts/01_b2b_contacts/research_lead.py --input {out}")


if __name__ == "__main__":
    main()
