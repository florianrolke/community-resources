# Picking a niche: the 3 Ps

The most valuable ninety seconds in the course, and the step people skip.

Everything downstream — the scraping, the research, the copy — multiplies whatever
you point it at. Point it at the wrong list and you just arrive at nothing faster.

## The test

A niche is worth pursuing only if it has **all three**. Two out of three is a no.

### Pain

A problem that costs them real money, on a recurring basis. Not an annoyance, not
a nice-to-have.

The test: can you put a number on it, monthly? "They lose about eight jobs a month
to slow follow-up, and a job is worth $2,400" is pain. "Their website looks dated"
is an opinion.

If you can't size it, you can't justify your price, and every call turns into a
debate about whether the problem is real.

### Purchasing power

Someone who can say yes at your price without convening a committee.

The test: is there one person who can sign? For a 12-truck HVAC company, the
owner decides on Tuesday. At a 900-person company, your champion needs procurement,
legal, and a budget cycle. Same deal size, six months apart.

This is why owner-operated local businesses convert faster than enterprises for
anyone starting out — not because they're easier to sell, because the yes is
one conversation.

### Presence

At least a thousand of them, and you can find them.

The test: can you build a list right now? Try it — Google Maps, a LinkedIn search,
an association directory. If you can't get to a thousand findable businesses, the
pipeline maths never works. A 2% reply rate on a list of 200 is four conversations,
and you can't build a business on four conversations.

This is the one that quietly kills good ideas. "Independent bookshops that also
run recording studios" has pain and purchasing power. There are nine of them.

## Test it before you build it

Fifteen minutes:

```bash
# Are there enough of them?
python -X utf8 scripts/02_local_businesses/scrape_google_maps.py \
    --search "YOUR NICHE in YOUR CITY" --limit 25 --out-csv output/niche_test.csv
```

Read the 25. Then:

- Fewer than 20 are actually your target → **Presence fails**, or your search term is wrong
- No websites, no emails, no reviews → **Presence fails**; you can't reach them
- You can't name a problem costing them $10k a year → **Pain fails**
- You'd be selling to a purchasing department → **Purchasing power fails**

Cost of that test: about two cents. Cost of skipping it: a month.

## ICP is a theory, not a decision

The course frames it well: your ideal customer profile is a hypothesis you're
testing, not a thing you decide once and defend.

Start deliberately narrow — "roofing contractors in coastal Alabama with 5–20
staff" — because narrow is testable. Send 50. Then read what happened:

- **Replies but no calls** → the offer is wrong, the list is fine
- **Calls but no closes** → wrong buyer, or wrong price
- **Neither** → wrong list. Change one variable and retest.

Change one thing at a time. If you change the niche and the copy together you
learn nothing from the result.

## Where the good ones cluster

Not a rule, just where it tends to work:

- **Owner-operated, 5–50 staff.** Big enough to have the problem and a budget, small enough that one person decides.
- **Trades and local services.** Roofing, HVAC, plumbing, landscaping, dental. Pain is measurable in booked jobs; the owner signs.
- **Growing, visibly.** A company that just opened a second location or hired ten people is already feeling the strain. That's also a trigger event for your opener — `--recently-changed-jobs` in System 1 filters for exactly this.
- **Somewhere you have any connection at all.** A shared city, a former industry, a client you already served. It raises reply rates more than any copy trick.

## And where they don't

- **Everyone.** "Small businesses" is not a niche.
- **Nine of them.** Presence fails.
- **Enterprise, as a first niche.** Long cycles, committees, and you'll run out of runway before the first close.
- **Whoever is loudest online.** Popular niches are saturated niches — every one of those prospects gets forty of these emails a week.

## Then go

Once a niche passes all three, the rest of this repo is mechanical:

```bash
python -X utf8 scripts/01_b2b_contacts/search_linkedin.py --titles "Owner" --locations "Alabama" --limit 25
```

Just don't start there.
