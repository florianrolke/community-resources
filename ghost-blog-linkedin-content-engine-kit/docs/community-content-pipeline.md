# Community Content Pipeline

This workflow turns newsletters, community wins, masterclasses, case studies, and quote banks into redacted Ghost drafts.

## Redacted Community Win

```bash
python scripts/community_blog_pipeline.py from-file --source-file examples/community-win-source.md --title "How A Simple Website Offer Became A First-Client Win" --slug simple-website-offer-first-client-win --content-type win --redact "Member Name"
```

Supported `--content-type` values:

- `win`
- `case-study`
- `masterclass`
- `newsletter-update`
- `quote-bank`

## Quote Bank

Set `QUOTE_BANK_ROOT` in `.env`, or place files under:

```text
quote-bank/runs/<run-name>/quote_candidates.jsonl
```

Each JSONL row can include:

- `quote_id`
- `quote_text`
- `speaker`
- `meeting_title`
- `context_summary`
- `quote_category`
- `score`
- `source_path`

Run:

```bash
python scripts/community_blog_pipeline.py from-quote-bank --query "first client" --title "The First Client Pattern" --slug first-client-pattern --limit 5
```

## Privacy Rules

- Redact names unless you have permission.
- Preserve business facts only when they cannot identify the person.
- Keep raw source notes internal.
- Publish the lesson, not the private community context.

