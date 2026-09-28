# The original n8n workflows

Jack's two workflows from *UNLIMITED leads for FREE (FULL COURSE)*, included with
his permission, plus the course transcript.

| File | What |
|---|---|
| `n8n-original/system1-b2b-contacts.json` | System 1 — 19 nodes |
| `n8n-original/system2-google-maps.json` | System 2 — 13 nodes |
| `course-transcript.txt` | The full video transcript |

## Using them

Import into n8n via **⋯ → Import from File**. You'll need to supply your own
credentials — none are included.

## Read this instead

`docs/03-n8n-blueprint-mapping.md` maps all 32 nodes to what replaced them. It's
generated from these files, so it can't drift out of date, and it's a lot easier
to read than the JSON.

## A note on the two bugs

The mapping doc documents two defects in these workflows: the Google Maps form
input never reaches the scraper (every run returns dentists in Leeds regardless
of what you type), and the summary column writes `[object Object]`.

That's not a dig at Jack — it's the point. Both bugs are invisible on a canvas:
no types, no diff, no test, and the logic is a picture rather than something you
can read top to bottom. They're the clearest argument in the repo for moving
logic into files.
