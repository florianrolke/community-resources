# Ghost Blog To LinkedIn CLI Workflow

This workflow lets the Ghost blog setup automatically create and publish a LinkedIn post from an existing Ghost post.

## Required Local Variables

Your local `.env` needs Ghost access so the pipeline can fetch the post:

```text
GHOST_URL=https://your-ghost-blog.example.com
GHOST_ADMIN_API_KEY=your_admin_key_id:your_admin_secret
```

If you publish through a hosted native LinkedIn service, also add:

```text
LINKEDIN_NATIVE_API_URL=https://linkedin-api.example.com
LINKEDIN_NATIVE_API_KEY=the same private key used by the hosted service
```

## Review First

```bash
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --review-only
```

This creates:

```text
social-drafts/linkedin/YYYY-MM-DD/your-ghost-post-slug.md
social-drafts/linkedin/YYYY-MM-DD/your-ghost-post-slug.json
```

## Dry Run The LinkedIn API Payload

```bash
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --dry-run
```

This calls the same publishing path without creating a live LinkedIn post.

## Publish Now

```bash
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --publish-now
```

The command:

1. Fetches the Ghost post by slug.
2. Extracts the post title, URL, body, and feature image.
3. Writes a shorter LinkedIn draft.
4. Uploads the public feature image to LinkedIn.
5. Publishes to the connected LinkedIn member profile.

## Two-Step Workflow

If you want manual approval between draft and publish:

```bash
python scripts/linkedin_post_pipeline.py draft-ghost --slug your-ghost-post-slug
python scripts/linkedin_post_pipeline.py print --draft-json social-drafts/linkedin/YYYY-MM-DD/your-ghost-post-slug.json
python scripts/linkedin_post_pipeline.py schedule --draft-json social-drafts/linkedin/YYYY-MM-DD/your-ghost-post-slug.json --provider native-hosted --when now --publish-now
```

## Notes

- Native LinkedIn publishing posts immediately. It does not schedule future times by itself.
- For scheduling, use an external scheduler to run the final command at the desired time, or plug the draft JSON into your preferred social scheduler.
- Hosted publishing needs public image URLs. Ghost feature images are public and work well.
- If you want to use a local image file, either upload it to Ghost first or run with `--provider native` on a machine that has the local OAuth token.

