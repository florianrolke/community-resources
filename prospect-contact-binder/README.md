# Prospect Contact Binder

Turn a conference website into a client-ready prospect binder. One link, not a spreadsheet.

**Python 3.10+ · MIT · runs for $0**

---

## What you get

Point it at a conference, get back a site like this:

- **A full-screen splash** — a photo of the host city, the event name in serif, one gold button
- **Live outreach consoles** — per row, a **Create Gmail Draft** button and a **Copy Msg + Open LinkedIn** button, each pre-filled from your pitch templates. Nothing sends automatically.
- **Research lists** — searchable, sortable, CSV download
- **Confidence pills** — so nobody mistakes a guess for a verified contact

### Consoles vs lists

Set `"console": true` on a section and it becomes a working outreach desk instead of a table. Consoles sort reachable rows to the top, filter by role and confidence, and preview the exact message before you send it.

The card on the front page describes what the console can actually do — if no row has an email, it says "LinkedIn messages", not "one-click Gmail drafts". A promise the page can't keep is worse than a smaller promise.

### Pitch templates

Consoles need copy. Put it in `pitches` in your config, keyed by name, and point each section at one with `"pitch": "speaker"`:

```json
"sender": { "name": "Your Name", "signature": "Your Name
Your Company
yourcompany.com" },
"pitches": {
  "speaker": {
    "subject": "Your {event} session — quick question",
    "body": "Hi {first},

I saw you're speaking at {event} in {city}. I'll be there too.

...

{signature}",
    "linkedin": "Hi {first} — saw you're speaking at {event}. I'll be there too."
  }
}
```

Placeholders: `{first}` `{name}` `{title}` `{company}` `{event}` `{dates}` `{city}` `{sender}` `{signature}`.

Write one pitch per segment. A speaker and a sponsor are in the room for different reasons and should not get the same email.

It is plain HTML with the data inlined. No build step, no server, no framework. Open it locally or drop it on Cloudflare Pages.

### Why a binder and not a spreadsheet

A CSV is a file you attach. A binder is a link you send. It opens on a phone, it looks like you spent money on it, and it gets forwarded to the person who actually signs.

Same data. Completely different reception.

---

## Setup

```bash
git clone https://github.com/florianrolke/prospect-contact-binder.git
cd prospect-contact-binder
pip install -r requirements.txt
playwright install chromium
```

Only the scraper needs Playwright. If you already have CSVs, skip it.

---

## Quick start

### 1. Scrape the conference

```bash
python -X utf8 -m scripts.scrape_conference_roster \
    --url https://someconference.com/2026/speakers \
    --event-name "Some Conference 2026" \
    --output data/speakers.csv
```

Free. No API key. Works on server-rendered *and* JavaScript-heavy sites, and reads sponsor names out of logo walls via alt text and outbound links.

If a page is behind a form or a login, it says so instead of writing an empty file. Go fill the form in yourself — you're a real prospective attendee, and that list is usually the good one.

### 2. Add LinkedIn profiles (optional, free)

```bash
python -X utf8 -m scripts.enrich_linkedin \
    --input data/speakers.csv --output data/speakers-li.csv
```

