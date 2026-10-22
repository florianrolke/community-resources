# AEO Blog Resources and Template

Florian Rolke's reusable AEO blog workflow and static-site engine, adapted for a new niche without client-specific content. This folder contains the actual resources. No access to another repository is required.

Start with the [AEO workflow](docs/aeo-workflow.md). For the code, follow the quick start below. The same frontmatter FAQ data generates the visible answers and FAQ structured data.

## Included

- Markdown-to-HTML blog builder with question-based guides and section hubs.
- Configurable branding, author, canonical domain, navigation, entity information, and calls to action.
- Article, BreadcrumbList, optional Person/entity, and FAQ structured data.
- Sitemap, robots.txt, optional llms.txt, related links, and draft/future-date publishing gates.
- Competitor analysis, Apify question research, staged FAQ enrichment, and publication scheduling.
- A fictional example, [article template](docs/article-template.md), [ranking checklist](docs/ranking-checklist.md), and [agent instructions](SKILL.md).

The local build works offline without API keys. Optional research tools can incur provider charges; they are separate from building the site. No client articles, contact information, credentials, or client Git history are included.

## Quick start

```text
git clone https://github.com/florianrolke/community-resources.git
cd community-resources/aeo-blog-template
python -m venv .venv
```

Activate the environment: `.venv\Scripts\activate` on Windows, or `source .venv/bin/activate` on macOS/Linux. Then:

```text
python -m pip install -r execution/requirements.txt
python execution/build_site.py
python -m http.server 8000 --directory public
```

Open http://localhost:8000. Edit `site.config.json` and the Markdown under `content/`, then rebuild. The sample uses a fictional bicycle workshop and the reserved domain `https://example.com`; replace both before publishing. Do not describe the example as a real business or its content as verified field experience.

To include draft and future pages locally:

```text
python execution/build_site.py --include-drafts
python -m http.server 8001 --directory preview
```

Preview output is separate from production output. The builder replaces only its generated `public/` or `preview/` directory.

Run the offline checks with `python -m unittest discover -s tests -v`. They verify draft and date gates, production/preview separation, FAQ escaping and schema, output-directory protection, and research opt-in behavior.

## Research and writing

```text
python execution/analyze_competitor.py example.org --sample 3
python execution/discover_topics.py
python execution/enrich_faqs.py --all --dry-run
python execution/schedule_drip.py --start 2026-11-03 --days 1,4
```

Competitor analysis fetches the requested public site. Topic discovery and FAQ enrichment do not call paid services without `--live`. Configure your own `.env` from `.env.example` and install `execution/requirements-research.txt` for live FAQ enrichment. Set `FAQ_MODEL` to a model currently available from your chosen provider. Never include private source material in an API request without permission.

Review staged FAQs and verify facts before applying them. Research tools are helpers, not sources of business credentials, testimonials, or outcomes. See [research setup](docs/research-setup.md) and [publishing](docs/publishing.md).

## What this does not promise

Readable content and valid markup do not guarantee indexing, AI citations, rankings, or leads. Google does not require special AI text files or special schema for AI Overviews or AI Mode. FAQ markup is optional semantic data, not a promise of a Google rich result. Keep structured data consistent with what visitors can read.

- https://developers.google.com/search/docs/appearance/ai-features
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content

Do not add an MCP server just to obtain an audit score. Add one when the site offers a useful function for an agent.
