# The 5-touch sequence

The course's number: roughly half of people stop after one message, and most
deals land somewhere between touch three and five. One email is not outreach.

`write_outreach.py` generates touch 1. These are the follow-ups. Same rule
applies — the copy is fixed, only `{opener}` was ever AI-written, and touches 2
through 5 don't need AI at all.

Suggested cadence: day 0, 3, 7, 12, 20. Stop the moment they reply.

---

## Touch 1 — the trigger event (day 0)

This is the one the script writes. See `email_template.md`.

---

## Touch 2 — the proof (day 3)

Reply in the same thread. No new subject line.

```
Hi {first_name},

Following up on the note above.

The {similar_company} case: {metric}. Happy to send the one-page breakdown of
how, if useful.

{sender_name}
```

---

## Touch 3 — the angle change (day 7)

They ignored the outcome. Try the problem instead.

```
Hi {first_name},

Different thought.

Most {industry} teams I speak to lose more deals to slow follow-up than to
price. Nobody plans it that way — it's just what happens when the pipeline
outgrows the process.

Is that a live problem for you, or have you already solved it?

{sender_name}
```

A question they can answer in three words does better than another pitch.

---

## Touch 4 — the useful thing (day 12)

Give something away with no ask attached.

```
Hi {first_name},

Not selling anything here.

I put together the checklist we use with {industry} teams to find where deals
stall. Takes about ten minutes and you don't need us to run it.

Want me to send it over?

{sender_name}
```

---

## Touch 5 — the close-out (day 20)

The one that gets the most replies. Make it genuinely final.

```
Hi {first_name},

I'll stop here — you're clearly busy and I don't want to keep landing in your
inbox.

If {pain_point} becomes a priority later, reply to this and I'll pick it back
up. No hard feelings either way.

{sender_name}
```

Mean it. Don't send a sixth.

---

## Rules

**One thread.** Reply to your own message; don't start a new subject each time.
**One idea per email.** Two asks gets you zero answers.
**Get shorter.** Touch 5 should be the shortest thing you send.
**Stop on reply.** Even a "not now" ends the sequence.
**Never fake a bump.** "Just floating this to the top of your inbox" fools nobody.

## Filling these in

The placeholders match the flags on `write_outreach.py`:
`{first_name}` `{similar_company}` `{metric}` `{pain_point}` `{sender_name}`,
plus `{industry}` which you set per campaign.

Write them once, well. They go out unchanged every time — which is exactly what
makes the sequence testable.
