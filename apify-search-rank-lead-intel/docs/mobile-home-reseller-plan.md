# Mobile Home Reseller Implementation Plan

This repo is generic, but this is the focused implementation plan for mobile home cash buyers and resellers.

## Target

Only include businesses that sell, buy, or broker mobile/manufactured/modular homes. Exclude general single-family cash buyers, real estate agents, apartment operators, and broad property managers unless their category/name/site clearly supports mobile or manufactured homes.

## Search Terms

- `mobile home dealer`
- `manufactured home dealer`
- `manufactured homes for sale`
- `mobile homes for sale`
- `mobile home buyer`
- `sell my mobile home`
- `modular home dealer`
- `park model homes dealer`

## Location Grid

Run city by city, county by county, and state by state:

- top metros first
- all counties second
- state-wide terms last for broad operators

## Output

Preserve:

- `input_query`
- `query_term`
- `query_location`
- `result_rank`
- `rank_bucket`
- `place_id`
- `business_name`
- `category_name`
- `phone`
- `website`
- `reseller_confidence`

Then enrich accepted reseller rows with the local maps enrichment package.

