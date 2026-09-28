# YouTube Repurposing Pipeline

The YouTube pipeline turns one video or a channel feed into Ghost-ready article drafts.

## One Video

```bash
python scripts/youtube_blog_pipeline.py from-url --url "https://www.youtube.com/watch?v=VIDEO_ID" --faq-dry-run
```

What it does:

- Gets the video ID and metadata.
- Fetches or prepares transcript content.
- Engineers headline candidates.
- Creates an answer-first article draft.
- Embeds the YouTube video.
- Adds transcript-derived FAQs.
- Optionally plans Neo4j and Reddit enrichment.

## Channel Run

```bash
python scripts/youtube_blog_pipeline.py run-channel --channel-url "https://www.youtube.com/@yourchannel/videos" --limit 5 --faq-dry-run
```

Use `--reddit-live` or `--faq-live` only when you are ready to spend Apify credits.

## Long-Form vs Shorts

The default threshold is 180 seconds. Long-form videos become blog draft candidates. Shorts are better treated as idea seeds unless you explicitly want short posts.

```bash
python scripts/youtube_blog_pipeline.py run-channel --long-form-threshold 180
```

## Headline Rules

The pipeline treats the headline as a strategic asset:

- One clear search intent.
- Specific outcome or decision.
- No vague curiosity gap when the article should answer directly.
- Evergreen slug unless the page is an annual guide.

