# Research Report Workflows

Use pasted Genspark or Perplexity reports as optional input examples for the pipeline, not as permanent private data. The default out-of-the-box flow should use Apify SERP discovery so community members are not dependent on manual research.

## What The Skill Must Learn From Reports

Reports may contain:
- Niche podcast lists.
- Host and guest names.
- LinkedIn profile URLs already found by research.
- YouTube channel URLs and episode URLs.
- Generated CSV previews.
- Tool traces such as `Using Tool`, `Parallel Search`, `Video Search`, `Write File`, and `Read File`.

The goal is always to convert messy research into clean enrichment outputs:
- Relevant niche-specific podcasts.
- Podcast hosts/owners with LinkedIn URLs.
- YouTube/RSS/Spotify/Apple source URLs.
- Interview episode URLs.
- Guest/speaker names.
- Guest/speaker LinkedIn URLs with confidence and evidence.

For client use, treat the interviewee list as the core enrichment product. The show list is the source map; the final outreach sheet should contain one row per guest/interviewee appearance with a LinkedIn profile candidate and evidence.

## Intake Prompts

Before running automation, collect:
- `niche`: the industry or sub-niche, e.g. `pool construction`.
- `audience`: the people to reach, e.g. `pool builders, designers, remodelers`.
- `seed_terms`: optional terms that improve relevance, e.g. `design build remodeling service concrete fiberglass`.
- `geo`: optional location if the campaign is regional.
- `must_include`: optional terms that should appear in shows or episodes.
- `exclude`: optional terms to avoid, such as consumer DIY shows when the ICP is contractors.

If the user cannot provide more than the niche, run anyway with broad default query patterns and produce a review queue.

## Default Waterfall

Use this no-manual-research flow first:

```bash
$env:PYTHONPATH=(Get-Location).Path
python scripts/run_podcast_intelligence_waterfall.py \
  --niche "pool construction" \
  --audience "pool builders designers remodelers" \
  --seed-terms "design build construction service"
```

The waterfall performs:
1. Apify SERP discovery for podcast/interview episode URLs.
2. Episode row normalization into `data/<niche>-podcast-interview-episode-serp-discovery.csv`.
3. Guest/interviewee extraction into `data/<niche>-podcast-interviewees-extracted.csv`.
4. LinkedIn matching via Apify SERP into `data/<niche>-podcast-interviewees-linkedin-enriched.csv`.
5. Candidate/evidence preservation for review.

Only use Tavily/Exa/Perplexity as optional fallback passes after Apify SERP leaves important high-value rows unresolved.

## Genspark Pattern

Genspark often includes a tool log before the useful answer. Do not treat tool-log lines as podcast rows. Use them to classify the source and find generated CSV previews or YouTube URLs.

Common markers:
- `Using Tool | Parallel Search`
- `Using Tool | Video Search`
- `Using Tool | Write File`
- `Using Tool | Read File`
- `/mnt/user-data/outputs/...csv`

## Family Law Voice Pattern

For a niche such as family law, the best output is not just shows. It is a prospecting sheet:
- Podcast or series.
- Why it matches the niche.
- Host/owner LinkedIn.
- Episode title.
- Guest/speaker.
- YouTube URL or RSS episode URL.
- Priority score and outreach angle.

Use law-firm-growth shows as a second lane when they have family-law guests or family-law-specific episodes.


## Confirmed Episode URL Pattern

Some reports answer the final task directly with sections like `Family Law Growth Podcast`, a table containing `Episode title`, `Guest`, and `Direct URL`, then a `Final combined URL list`.

For these reports, extract the table rows first because they preserve the guest and episode title. Use the final URL list only as a dedupe/checklist fallback.

## One-Step Interviewee List Pipeline

When the user has either a podcast source CSV or pasted reports, prefer the aggregate pipeline:

```bash
python scripts/build_interviewee_linkedin_list.py \
  --podcasts data/<niche>-podcast-sources.csv \
  --report reports/<niche>-genspark-youtube-episodes.md \
  --output data/<niche>-podcast-interviewees-linkedin-enriched.csv \
  --match-linkedin
```

Use `--use-perplexity` only when Apify SERP/Tavily/Exa leave important `verify` or `low` rows. The script accepts repeated `--report` flags so Genspark, Perplexity, and user-supplied research can be merged into one deduped outreach sheet.
