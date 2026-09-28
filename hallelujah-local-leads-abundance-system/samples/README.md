# Sample Output

These are anonymized samples from real production runs, showing the data quality and structure you can expect from each pillar.

## Files

| File | Source | Records | What It Shows |
|------|--------|---------|---------------|
| `chamber_output.json` | Chamber scraper | 8 members | GrowthZone directory data with ICP tiers, LinkedIn, contacts |
| `bni_output.json` | BNI scraper | 5 members | BNI chapter data with 92% LinkedIn hit rate |
| `magazine_output.json` | Magazine pipeline | 5 advertisers | Issuu ad detection + enrichment with owner, email, meta |
| `enrichment_output.json` | Enrichment engine | 5 leads | Full waterfall enrichment result |
| `stats.json` | Production metrics | - | Aggregate numbers from 40,000+ businesses |

## Data Quality

All samples reflect real production patterns:
- **ICP tiers** are classified by keyword matching on category
- **LinkedIn URLs** are validated (person name tokens in slug)
- **Emails** are SMTP-verified (safe/risky/invalid status)
- **Appearance counts** (magazine) show repeat advertisers across issues