Tries [Exa](https://exa.ai) first, falls back to [Tavily](https://tavily.com) — both free tier. Rotates through numbered keys (`EXA_API_KEY_2`, `_3`, …) when one runs out of credits, and checkpoints so an interrupted run resumes instead of re-spending quota.

A profile is only kept when the profile itself names the person **and** their employer — not by reading the URL. See [Two things it refuses to do](#two-things-it-refuses-to-do).

📄 **Full guide: [linkedin.md](linkedin.md)** — key setup, hit rates, flags, troubleshooting.

### 3. Write your config

See [Configuring the binder](#configuring-the-binder) below. Start from `examples/binder.example.json`.

**Want to see it working first?** The `examples/` folder holds real output from a
real conference — Behavioral Health Tech 2026 in Nashville. Build it and look
before you point it at your own event:

```bash
python -X utf8 -m scripts.build_event_binder     --config examples/binder.example.json --outdir dist/demo
```

### 4. Build

```bash
python -X utf8 -m scripts.build_event_binder \
    --config data/my-binder.json \
    --outdir dist/my-binder
```

Open `dist/my-binder/index.html`.

---

## Configuring the binder

This is the part you actually edit. Everything below is yours to change.

```json
{
  "title": "Some Conference 2026",
  "subtitle": "Conference Prospect Binder",
  "owner": "Client Name · Their Company",

  "event_dates": "September 22–24, 2026",
  "venue": "Some Convention Center",
  "city": "Nashville, TN",

  "hero_image": "assets/hero.jpg",
  "hero_credit": "Nashville skyline — Photographer Name, CC BY 4.0",

  "intro": "One or two sentences on what this is and why it matters.",

  "sections": [
    {
      "id": "speakers",
      "label": "2026 Speakers",
      "icon": "&#127908;",
      "accent": "blue",
      "csv": "data/speakers.csv",
      "blurb": "Everyone on stage, with title and company.",
      "columns": ["person_name", "title", "organization", "linkedin_url", "confidence"]
    }
  ]
}
```

### Top level

| Field | Required | What it does |
|---|---|---|
| `title` | **yes** | Big headline on the hero. Use the conference's real name. |
| `sections` | **yes** | One entry per list. See below. |
| `subtitle` | no | Small uppercase kicker above the title. |
| `owner` | no | Appears in the footer — "Built March 3, 2026 for …". |
| `event_dates`, `venue`, `city` | no | Joined into the line under the title. |
| `hero_image` | no | **Read the next section.** This is what makes it feel bespoke. |
| `hero_credit` | no | Photographer credit, bottom-right of the hero. |
| `intro` | no | A paragraph under the hero. Say what the lists are for. |

### Sections

| Field | Required | What it does |
|---|---|---|
| `id` | **yes** | Filename slug. `speakers` → `speakers.html` + `speakers.csv`. |
| `label` | **yes** | Card title and page heading. |
| `csv` | **yes** | Path to the CSV. Missing files are skipped with a message. |
| `blurb` | no | Card body text. **Say why this list matters, not what it is.** |
| `icon` | no | An emoji as an HTML entity, e.g. `&#127908;` 🎤, `&#127919;` 🎯, `&#127970;` 🏢. |
| `accent` | no | `blue`, `green`, `amber`, `purple`. Cycles automatically if omitted. |
| `columns` | no | Which columns to show, in order. Omit and it picks the non-empty ones. |

Columns that render specially: `linkedin_url` and `website` become links, `email` becomes a mailto, `confidence` becomes a coloured pill.

**On blurbs:** "186 companies with the budget to sponsor — they already pay for visibility at events, which is the thing you sell" beats "list of sponsors". The client is reading this to decide where to start.

---

## The hero image

The photo is what separates this from a generated report. **Use the host city.** A real skyline of the place your client is flying to reads as effort in a way that a stock gradient never does.

### Get a properly licensed one

Wikimedia Commons has good skylines for most cities, free and reusable:

```bash
python -X utf8 -c "
import json,urllib.request,urllib.parse
q='Nashville Tennessee skyline'          # <-- change this
u='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode({
 'action':'query','format':'json','generator':'search',
 'gsrsearch':f'filetype:bitmap {q}','gsrlimit':8,'gsrnamespace':6,
 'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':2000})
r=urllib.request.Request(u,headers={'User-Agent':'binder/1.0 (research)'})
for _,p in json.load(urllib.request.urlopen(r))['query']['pages'].items():
    ii=p['imageinfo'][0]; md=ii['extmetadata']
    print(md.get('LicenseShortName',{}).get('value','?'), '|', p['title'][:50])
    print('   ', ii['thumburl'])
"
```

Then download the **exact** `thumburl` it printed:

```bash
python -X utf8 -c "
import urllib.request
url='PASTE_THE_THUMBURL_HERE'
req=urllib.request.Request(url,headers={'User-Agent':'binder/1.0 (research)'})
open('assets/hero.jpg','wb').write(urllib.request.urlopen(req,timeout=90).read())
print('saved')
"
```

Wikimedia rejects arbitrary widths with a 400 — use the URL the API gave you, unchanged.

### Rules that matter

- **Credit the photographer** in `hero_credit`. The licence requires it and it costs you nothing.
- **Darker photos read better.** A scrim darkens the lower half so white text stays legible; a bright noon skyline fights it. Dusk and night shots work best.
- **Resize to ~2000px wide.** A 3840px original is 2.5MB and the binder should load instantly.
- **Don't pay to generate one.** A real photo of the real city is better, and free.

Any wide image works — the venue, a landmark, your client's own photography from last year's event. City skylines are just the reliable default.

---

## Two things it refuses to do

**It will not attach a LinkedIn URL it can't verify.** The profile itself has to name the person *and* their employer, or the cell stays empty.

This is not paranoia, and reading the URL is not enough. An earlier version checked whether the name appeared in the profile slug, which was wrong in both directions: searching *Adam Morgan* at Twilio accepted `/in/adam-morgan-28227a420` (a different Adam Morgan) while rejecting `/in/admo3` — the real one, whose profile says "VP of Brand at Twilio". A slug is a handle someone picked, not a fact about where they work.

Shipping the wrong one means your client sends a personal note to a stranger about a talk they aren't giving. An empty cell is honest; a wrong cell is a wrong email, and a full-looking row never gets checked. See [linkedin.md](linkedin.md) for how it's verified.

**It will not invent a contact.** Names come from search-result titles and pass a strict shape test. Mining names out of prose produced a contact called "combine design". Companies with no confident contact stay in the list, flagged — dropping them would overstate your coverage.

Fewer rows, all true, beats more rows you have to second-guess.

---

## Putting it behind a key

For client work you usually want a link that only they can open.

Add a `_worker.js` at the root of your output folder:

```js
function deny() {
  return new Response("Not authorized.", { status: 403 });
}
export default {
  async fetch(request, env) {
    const key = (env.DASHBOARD_KEY || "").trim();
    if (!key) return deny();                       // fail closed
    const url = new URL(request.url);
    const qk = (url.searchParams.get("k") || "").trim();
    const m = (request.headers.get("Cookie") || "").match(/(?:^|;\s*)ok=([^;]+)/);
    const ck = m ? decodeURIComponent(m[1]).trim() : "";
    if (qk !== key && ck !== key) return deny();
    const res = await env.ASSETS.fetch(request);
    if (qk === key) {
      const r = new Response(res.body, res);
      r.headers.append("Set-Cookie",
        `ok=${encodeURIComponent(key)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000`);
      return r;
    }
    return res;
  },
};
```

Then deploy and set `DASHBOARD_KEY` as an environment variable on the Pages project:

```bash
npx --yes wrangler@latest pages deploy dist/my-binder \
    --project-name my-conference --branch main --commit-dirty=true
```

Access is then `https://my-conference.pages.dev/?k=YOUR_KEY`.

> ### ⚠️ Check for one line in the output
>
> Wrangler 4 **silently stopped compiling** the Pages `functions/` directory. If you use `functions/_middleware.js`, it uploads your files, prints "Deployment complete", and serves your client's data **completely open**. Nothing in the output warns you.
>
> Use `_worker.js` as above, and confirm the deploy prints:
>
> ```
> ✨ Compiled Worker successfully
> ```
>
> **If that line is missing, your site is public.** Always open the bare URL in a private window and check you get a 403.

Leave the key in the URL rather than stripping it — one link then works on every device your client opens it on.

---

## Never commit secrets

`.gitignore` already covers `.env`, `*.key`, and `dist/`. Keep it that way.

- API keys go in `.env`, which is ignored. Never in a config file, never in a committed script.
- The binder's `DASHBOARD_KEY` belongs in the Pages project's environment variables, **not** in `_worker.js`.
- `dist/` is ignored because it contains your client's actual prospect list. That is their data, not yours to publish.

Before your first push:

```bash
git add -A
git status --porcelain          # read every line
git grep --cached -nIE "sk-|api[_-]?key\s*=\s*['\"]|token\s*=\s*['\"]"
```

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Section skipped | CSV path wrong or file empty. It names which. |
| A stat pill reads 0 | That layer wasn't run. Run it or drop the section — a zero on the front page undersells the work. |
| Hero looks washed out | Photo too bright. Use a dusk or night shot. |
| Wikimedia 400 | You changed the thumbnail width. Use the API's URL verbatim. |
| Sticky header over the rows | Fixed — `border-collapse:collapse` breaks `position:sticky` on `<th>` in Chrome, so this uses `separate` + `border-spacing:0`. |
| Everything says `weak` | No `EXA_API_KEY`. That's the step that confirms LinkedIn matches. |
| `UnicodeEncodeError` on Windows | Add `-X utf8`. |

---

## License

MIT. The scraper and binder are yours to modify and use commercially.
