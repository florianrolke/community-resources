# Ghost Content Engine Kit

A public-ready starter kit for self-hosted Ghost blogs that turn source material into SEO/AEO-friendly posts.

It includes:

- Ghost Admin API publishing.
- YouTube-to-blog repurposing with embedded videos.
- Reddit exact-question FAQ mining through Apify.
- Optional Neo4j enrichment from your own meeting/community/content graph.
- Community win, case-study, masterclass, newsletter, and quote-bank draft workflows.
- Native LinkedIn repurposing through LinkedIn's official OAuth and Share API.
- Ghost HTML-card article styling that keeps important content visible in real HTML.
- A reusable CTA config so calls to action can be changed centrally.

## Why This Exists

Most creators and operators have better source material than they realize: calls, meetings, wins, comments, YouTube videos, newsletters, and community discussions. This kit turns those inputs into a repeatable Ghost publishing workflow:

1. Start with a real source.
2. Generate an answer-first article draft.
3. Enrich it with internal context from Neo4j when available.
4. Add exact-market FAQ wording from Reddit.
5. Publish to Ghost with clean slugs, metadata, visible FAQs, and a maintenance log.

## Quick Start

```bash
git clone https://github.com/Florian1995-ai/ghost-blog-linkedin-content-engine-kit.git
cd ghost-blog-linkedin-content-engine-kit
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your Ghost URL and Admin API key.

Test Ghost access:

```bash
python scripts/ghost_client.py list-posts --limit 5
```

Create a styled Ghost draft from a local HTML file:

```bash
python scripts/ghost_client.py create "My First Ghost Engine Post" content-drafts/my-post.html --slug my-first-ghost-engine-post --excerpt "One sentence summary." --meta-title "My First Ghost Engine Post" --meta-description "A clear search description." --tags "Content Strategy,AEO" --html-card --code-head-file theme-assets/guided-reading-head.html --code-foot-file theme-assets/guided-reading-foot.html
```

## Main Workflows

Create a blog draft from one YouTube URL:

```bash
python scripts/youtube_blog_pipeline.py from-url --url "https://www.youtube.com/watch?v=VIDEO_ID" --faq-dry-run
```

Mine Reddit questions for a topic:

```bash
python scripts/reddit_question_mining.py research --topic "AI agency first client" --slug ai-agency-first-client --dry-run
```

Run live Reddit mining through Apify:

```bash
python scripts/reddit_question_mining.py research --topic "AI agency first client" --slug ai-agency-first-client --live --max-results 25
```

Mine internal FAQ/story candidates from Neo4j:

```bash
python scripts/neo4j_question_mining.py research --topic "AI agency first client" --slug ai-agency-first-client --max-nodes 500
```

Merge Neo4j and Reddit FAQ enrichment:

```bash
python scripts/faq_enrichment_pipeline.py enrich --topic "AI agency first client" --slug ai-agency-first-client --seed-file content-drafts/ai-agency-first-client.html --graph-live --reddit-live --reddit-count 10 --graph-count 8
```

Create a redacted community-win draft:

```bash
python scripts/community_blog_pipeline.py from-file --source-file examples/community-win-source.md --title "How A Simple Website Offer Became A First-Client Win" --slug simple-website-offer-first-client-win --content-type win --redact "Member Name"
```

Repurpose an existing Ghost post to LinkedIn:

```bash
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --review-only
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --dry-run
python scripts/ghost_to_linkedin.py --slug your-ghost-post-slug --publish-now
```

The LinkedIn path uses the official LinkedIn API. See `linkedin-setup/README.md` for Coolify and non-Coolify setup.

## Recommended Article Structure

- One clear Ghost post title/H1.
- Direct answer or BLUF near the top.
- Short "In This Guide" table of contents.
- Descriptive H2 sections.
- Visible section FAQs where helpful.
- Full FAQ block near the bottom.
- Related links, glossary links, sources, and CTA.
- Clean evergreen slug with no random UUID and no year unless the article is a maintained annual guide.

## Cost Notes

The dry-run commands do not spend Apify credits. Live Reddit and YouTube actor runs do. Keep `--dry-run` while designing the topic, then run live only when you are ready to enrich a real article.

## Docs

- `docs/setup.md`
- `docs/youtube-repurposing.md`
- `docs/reddit-faq-enrichment.md`
- `docs/neo4j-content-memory.md`
- `docs/community-content-pipeline.md`
- `docs/publishing-checklist.md`
- `linkedin-setup/README.md`
- `linkedin-setup/coolify.md`
- `linkedin-setup/docker.md`
- `linkedin-setup/cli-workflow.md`
