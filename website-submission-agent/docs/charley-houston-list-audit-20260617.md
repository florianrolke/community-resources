# Charley Houston List Audit - 2026-06-17

Purpose: identify remaining Houston plumbing/HVAC/contact-form outreach lists
after the first Charley website submission production run.

## Already Exhausted

Primary Google Maps Houston home-services source:

`CLIENTS/clients/vincent-sims/houston/leads/houston_home_services_gmaps.csv`

Summary:

- 2,000 rows
- 1,436 unique website domains
- 1,436/1,436 domains already processed in
  `data/vincent-charley-first-1500-tracking-20260616.csv`

This is the source behind the first 1,436-domain Charley run. Do not rerun it
as a fresh source unless new rows are added.

## Current Saved Progress

Resume note:

`docs/charley-website-submission-resume-20260617.md`

Short-path restore package:

`C:\tmp\charley-website-submission-resume-20260617`

Latest master tracking:

`data/vincent-charley-first-1500-tracking-20260616.csv`

Rows processed: 1,436

Reached out: 443

Retry batch 1 final:

`data/vincent-charley-retry-backlog-batch-1-final-tracking-20260617.csv`

Rows retried: 100

Reached out after recovery: 26

## Additional Houston Sources Found

Dedicated Houston client folder:

`CLIENTS/clients/vincent-sims/houston/leads/`

Files audited:

- `houston_home_services_enriched.csv`
- `houston_home_services_scored.csv`
- `vincent_sims_chamber_contacts_gmaps_enriched.csv`
- `vincent_sims_chamber_leads.csv`
- `houston_all_contacts.csv`

Raw additional unprocessed candidate audit:

`data/charley-houston-additional-unprocessed-candidates-audit-20260617.csv`

This audit found 60 combined likely service-company domains that were not in
the first 1,436-domain run, but several were low-quality chamber/directory/media
false positives.

Strict queue created for the next Charley website-form run:

`data/charley-houston-additional-strict-queue-20260617.csv`

Strict queue size: 29 domains

Use this as the next fresh Charley source before generating new scrapes.

## Source Quality Notes

Best additional sources:

- `vincent_sims_chamber_contacts_gmaps_enriched.csv`
- `vincent_sims_chamber_leads.csv`
- `houston_home_services_enriched.csv`

Use with filtering. These contain good Houston-area plumbing/HVAC companies,
but also chamber pages, article pages, suppliers, colleges, directories, and
other false positives.

Lower priority:

- `houston_all_contacts.csv` - broad chamber file; many non-ICP companies and
  many missing websites.
- `houston_tier_a_prospects.csv` - useful for other outreach, but not for
  website-form submission because it has no website column.
- `CLIENTS/joya_national_leads/hvac.csv` - national HVAC file. It has a small
  Houston/Katy-looking subset, but it is not a clean Houston-specific source.
- `CLIENTS/joya_national_leads/ALL_national.csv` - not recommended for this
  task because location matching creates many false positives.

## Recommended Next Order

1. Run `data/charley-houston-additional-strict-queue-20260617.csv`.
2. If more volume is needed, manually review the broader 60-domain audit file
   and rescue any legitimate plumbing/HVAC domains.
3. Only after that, create a new Google Maps scrape for additional Houston
   search terms, surrounding cities, or association/member lists.
4. Keep retry work separate from fresh-source work so reached-out accounting
   stays clean.

## Candidate Next Scrape Ideas

If we need more Charley volume after the 29-domain strict queue:

- PHCC/TACCA member directories if accessible
- Greater Houston plumbers
- Greater Houston HVAC contractors
- Katy plumbing/HVAC
- Cypress plumbing/HVAC
- The Woodlands plumbing/HVAC
- Conroe plumbing/HVAC
- Pasadena plumbing/HVAC
- League City plumbing/HVAC
- Galveston plumbing/HVAC
- Fort Bend/Richmond/Rosenberg plumbing/HVAC

Deduplicate every new scrape against
`data/vincent-charley-first-1500-tracking-20260616.csv` before submitting.
