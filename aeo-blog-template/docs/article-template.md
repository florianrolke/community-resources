# Article template

Create a Markdown file under `content/guides/`. Use a descriptive filename and an existing hub. Change every example before publishing.

```yaml
---
title: What should a reader know before choosing this service?
description: A specific summary of the decision this article helps with.
primaryQuestion: What should a reader know before choosing this service?
draft: true
related:
  - /guides/prepare-for-service/
faqs:
  - q: What should I ask before booking?
    a: Ask what is included, how estimates are provided, and how additional work is approved. Confirm the actual provider's terms before relying on them.
---
```

Below the frontmatter, add one H1, a direct answer, useful question headings, supported detail, and sources where relevant. Replace the example related link with the correct page for your niche. Remove `draft: true` only after review; use `publishDate: YYYY-MM-DD` for a scheduled release. Use `dateModified` only after a genuine editorial change.

The output escapes FAQ text rather than rendering Markdown inside FAQ answers. Keep answers in plain text so the visible text and schema describe the same answer.
