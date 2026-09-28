# Fable Meta Ads Factory

**How I built a complete Meta lead-ads campaign — 15 ad concepts, generated creatives, a compliance
playbook, and a phone-accurate lead-form preview — using one AI model to orchestrate and another to
execute.**

This repo is a worked case study plus the reusable pieces. The client was a local water-damage
**mitigation** company in a large Sun Belt metro that pays plumbers a referral fee ($100 the day a
lead is sent, $900 more when the job closes) for pointing homeowners with water damage their way.
Every identifying detail is anonymized to `[Name Redacted]`; what's shared here is the *method*, not
the client.

**Live anonymized preview:** https://meta-ads-preview.pages.dev — 13 ads rendered exactly as they'd
appear in the Facebook feed, with a working Instant-Form simulation.

---

## The one idea worth stealing: orchestrator / executor split

I ran this with two models playing two different roles, and the split is the whole trick:

- **The orchestrator (planning model)** holds the goal, the client context, and the sequence. It
  reads the meeting transcripts, decides what to build, writes the strategy and the ad copy, spawns
  workers, verifies their output, deploys, and keeps the privacy rules straight. It rarely writes
  application code itself.
- **The executor (coding model)** is spawned as a fresh sub-agent for each concrete build job:
  "write this generation script and run it," "adapt this HTML template," "restyle this to light
  mode." It gets a tight brief and returns a finished artifact.

Why bother? Because the two jobs fail in different ways. Orchestration fails when you lose the thread
— you forget a constraint, you let the client's real name leak, you deploy the wrong folder.
Execution fails when code is sloppy. Keeping them separate means the model holding the *context*
isn't also burning its attention on brace-matching, and the model writing the *code* gets a clean,
single-purpose task it can nail. In practice the orchestrator wrote ~zero lines of the Python and
HTML; it wrote the briefs and checked the results.

### Who did what, concretely

| Step | Orchestrator | Executor (sub-agent) |
|---|---|---|
| Pull meeting transcripts, extract the offer + audience | ✅ | |
| Write the strategy, angles, and 15 ad copy units | ✅ | |
| Write the Kie image-generation script + run it | brief + verify | ✅ code + run |
| Adapt the landing-page / feed-preview HTML template | brief + verify | ✅ code |
| Restyle preview to light mode | brief + verify | ✅ code |
| Sanitize everything for public release | ✅ rules + grep | ✅ edits |
| Deploy to Cloudflare Pages, verify the live URL | ✅ | |
| Keep the client's identity out of every asset | ✅ (hard rule) | ✅ (per-brief) |

The executor sub-agents ran **in parallel** whenever the work was independent (e.g. generating the
second batch of images *while* the preview site was being built), and the orchestrator only blocked
when it needed a result to proceed.

---

## What's in this repo

```
fable-meta-ads-factory/
├── README.md                     ← you are here
├── kie-pipeline/                 ← the image-generation engine (reusable)
│   ├── generate_ads.py           ← Kie seedream text-to-image, prompts from JSON, dry-run/live/retry
│   ├── prompts.example.json      ← generic example ad prompts
│   ├── .env.example              ← KIE_AI_API_KEY=...
│   └── README.md                 ← setup + usage
├── methodology/                  ← the written IP (sanitized)
│   ├── ad-copy-interplay-doctrine.md      ← the copy technique below
│   ├── meta-compliance-playbook.md        ← how to not get your ad account banned
│   └── targeting-creative-as-targeting.md ← reaching a niche B2B audience compliantly
└── sample-creatives/             ← a few generated ad statics (anonymized)
```

---

## The creative pipeline (Kie AI, text-baked-into-image)

The ad statics were generated with **Kie AI's `seedream/5-pro-text-to-image`** model. The trick that
makes these look like real Meta ads: the **headline is baked into the image** as a navy bar with
white uppercase text, generated *by the image model* rather than overlaid afterward. It costs ~7
credits (~$0.70) per image and renders legible headline text about 90% of the time.

Key engineering choices, all in [`kie-pipeline/generate_ads.py`](kie-pipeline/generate_ads.py):

