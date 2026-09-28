# Creative IS the Targeting — reaching a niche B2B micro-audience on Meta

## What problem this solves

You want to reach a very small, very specific professional audience on Meta — say,
a few thousand people in one trade, in one metro, maybe with an extra qualifier
like "recently relocated." Meta's targeting tools were built to isolate broad
consumer segments, not to pick out one occupation in one city. If you try to
micro-target your way to that audience, you'll build a tiny, brittle, expensive
ad set that Meta can barely deliver — and you'll still miss most of the people you
wanted.

This doc lays out the counter-intuitive doctrine that works instead: **the
creative is the targeting.** You let the *settings* cast a wide net over the right
geography and age, and you let the *copy* do the actual selecting. A feed full of
the right-city adults will contain your niche; a well-aimed first line makes
exactly those people stop scrolling and self-identify. Settings narrow the pond;
the creative does the fishing.

> **Worked example used throughout:** reaching **plumbers in one large Sun Belt
> metro**, including ones who recently relocated from another state, for a B2B
> referral offer. Treat it as one concrete instance; the doctrine generalizes to
> any niche-trade or niche-professional micro-audience.

---

## The audience math (why broad beats narrow here)

Work the numbers and the strategy falls out on its own.

- The target trade in one metro might be **~15,000–25,000 people** total (licensed
  practitioners plus apprentices/helpers across the surrounding counties).
- That is **far too small** for Meta to isolate cleanly with detailed targeting.
  Occupation isn't a clean targeting facet, and layering filters to approximate it
  just shrinks and distorts the pool.
- But here's the thing: a B2B offer like this often only needs a **handful of
  partners** to be full — and a couple dozen leads a year to be a success.
- At typical metro CPMs, even *untargeted* delivery that reaches a few thousand of
  the right-city adults will surface the small number of your niche who are ready
  to act. **You are not buying efficiency. You are buying two or three
  conversations.**

The conclusion: don't pay (in reach, in delivery quality, in fragility) to
micro-target an occupation Meta can't cleanly see. Cast wide over the right
geography and let the copy filter.

---

## Ad-set structure

A practical three-tier structure, from broadest to most speculative.

### Ad set A — Broad, copy-filtered *(launch, primary budget)*

- **Location:** the metro + a generous radius (large enough to cover the suburbs
  where your audience actually lives and works).
- **Age:** a wide working-age band. **Gender: all** — don't exclude. (Leaving
  gender open is also a Special-Ad-Category-safe habit, and office/dispatch staff
  of any gender may forward a good ad to the crew.)
- **Detailed targeting:** **none** (broad). Turn Meta's automatic audience
  expansion **on**, with location and age as the hard bounds.
- **Placements:** automatic, but consider turning **Audience Network off** for
  lead forms (it tends to produce junk leads).
- **Creatives:** units whose **first line is an occupational callout** ("Local
  plumbers:", "Local HVAC techs:"). The callout is what does the filtering —
  the right reader self-selects in the first three words.

### Ad set B — Interest-narrowed *(launch, test against A)*

- Same geography and age as A. **Detailed targeting:** add trade-relevant
  interests (search Ads Manager for the trade name and adjacent terms — the tool,
  the craft, "home repair," "construction," and whatever employer-adjacent
  interests Meta suggests).
- Expect this segment to be **loose** — interest targeting for a trade sweeps in
  DIY homeowners and hobbyists. That's fine: the **copy filters again.** The
  interest layer just tilts delivery slightly toward the trade.
- **Verdict after ~7 days:** if the cost-per-lead of B is meaningfully below A,
  keep both; otherwise consolidate B's budget into A. Interest targeting earns its
  keep only if it actually lowers CPL.

### Ad set C — The hard-to-reach qualifier *(small test budget)*

This is the compliant approximation of a qualifier Meta can't target directly
(the running example: "recently relocated"). Try, in order:

1. **A life-event segment, if one exists.** Meta has historically offered
   life-event segments (e.g. a "recently moved" style segment). **Verify it still
   exists at build time** — Meta prunes segments constantly. If present, layer it
   on the broad-metro base (do **not** also stack occupation interests — that gets
   too narrow to deliver) and run your relocation-story creative.
2. **A lateral interest proxy.** Interests that only your qualifier would plausibly
   have — e.g. out-of-state sports-team fandom for someone who moved from another
   state — combined with the metro location. This is delightfully sideways and
   fully compliant (sports interests are not sensitive attributes). Expect tiny
   reach; treat it as a sniper test, its own small ad set, one creative.
3. **If neither exists or performs: kill the ad set** and let the
   relocation-story creative simply run **inside Ad set A.** The story still finds
   your qualifier in a broad feed — this is the expected end state. C is a bonus
   if it works, not a dependency.

### Retargeting *(from week two)*

- Custom audiences from **your own** engagement: form **opened-but-not-submitted**
  (7/30-day), Page/profile engagers (30-day), video viewers if you run video.
- Creatives: your trust-anchor and closer units. Keep the budget small at first —
  the pool is tiny until reach accumulates.

---

## The compliant way to reach a "life-situation" qualifier

When your best angle depends on a life situation Meta won't let you target (moved
recently, changed jobs, new to the area), reach it with a **stack of compliant
proxies plus creative**, never a direct claim:

1. **Life-event segment** (if it currently exists — verify).
2. **Interest proxies** that correlate with the situation but aren't sensitive
   (the out-of-state-sports-team trick).
3. **Third-person creative** as the real workhorse: a story about *someone else*
   in that situation ("a tradesperson who moved here from out of state told
   me…"), or a conditional ("if you came here for a bigger opportunity…"). The
   story finds the right people inside a broad feed **and** it's compliant,
   because it never claims to know anything about the reader. (See the compliance
   playbook's personal-attributes section for why the direct version — "Did you
   just move here?" — is prohibited.)

The proxies tilt delivery; the creative does the selecting and stays legal.

---

## What Meta does NOT allow (settled, so nobody re-litigates it)

- **Targeting Facebook Groups.** You cannot target the members of a group ("moved
  from X to Y" groups, trade groups). Meta has never allowed group targeting. The
  groups play is **organic** — join as yourself and post/comment where the rules
  allow. That's a free channel with zero ad-policy exposure, and it pairs well
  with any in-person motion.
- **Targeting by employer.** Employer targeting was removed from detailed
  targeting. You cannot make an ad set of "people who work at Company X." Reaching
  a specific employer's staff is a job for **other channels** (e.g. cold email or
  in-person), not Meta ads.
- **Uploading a scraped list as a Custom Audience.** Custom-Audience terms require
  the data to have been collected with consent to share with Meta. Lists scraped
  from directories, chambers, maps, etc. **do not meet that bar** — uploading them
  risks the ad account. Keep those lists in your email/outreach channels, not in
  Ads Manager.
- **Zip-level "new mover" list bombing.** Beyond being non-compliant as a data
  source, it's also the wrong tool — a relocated professional is spread across a
  whole metro, not concentrated in a zip you can bomb.

---

## Measuring a qualifier you can't see in Ads Manager

You can't read "recently relocated" (or most life-situation qualifiers) in Meta's
reporting. So measure it **downstream**, in your own intake:

- On every callback/first conversation, ask a natural qualifying question ("how
  long have you been in the area / where did you come from?") and **log the
  answer.**
- If your qualifier **over-indexes** among the partners who actually convert
  (it usually will, if the thesis is right), shift budget toward the
  qualifier-story creative and Ad set C, and build **more story variants** —
  but only when a *true* story exists to ground each one. Don't fabricate a
  relocation story for a city you have no real anecdote from; invented stories
  read false and you can't defend them.

---

## Expansion (after the core funnel proves — not before)

Once the primary trade funnel is working, the same doctrine extends to adjacent
audiences with the **same broad-plus-callout structure**, just swapping the
first-line callout:

- **Adjacent trades** that encounter the same trigger event (for a water-damage
  referral offer, that's HVAC/AC techs via condensate/drain-pan issues,
  leak-detection and foundation crews, etc.). Same creatives, new callout: "Local
  HVAC techs:".
- **Higher-volume B2B relationships** (e.g. property managers) — but these usually
  have different economics and need their own offer math before you point ads at
  them.

Prove the core before expanding. A working broad-plus-copy funnel is a template
you can re-aim; a broken one just multiplies the problem.

---

## The one-paragraph version

For a niche B2B micro-audience, stop trying to make Meta's targeting do the
selecting — it can't isolate one trade in one city, and forcing it just builds a
fragile, undeliverable ad set. Cast a **wide** net over the right **geography and
age**, and let the **creative** select: an occupational callout in the first line
filters the trade, and a third-person story reaches a life-situation qualifier you
can't legally target. Layer compliant proxies (life-event segments, lateral
interests) as bonuses, never dependencies. And know the hard walls — no group
targeting, no employer targeting, no uploading scraped lists — so you don't waste
a cycle trying. The creative is the targeting; the settings just narrow the pond.
