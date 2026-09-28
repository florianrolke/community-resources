# LinkedIn Enrichment

You have a list of names. You need their LinkedIn profiles. This does that, for $0.

**Script:** `scripts/enrich_linkedin.py` · **Cost:** free tier only · **Needs:** one Exa key, one Tavily key, or both

---

## The 30-second version

```bash
pip install -r requirements.txt
cp .env.example .env          # add EXA_API_KEY and/or TAVILY_API_KEY

# Try one person first
python -X utf8 -m scripts.enrich_linkedin --name "Cara McNulty" --company "Vibrant Emotional Health"

# Then the whole list
python -X utf8 -m scripts.enrich_linkedin --input data/speakers.csv --output data/speakers-linkedin.csv
```

Your CSV needs a `person_name` column. An `organization` column makes matches
substantially better — "Andy Kelly" is a dozen people, "Andy Kelly + Boulder
Care" is one.

---

## Get the keys (both free, no card)

| Engine | Where | Free tier |
|---|---|---|
| **Exa** | [exa.ai](https://exa.ai) | ~1,000 searches/month per key |
| **Tavily** | [tavily.com](https://tavily.com) | 1,000 searches/month per key |

Put them in `.env`:

```
EXA_API_KEY=your-key
TAVILY_API_KEY=your-key
```

### Add more keys to raise the ceiling

The script reads `EXA_API_KEY`, `EXA_API_KEY_2`, `EXA_API_KEY_3` … up to `_20`,
and the same for Tavily. When a key returns "out of credits", the script retires
it and moves to the next one **mid-run** — you don't restart, you don't lose
progress.

```
EXA_API_KEY=key-one
EXA_API_KEY_2=key-two
EXA_API_KEY_3=key-three
```

This matters more than it sounds. On a real 24-person list, running with one
(spent) key matched 3 people. The same list with the full key set matched 7 out
of the first 10. Same script, same names — the only difference was having live
credits to rotate into.

---

## Why two engines

They fail differently, so they run in order:

**1. Exa** — embedding-based search. Markedly better at *"which profile IS this
exact person"*, which is the whole problem here. Tried first.

**2. Tavily** — keyword search. Weaker at telling two same-named people apart on
its own, which is exactly why the name check below is not optional. Separate
quota, so it keeps working after Exa runs dry.

If Exa returns nothing usable, Tavily gets a turn. If you only have one of the
two keys, it just uses that one.

---

## The rule that makes this trustworthy

**The profile has to say the person's name AND their employer, or the result is thrown away.**

Note what that does *not* say: it says nothing about the URL.

### Why reading the URL doesn't work

The obvious check is to read the link — does `linkedin.com/in/adam-morgan`
contain "adam" and "morgan"? It's free, it needs no extra API call, and it is
wrong in **both** directions:

```
Searching "Adam Morgan" at Twilio:

  linkedin.com/in/adam-morgan-28227a420   slug has adam + morgan   ACCEPTED  <- wrong person
  linkedin.com/in/admo3                   slug has neither          REJECTED  <- right person
                                          profile reads "VP of Brand at Twilio"
```

Both mistakes have the same cause: **a slug is a vanity handle someone picked,
not a fact about where they work.** Plenty of senior people use initials, a
nickname, or a number — `admo3`, `ckoehler`, `andykkelly`, `ysherwani`. Slug
matching can't find any of them, while it happily hands you a stranger who
happens to share a name.

### What it checks instead

Exa can return the profile's **text** alongside the search result. That text
says where the person actually works, so that's what gets checked:

| Check | Question it answers |
|---|---|
| Name appears as the profile's owner | Is this that person? |
| Employer appears in the profile | At the company you meant? |

Both, or it's dropped. That's how `Adam Morgan` at Twilio resolves to `admo3`
and not to the other Adam Morgan.

### The trap with posts

A post URL embeds its **author's** handle:

```
linkedin.com/posts/andykkelly_big-news-ive-joined-boulder-care-...
                   ^^^^^^^^^^ Andy's handle — his own post
```

That's a gift: it finds people whose handle you'd never guess. But it cuts the
other way, because a company posting *about* someone embeds the **company's**
handle:

```
linkedin.com/posts/boulder_before-joining-our-team-andy-kelly-spent-...
                   ^^^^^^^ Boulder Care's handle, not Andy's
```

Take the handle blindly and you record `linkedin.com/in/boulder` as a person's
profile. So the author is checked first — Exa titles posts as
`"<post text> | <Author>"` — and the handle is only used when the author *is*
your person.

### Names it won't even search

Scraped rosters are full of `Investor Relations`, `Who We Are`, `Y Combinator`.
Those are skipped before a search is spent, because they can only ever produce
a false match.

Credentials are stripped before comparing, so `Cara McNulty, DPA`,
`Amber Childs, PhD` and `Kelly Crosbie, MSW, LCSW` are matched as people rather
than as someone whose surname is "PhD".

**An empty cell is honest. A wrong cell is a wrong message** — and worse, it's
one nobody re-checks, because the row looks finished.

---

## Commands you'll actually use

```bash
# Spot-check the matcher on one person — no file, no cost worth counting
python -X utf8 -m scripts.enrich_linkedin --name "Andy Kelly" --company "Boulder Care"

# Full list
python -X utf8 -m scripts.enrich_linkedin \
  --input data/speakers.csv --output data/speakers-linkedin.csv

# Test on 10 rows before committing your quota to 500
python -X utf8 -m scripts.enrich_linkedin \
  --input data/speakers.csv --output data/test.csv --limit 10

# Second pass: only retry rows still missing a URL (safe to re-run any time)
python -X utf8 -m scripts.enrich_linkedin \
  --input data/speakers-linkedin.csv --output data/speakers-linkedin.csv --only-missing

# Got interrupted? Same command resumes from the checkpoint.
# Start clean instead:
python -X utf8 -m scripts.enrich_linkedin --input ... --output ... --no-resume
```

| Flag | What it does |
|---|---|
| `--input` / `--output` | CSV in, CSV out. Safe to use the same path for both. |
| `--name` / `--company` | Single lookup, no file needed |
| `--only-missing` | Skip rows that already have a `linkedin_url` |
| `--limit N` | First N rows only. **Use this first.** |
| `--workers N` | Parallel lookups, default 4 |
| `--no-resume` | Ignore the checkpoint, start clean |

---

## It resumes

Progress is checkpointed to `<output>.checkpoint.json` every 10 lookups. Kill it
with Ctrl-C, close the laptop, lose the wifi — re-run the same command and it
picks up where it stopped instead of re-spending quota on names it already did.

Delete that file (or pass `--no-resume`) to force a clean run.

---

## What you get back

The same CSV, with these columns filled in on matched rows:

| Column | Value |
|---|---|
| `linkedin_url` | The profile URL, or empty |
| `confidence` | `confirmed` = name and employer both verified in the profile. `probable` = person verified, but you gave no company to check against |
| `evidence` | Which engine matched it, and what was verified |
| `next_action` | `outreach` |

If a row comes back empty, the reason is worth reading — the script prints one
per miss:

| Reason | What happened |
|---|---|
| `employer-not-in-profile` | Found someone with that name, but nothing ties them to that company. Usually a different person with the same name. |
| `profile-title-is-a-different-person` | The profile belongs to someone else entirely. |
| `post-written-by-someone-else` | The only hit was a post *about* them by another account, so the handle isn't theirs. |
| `skipped-not-a-person` | The "name" is a page title or org (`Who We Are`), never searched. |
| `not-a-profile-url` | Results were company pages or articles, no personal profile. |

Rows that didn't match are left exactly as they were. Nothing is deleted, nothing
is overwritten with a guess.

---

## Realistic hit rates

Depends almost entirely on who's on your list.

- **Executives and founders at known companies** — high. They maintain profiles and their name+company pairing is unambiguous.
- **Clinicians, public-sector staff, academics** — much lower. Many have no public profile, or one under a maiden/legal name that doesn't match the roster.
- **Anyone with a very common name and no company** — low. There's nothing to disambiguate on.

If a run comes back mostly empty, check in this order:

1. **Is `organization` populated?** This is usually the fix.
2. **Are your keys live?** The script prints `Engines: Exa N key(s), Tavily N key(s)` on start, and warns at the end if Exa ran dry mid-run.
3. **Are the "names" actually names?** Scraped rosters are full of `Who We Are`, `Investor Relations`, `Y Combinator`. Those are skipped automatically, but they'll show as misses.

---

## Feeding the binder

`linkedin_url` is what the outreach consoles read. Once it's populated:

- the **Copy Msg + Open LinkedIn** button goes live on that row
- the URL shows as a clickable link in the Contact column
- the row sorts toward the top, because reachable rows come first

```bash
# enrich, then rebuild
python -X utf8 -m scripts.enrich_linkedin --input data/speakers.csv --output data/speakers-linkedin.csv
python -X utf8 -m scripts.build_event_binder --config data/binder.json --outdir dist/binder
```

Point the section's `csv` at the enriched file in your binder config and the
console picks it up on the next build.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No EXA_API_KEY or TAVILY_API_KEY found` | Keys aren't in `.env`, or you're running from outside the repo root |
| Everything returns `-` | Usually spent keys. The startup line shows how many were loaded; a 402/429 retires a key silently and rotates on |
| `UnicodeEncodeError` on Windows | You dropped the `-X utf8`. Names have accents; keep the flag |
| Matched the wrong person | Report it — that means `slug_matches()` has a hole, and that's the one bug in here that actually costs you a relationship |
| Slow | Raise `--workers`, but free tiers rate-limit; 4–8 is the sweet spot |

---

## Where this came from

The waterfall pattern (Exa → Tavily, rotate keys on exhaustion, checkpoint every
N) is the same one used across the lead-enrichment work this repo grew out of.
What's specific here is the strict both-names slug check — added after a real
wrong-person match made it into a real client list.