- **Prompts live in a JSON file**, not the script — so the engine is reusable and no copy is
  hardcoded.
- **`.task.json` sidecar** written next to every PNG (task id, prompt, credits, result URL) — a full
  audit trail, and you never lose track of what produced what.
- **`--dry-run` is the default.** You have to pass `--live` to spend a cent. This exists because
  image credits are irreversible; a stray run shouldn't cost money.
- **`--only <substr>`** regenerates a single image by filename stem. When one headline renders with a
  typo (the model wrote "LEEK" instead of "LEAK" once), you retry *just that one* without re-billing
  the whole batch.
- **Verify the text visually.** Every generated image was opened and its headline read back
  character-by-character before it was accepted. Image models misspell; you catch it by looking.

See [`kie-pipeline/README.md`](kie-pipeline/README.md) for setup and the prompts schema.

---

## The copy technique: the interplay doctrine

Most ad copy makes every element say the same thing three times: the image, the headline, and the
body all restate the offer. That's a waste of three surfaces.

The better approach — detailed in
[`methodology/ad-copy-interplay-doctrine.md`](methodology/ad-copy-interplay-doctrine.md) — is to make
each element play a **different note of one chord**:

- **Image headline** opens a loop / names a tension — and does *not* resolve it.
- **Primary text (first line)** is a curiosity hook that develops the tension.
- **Ad headline** *answers* the image — a call-and-response.
- **Description** is the kicker.

The flagship example (anonymized): the image says **"NOBODY PAYS PLUMBERS FOR SPOTTING WATER
DAMAGE."** The body enumerates the nobodies. The ad headline answers: **"We do. $100 the same day."**
One sentence spread across three surfaces, each incomplete without the others. Cover any one element
and the ad feels broken — that's the test.

---

## Staying compliant (and un-banned)

Recruiting-style lead ads sit near three Meta tripwires at once, and a lazy version gets the ad
account restricted. The full checklist is in
[`methodology/meta-compliance-playbook.md`](methodology/meta-compliance-playbook.md); the headlines:

1. **Employment Special-Ad-Category risk.** "Get paid to do X" ads get auto-classified as
   employment, which nukes your targeting. Framing it as a **business-to-business partnership** (with
   fee-schedule language, not "income") keeps it out of that bucket.
2. **Personal attributes.** You may not imply you know the viewer's situation. "Did you just move
   here?" is banned; a third-person story ("a tradesperson who relocated from another state told me…") does
   the same targeting job compliantly.
3. **Money claims.** A fee schedule ("$100 per lead") is fine; an income projection ("make $3k/month")
   is not. Never multiply.

And the targeting counterpart — [`methodology/targeting-creative-as-targeting.md`](methodology/targeting-creative-as-targeting.md)
— covers the "creative *is* the targeting" doctrine: for a niche B2B micro-audience you run broad and
let the copy self-select, because Meta won't let you cleanly target an occupation or "recently
relocated" people anyway.

---

## The preview technique

Clients can't picture an ad from a spec. So the last step was a single-file HTML page that renders
every concept as a **pixel-faithful Facebook feed card** — Sponsored header, "See more" text
truncation, the grey lead-form strip, engagement row — and a **working Instant-Form simulation**: tap
Sign Up, walk the real Meta lead-form flow (intro → contact → qualifying questions → review →
thank-you). In the client build, the thank-you buttons fired a real `sms:`/`tel:` to the owner's
phone, so a test tap actually reached them. The public version here has those neutralized.

It's one static HTML file, deployed free to Cloudflare Pages. Live: https://meta-ads-preview.pages.dev

---

## Tools used

- **Kie AI** — image generation (`seedream/5-pro-text-to-image`): https://kie.ai
- **Cloudflare Pages** (via `wrangler`) — free static hosting for the previews
- **Python** + `requests` + `python-dotenv` — the generation engine
- An agentic coding harness with an **orchestrator model** driving **executor sub-agents**

---

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, adapt it. The package isn't perfect, but on my end it
works.
