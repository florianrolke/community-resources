# exact-website-clone

Clone any prospect's website header in minutes and deploy it to a live URL — with personalized case-study copy below the fold.

Live demo: [teamsiok.clients.of.florianrolke.com](https://teamsiok.clients.of.florianrolke.com)

---

## What this does

**Step 1 — Clone.** `clone_website.py` uses Firecrawl to pull the real HTML of any website: nav bar, hero section, fonts, brand colors. Not an approximation — the actual site.

**Step 2 — Personalize.** Below the cloned header you drop a 7-section personalized case study built around the prospect's numbers: stats grid, before/after comparison, ROI calculator, and a CTA.

**Step 3 — Deploy.** `deploy_redesign.py` pushes the HTML to a GitHub repo, which Coolify auto-builds into an nginx Docker container. The page is live at `{slug}.preview.yourdomain.com` within ~2 minutes.

---

## Architecture

```
GitHub repo (your deploy repo)
    └── sites/{slug}/index.html
           ↓ Coolify webhook → Docker build
nginx container on your VPS
    └── {slug}.preview.yourdomain.com → sites/{slug}/
           ↓
Cloudflare DNS A record → VPS IP
```

Subdomain routing patterns (nginx.conf):

| Pattern | Serves from |
|---------|------------|
| `{slug}.preview.yourdomain.com` | `sites/{slug}/` |
| `{slug}.clients.of.yourdomain.com` | `landing/{slug}/` |
| `{slug}.yourdomain.com` | `sites/{slug}/` |

---

## Quick start

```bash
# 1. Clone this repo
git clone https://github.com/Florian1995-ai/exact-website-clone
cd exact-website-clone

# 2. Install dependencies
pip install firecrawl-py python-dotenv requests

# 3. Copy and fill env vars
cp .env.example .env
# edit .env

# 4. Clone a website
python execution/clone_website.py --url "https://yourprospect.com" --slug prospect-name

# 5. Deploy to live URL
python execution/deploy_redesign.py --slug prospect-name --html-file .tmp/clones/prospect-name/index.html
# → live at https://prospect-name.preview.yourdomain.com
```

---

## Infrastructure setup (one-time)

You need:
- A GitHub repo for the HTML files (can be public or private)
- A VPS with [Coolify](https://coolify.io) installed — point it at your GitHub repo, Dockerfile included
- A domain managed by Cloudflare — create a wildcard A record `*.preview` → your VPS IP

The `Dockerfile` and `nginx.conf` in this repo are what Coolify builds. Drop them into your GitHub deploy repo root.

---

## Personalized section blueprint

The copy below the cloned header follows the **7-section blueprint** (from real outreach sessions):

1. **Transition hook** — references something specific about the prospect
2. **Stats grid** — 3-4 cards with real numbers (leads/mo, response time, close rate)
3. **Before / After** — red card (pain) → green card (what changed)
4. **Client quote** — attributed, from a real transcript
5. **Ceiling benchmark** — where top 5% in their industry sit vs. average
6. **Interactive ROI calculator** — pre-filled sliders, live math
7. **CTA** — low friction ("15 minutes. Your numbers. Zero pressure.")

---

## Required env vars

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Scrape prospect websites |
| `GITHUB_TOKEN` | Push HTML to deploy repo (needs Contents: write) |
| `COOLIFY_API_TOKEN` | Register domains + trigger redeploys |
| `COOLIFY_API_URL` | Your Coolify instance URL |
| `CLOUDFLARE_API_TOKEN` | Create DNS A records |
| `CLOUDFLARE_ZONE_ID` | Which zone to add records to |

See `.env.example` for the full list.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `execution/clone_website.py` | Scrape any URL → `.tmp/clones/{slug}/index.html` + branding.json |
| `execution/deploy_redesign.py` | Push HTML to GitHub, register Coolify domain, trigger build, wait for SSL |
| `execution/deploy_static_site.py` | Simpler single-file deploy (no batch/sheet features) |
| `nginx.conf` | Wildcard subdomain routing — copy into your deploy repo |
| `Dockerfile` | nginx Docker build — copy into your deploy repo |
