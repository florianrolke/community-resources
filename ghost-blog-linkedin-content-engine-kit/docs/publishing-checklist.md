# Publishing Checklist

Use this before a real post goes live.

## URL

- Explicit `--slug`.
- Lowercase and hyphenated.
- No random UUID.
- No year unless this is an annual guide.

## Article Structure

- Clear title answering one intent.
- BLUF/direct answer at the top.
- Short table of contents.
- Descriptive H2s.
- Visible section FAQs where helpful.
- Full FAQ block near the bottom.
- Related links or glossary links.
- Sources and CTA.

## Metadata

- `--excerpt`
- `--meta-title`
- `--meta-description`
- `--tags`
- Feature image and alt text if using images.

## Ghost Command

```bash
python scripts/ghost_client.py create "Post Title" content-drafts/post-file.html --slug post-title-keyword-slug --excerpt "One sentence summary." --meta-title "SEO title under about 60 characters" --meta-description "Search description under about 155 characters." --tags "Content Strategy,AEO" --html-card --code-head-file theme-assets/guided-reading-head.html --code-foot-file theme-assets/guided-reading-foot.html
```

Add `--publish` only after review:

```bash
python scripts/ghost_client.py create "Post Title" content-drafts/post-file.html --slug post-title-keyword-slug --excerpt "One sentence summary." --meta-title "SEO title under about 60 characters" --meta-description "Search description under about 155 characters." --tags "Content Strategy,AEO" --html-card --code-head-file theme-assets/guided-reading-head.html --code-foot-file theme-assets/guided-reading-foot.html --publish
```

## After Publishing

- Confirm the live URL returns `200`.
- Submit sitemap in Google Search Console and Bing Webmaster Tools.
- Request indexing manually for important early posts.
- Create the LinkedIn repurposing draft:

```bash
python scripts/ghost_to_linkedin.py --slug post-title-keyword-slug --review-only
```

- Dry-run the LinkedIn payload:

```bash
python scripts/ghost_to_linkedin.py --slug post-title-keyword-slug --dry-run
```

- Publish to LinkedIn only after approval:

```bash
python scripts/ghost_to_linkedin.py --slug post-title-keyword-slug --publish-now
```

- Add the post to a maintenance ledger with next review date.
