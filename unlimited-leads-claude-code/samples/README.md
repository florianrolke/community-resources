# Samples

Every record here is **invented**. The businesses don't exist, the domains are
`example.com`, and the phone numbers are in the 555-01xx range reserved for
fiction. Nothing scraped, nobody real.

They're here so you can see the shape of each stage before spending anything, and
so you can test the parsing scripts offline.

| File | Stage |
|---|---|
| `leads_b2b_sample.json` | System 1 output — straight from LinkedIn search |
| `leads_researched_sample.json` | After `research_lead.py` — five facts, each sourced |
| `outreach_output_sample.csv` | After `write_outreach.py` — ready to send |
| `gmaps_sample.csv` / `.json` | System 2 output, with AI summary and facts |
| `instant_data_scraper_export.csv` | System 3 — a raw browser-extension export |

## Two worth looking at properly

**`leads_researched_sample.json`** — the third lead has `facts_found: 0` and
`needs_research: true`. That's the designed behavior, not a failure. Research
found nothing true to say about them.

**`outreach_output_sample.csv`** — and so that same lead has empty email columns
and `outreach_status: skipped: no research facts`. The system would rather send
nothing than invent a trigger event. Check that column before you send anything.

## Run something offline

The System 3 parser works on the sample with no keys and no cost:

```bash
python -X utf8 scripts/03_free_scraping/parse_scraper_export.py     --input samples/instant_data_scraper_export.csv     --out-csv output/test.csv
```

Four messy rows in, three contacts out. It drops the Instagram login page,
recovers `hello (at) sawtoothbarbers (dot) com` into a real address, and pulls a
phone number out of a sentence.
