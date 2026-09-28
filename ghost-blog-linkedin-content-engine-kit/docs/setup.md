# Setup

## 1. Create A Ghost Admin Integration

In Ghost Admin:

1. Go to Settings.
2. Open Integrations.
3. Add a custom integration.
4. Copy the Admin API key.
5. Add `GHOST_URL` and `GHOST_ADMIN_API_KEY` to `.env`.

The Admin API key must look like:

```text
key_id:key_secret
```

## 2. Install Python Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Configure The Site

Copy `.env.example` to `.env`, then set:

- `GHOST_URL`
- `GHOST_ADMIN_API_KEY`
- `SITE_NAME`
- `SITE_AUTHOR_NAME`
- `APIFY_API_TOKEN` if using YouTube or Reddit actors
- `OPENROUTER_API_KEY` if using LLM headline/article generation
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` if using internal graph enrichment

## 4. Configure CTA Copy

Copy `theme-assets/blog-cta-config.example.json` to `theme-assets/blog-cta-config.json`.

Update the labels and URLs once. The YouTube and community pipelines read this file so CTA copy can be changed across future posts without rewriting every script.

## 5. Verify Ghost Access

```bash
python scripts/ghost_client.py list-posts --limit 5
```

If this fails, check:

- `GHOST_URL` includes `https://`.
- The Admin API key came from a custom integration, not a Content API key.
- The Ghost site is reachable from your machine.

## 6. Optional: Configure LinkedIn Publishing

If you want each approved Ghost post to become a LinkedIn post from the CLI or IDE, configure the native LinkedIn publisher:

- `linkedin-setup/README.md`
- `linkedin-setup/coolify.md`
- `linkedin-setup/docker.md`
- `linkedin-setup/cli-workflow.md`
