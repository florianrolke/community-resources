# Why this isn't in n8n

Not because n8n is bad. Because the thing it was solving stopped being the hard part.

## What n8n was for

In 2024, wiring an LLM to an API meant writing a client, handling auth, parsing
responses, managing retries. n8n removed all of that. You dragged a node, filled
in a field, connected an arrow. For someone who didn't write code, it was the
difference between having an automation and not.

Jack's course is a good example of that done well: 32 nodes across two workflows,
carefully assembled, and it worked.

## What changed

Writing the code stopped being the bottleneck. You can now describe what you want
and get a working script — so the value of a visual builder drops to whatever
it's worth *after* the code exists.

At that point the trade looks different:

| | Canvas | File |
|---|---|---|
| Read the whole thing | click through 32 nodes | scroll one page |
| See what changed | you can't | `git diff` |
| Enforce a rule | ask the model in a prompt | `assert` |
| Recover from a crash at item 400 | start over | `--resume` |
| Give it to someone | screen-share, or export JSON they can't read | `git clone` |
| Search for where X happens | open every node | `grep` |
| Run it | keep the canvas open, or self-host | `python script.py` |
| Cost | subscription + API | API |

## The one that actually matters

Everything above is convenience. This one is correctness.

The course's outreach prompt says: keep the subject under 11 words, start the
body with "I noticed", don't congratulate anyone, don't mention dates. Good
instructions. The model follows them most of the time.

Most of the time is the problem. On a canvas there is nowhere to put a check.
The Structured Output Parser node validates *shape* — that you got a `subject`
and a `body` — not *content*. A 14-word subject is a perfectly valid string. It
goes into the sheet, and out to a prospect, and you find out never.

In a file, that's four lines:

```python
if len(subject.split()) > 11:
    return f"Subject is {len(subject.split())} words; the limit is 11."
```

`write_outreach.py` runs that check plus seven more, feeds any failure back to
the model once with the specific reason, and holds the lead out with a note if
it still fails. The prompt is unchanged — it's Jack's, word for word. What
changed is that the request became a guarantee.

That's the whole argument. Prompts ask. Code enforces. Once writing the code is
cheap, there's no reason to keep only asking.

## The bugs

Two of them shipped in the original workflows, and both are the kind the format
invites — see `03-n8n-blueprint-mapping.md`. The Google Maps form input never
reached the scraper, so every run returned dentists in Leeds regardless of what
you typed. And the summary column wrote `[object Object]`.

Neither is a mistake about lead generation. Both are mistakes you can't see when
the logic is a picture: no types, no diff, no test, no way to read it top to
bottom.

## When n8n is still right

- You need it running on a schedule in the cloud tomorrow and don't want to think about hosting
- The workflow is genuinely event-driven — a webhook fires, three things happen
- Non-technical colleagues need to modify it themselves
- It's already built and working

Those are real. This repo just isn't any of them.

## What to take from the course anyway

The tooling aged. The thinking didn't:

- **The 3 Ps** — Pain, Purchasing power, Presence. Best ninety seconds in the video.
- **Determinism vs probabilism** — hardcode the template, let AI fill one slot. This repo enforces it.
- **Trigger events** — "I noticed you opened a second location" beats anything generic.
- **The follow-up is the campaign** — one email isn't outreach.

All four are in here. The prompts are in `prompts/`, unchanged.
