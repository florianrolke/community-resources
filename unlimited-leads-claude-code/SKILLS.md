# Skills

Eight skills live in `.claude/skills/`. Open Claude Code in this folder and ask
for what you want — it picks the right one. You can also just read them; they're
the operating manual for each system.

| Skill | Use it when |
|---|---|
| [`free-lead-scraping`](.claude/skills/free-lead-scraping/SKILL.md) | No budget, no keys. **Start here.** |
| [`finding-local-businesses`](.claude/skills/finding-local-businesses/SKILL.md) | Local businesses in a city — System 2 |
| [`finding-b2b-contacts`](.claude/skills/finding-b2b-contacts/SKILL.md) | People with a job title — System 1 |
| [`researching-leads`](.claude/skills/researching-leads/SKILL.md) | Find a trigger event per lead |
| [`writing-cold-outreach`](.claude/skills/writing-cold-outreach/SKILL.md) | Emails and connection requests |
| [`verifying-emails`](.claude/skills/verifying-emails/SKILL.md) | Before a campaign, to avoid bounces |
| [`exporting-to-google-sheets`](.claude/skills/exporting-to-google-sheets/SKILL.md) | Only if you want a live shared sheet |
| [`extending-this-repo`](.claude/skills/extending-this-repo/SKILL.md) | Adding your own source or step |

## Trying it

```
find me 50 barbers in Tuscaloosa AL and write me LinkedIn connection requests
```

It runs the setup check, picks `finding-local-businesses` then
`writing-cold-outreach`, and hands you a CSV.

## Why they're in a dot-folder

Claude Code only auto-discovers skills at `.claude/skills/`. The code deliberately
lives in the visible `scripts/` tree instead, and every script runs on its own
without Claude Code ever being opened.

That split is the repo's thesis in miniature: a thin declarative skill that says
*when* and *why*, over a deterministic script that does the work the same way
every time. It's the same reason the email template is a fixed file and the model
only fills one line.
