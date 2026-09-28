# Podcast LinkedIn Intelligence Skills

A shareable Codex skill bundle for turning a niche into podcast outreach lists:

- relevant niche podcasts and interview episode URLs
- podcast hosts/owners for LinkedIn outreach
- podcast guests/interviewees for LinkedIn outreach
- YouTube, RSS, Apple, Spotify, and generic episode URL handling
- evidence fields and confidence labels for review

The default workflow uses Apify SERP discovery first so members do not need to do manual research.

## Required API Tokens

Copy `.env.example` to `.env` and fill in only the keys you need.

Minimum out-of-the-box waterfall:

```env
APIFY_API_TOKEN=
APIFY_SERP_ACTOR=apify/google-search-scraper
```

Recommended for fuller runs:

```env
APIFY_API_TOKEN=
APIFY_API_TOKEN_2=
APIFY_API_TOKEN_3=
APIFY_API_TOKEN_4=
APIFY_API_TOKEN_5=
APIFY_SERP_ACTOR=apify/google-search-scraper
APIFY_YOUTUBE_CHANNEL_ACTOR=streamers/youtube-channel-scraper
APIFY_YOUTUBE_TRANSCRIPT_ACTOR=topaz_sharingan/youtube-transcript-scraper-1
APIFY_AUDIO_TRANSCRIPT_ACTOR=
OPENAI_API_KEY=
OPENROUTER_API_KEY=
```

Optional paid enrichment fallbacks:

```env
PERPLEXITY_API_KEY=
EXA_API_KEY=
EXA_API_KEY_2=
EXA_API_KEY_3=
EXA_API_KEY_4=
TAVILY_API_KEY=
TAVILY_API_KEY_2=
TAVILY_API_KEY_3=
TAVILY_API_KEY_4=
```

Do not commit `.env`, credentials, raw client reports, or generated campaign data.

## Install

```bash
python -m pip install -e .[test]
```

On Windows PowerShell, run commands from the repo root and set:

```powershell
$env:PYTHONPATH=(Get-Location).Path
```

## Fastest Waterfall

Use this when a member provides only a niche and ICP:

```bash
python scripts/run_podcast_intelligence_waterfall.py \
  --niche "pool construction" \
  --audience "pool builders designers remodelers" \
  --seed-terms "design build construction service"
```

The waterfall creates:

- `data/<niche>-podcast-interview-episode-serp-discovery.csv`
- `data/<niche>-podcast-interviewees-extracted.csv`
- `data/<niche>-podcast-interviewees-linkedin-enriched.csv`

## Best Member Intake

Ask the member for:

- niche or sub-niche
- audience/ICP
- geography, if relevant
- must-include terms
- exclusion terms
- known podcasts, creators, channels, or competitors, if they have them

Example:

```text
Niche: pool construction
Audience: pool builders, designers, remodelers
Seed terms: design build, construction, service, outdoor living
Geo: US
Exclude: consumer DIY maintenance
```

If the member only knows the niche, run the default waterfall anyway and treat low-confidence rows as a review queue.

## Manual Source Inputs

If a member already has pasted Genspark/Perplexity research or episode lists:

```bash
python scripts/build_interviewee_linkedin_list.py \
  --report reports/<niche>-episode-research.md \
  --output data/<niche>-podcast-interviewees-linkedin-enriched.csv
```

## Guardrails

- Accept only direct LinkedIn `/in/` profile URLs as strong candidates.
- Keep low-confidence candidates for review instead of guessing.
- Preserve evidence in every output row.
- Prefer Apify SERP before Tavily/Exa to reduce API-credit usage.
- Use Tavily, Exa, and Perplexity only as optional fallback passes.

## Validate

```bash
python -m pytest
```
