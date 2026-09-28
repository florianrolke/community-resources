# Reddit FAQ Enrichment

The Reddit workflow is for market-language research. The point is not to imitate Reddit answers. The point is to capture exact question wording from real people, then answer those questions in the site owner's voice.

## Dry Run

```bash
python scripts/reddit_question_mining.py research --topic "AI agency first client" --slug ai-agency-first-client --dry-run
```

Dry run prints the plan and does not spend credits.

## Live Run

```bash
python scripts/reddit_question_mining.py research --topic "AI agency first client" --slug ai-agency-first-client --live --max-results 25
```

Outputs:

- Raw Apify result data in `.tmp/reddit-question-mining/<slug>/`.
- Question candidates as JSON.
- Selected FAQ research notes under `theme-notes/reddit-faq-research/`.

## Best Practice

- Keep Reddit question wording exact when it is clean.
- Do not copy Reddit answers.
- Answer in your own voice.
- Prefer adjacent questions over repeated versions of the article headline.
- Keep FAQs visible on-page before adding FAQ schema.

