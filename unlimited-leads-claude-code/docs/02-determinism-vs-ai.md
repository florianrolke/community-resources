# Determinism vs probabilism

The course's best idea, and the one this repo enforces rather than suggests.

## The idea

An LLM gives you a different answer every time. That's the point of it, and it's
also the problem: anything you can't predict, you can't test, and anything you
can't test you can't improve.

So use it for exactly the part that has to vary, and nothing else.

In cold email, exactly one thing has to vary per prospect: the line proving you
looked them up. Everything else — your positioning, your proof, your ask — is
the same for every prospect in the niche. You wrote it, you tested it, it works.

```
Hi {first_name},

{opener}                   <-- AI. one line. per lead.

Most companies scaling this fast hit the same bottleneck: {pain_point}.

We helped {similar_company} solve this and saw {metric} in 60 days.

Worth a 15-min chat to see if we can do the same for {company}?

{sender_name}
```

Four of those placeholders are CLI arguments. One is the lead's name. One is the
model's. That ratio is the design.

## Why it matters more than it sounds

**You can A/B test it.** Change the pain point, send another 200, compare. If the
model rewrote the whole email each time you'd have no idea what moved the number.

**It can't drift.** Ask a model for 500 emails and somewhere around 300 one of
them will be too familiar, or invent a case study, or promise something you don't
do. A fixed template cannot.

**You can fix it in one place.** The offer changes, you edit
`templates/email_template.md`. Not 500 emails, not a prompt you have to re-tune.

**It's honest.** The model never sees your pricing or your client list, so it
can't embellish either.

## Where the repo draws the line

| AI writes | You write |
|---|---|
| The five research facts, each with a source | The email body |
| The subject line (constrained) | The pain point |
| The "I noticed…" opener (constrained) | The social proof and metric |
| The LinkedIn request (constrained) | The call to action |
| A 50-word website summary | Every follow-up in the sequence |

Note what's missing from the left column: nothing that states a fact about *you*.

## Constrained means checked

"Constrained" isn't a prompt instruction. `write_outreach.py` checks:

```
subject starts with "Quick question about {Company}'s", 11 words max
body starts with "I noticed {Company} recently", 15 words max
no "Congratulations" / "Congrats" / "amazing" / "great work"
no years, no month names, no quoted event names
LinkedIn request 200 chars max, no "building my network"
```

Fail once and the specific reason goes back to the model for a retry. Fail twice
and the lead is held out with a note, not shipped.

The n8n version had the same rules in the same prompt. It just had nowhere to put
the check — a Structured Output Parser validates that you got a string called
`subject`, not that the string is short enough. See `00-why-not-n8n.md`.

## Applying it elsewhere

The pattern generalizes. Ask twice:

1. What genuinely has to differ per record?
2. What am I only letting the model write because it's easier than writing it myself?

The second list should be empty. Everything in it is variance you didn't need,
can't test, and will eventually have to apologize for.
