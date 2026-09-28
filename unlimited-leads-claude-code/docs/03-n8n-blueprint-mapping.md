# Every n8n node, and what replaced it

The original workflows are in `reference/n8n-original/`. Import them into n8n if
you want to see the canvas — but you don't need to; this table is the whole map.

**19 nodes in System 1. 13 in System 2. 32 total.**

Most of them turn into "—" because they were plumbing: model selectors, wait
nodes, loop nodes, trigger nodes. On a canvas those are objects you place and
wire. In a script they're a function argument or they simply don't exist.

## System 1 — B2B contacts (19 nodes)

| n8n node | Type | Replaced by |
|---|---|---|
| `When clicking ‘Execute workflow’` | manualTrigger | just run the script |
| `HTTP Request1` | httpRequest | `01_b2b_contacts/search_linkedin.py` (new actor) or `scrape_apify.py` (the video's) |
| `AI Agent1` | agent | `01_b2b_contacts/research_lead.py` |
| `ChatGPT1` | lmChatOpenAi | — (model choice is a `--model` flag) |
| `Claude1` | lmChatAnthropic | — (model choice is a `--model` flag) |
| `Subject + One liner` | agent | `04_outreach/write_outreach.py` + validators |
| `ChatGPT` | lmChatOpenAi | — (model choice is a `--model` flag) |
| `Think` | toolThink | — (adaptive thinking, on by default) |
| `LinkedIN` | httpRequestTool | — (removed: it was hardcoded to a demo profile) |
| `Website` | httpRequestTool | `fetch_website` tool inside `research_lead.py` |
| `Research` | tavilyTool | `tavily_search` tool inside `research_lead.py` |
| `Output` | outputParserStructured | the `SCHEMA` in `research_lead.py` (API-enforced, not hoped for) |
| `LinkedIN1` | httpRequestTool | `--mode full` on `search_linkedin.py` |
| `LinkedIN One liner` | agent | `04_outreach/write_outreach.py` + validators |
| `ChatGPT2` | lmChatOpenAi | — (model choice is a `--model` flag) |
| `Output1` | outputParserStructured | the `SUBJECT_SCHEMA` in `write_outreach.py` |
| `Append row in sheet` | googleSheets | `--out-csv` (or `--sheet-url` if you want Sheets) |
| `ChatGPT3` | lmChatOpenAi | — (model choice is a `--model` flag) |
| `ChatGPT4` | lmChatOpenAi | — (model choice is a `--model` flag) |

## System 2 — Google Maps (13 nodes)

| n8n node | Type | Replaced by |
|---|---|---|
| `When clicking ‘Test workflow’` | manualTrigger | just run the script |
| `Scrape Google Maps` | httpRequest | `02_local_businesses/scrape_google_maps.py` |
| `Code in JavaScript` | code | `--out-csv` column selection |
| `On form submission` | formTrigger | CLI arguments |
| `Edit Fields` | set | — (this node had a bug; see below) |
| `Loop Over Items` | splitInBatches | — (the actor handles batching) |
| `Scrape Site` | httpRequest | `--contacts` flag (was a whole node) |
| `Wait` | wait | — (not needed; no per-item HTTP loop) |
| `Code in JavaScript1` | code | `extract_website_contacts.py` |
| `AI Agent` | agent | `02_local_businesses/summarize_website.py` |
| `OpenAI Chat Model` | lmChatOpenAi | — (`--model` flag) |
| `Append row in sheet1` | googleSheets | `--out-csv` (or `--sheet-url`) |
| `Structured Output Parser` | outputParserStructured | the `SCHEMA` in `summarize_website.py` |

## Two real bugs in the originals

Not a dig — this is what the format does to you, and it's the clearest argument
for moving the logic into files.

**1. The Google Maps form input never reached the scraper.**
The `Edit Fields` node builds `Query = Leeds+Dentist {{ form search term }}` and
`Volume = 10 {{ form count }}` — prepending hardcoded values to whatever you
typed. Then the `Scrape Google Maps` node ignores both and uses a static body:
`locationQuery: "leeds"`, `searchStringsArray: ["dentist"]`,
`maxCrawledPlacesPerSearch: 10`.

So the form is decorative. Whatever you type, you get 10 dentists in Leeds. You
would only find out by noticing the results had nothing to do with your input.

**2. The summary column wrote an object.**
`Append row in sheet1` maps `Summary` to `{{ $json.output }}` — the whole object
— instead of `{{ $json.output.summary }}`. Everyone who ran it got `[object Object]`
in that column.

Neither bug is exotic. Both are invisible on a canvas: no type checking, no diff,
no test, and the wiring is a picture rather than something you can read top to
bottom. In a script, the first is an unused variable and the second is caught the
first time you look at the output — which is why `summarize_website.py` returns a
typed dict and the CSV writer names its columns.

## What carried over unchanged

The four AI prompts. They're good, and they're in `prompts/`, word for word:

| File | From node |
|---|---|
| `prompts/research_agent.md` | `AI Agent1` |
| `prompts/subject_and_opener.md` | `Subject + One liner` |
| `prompts/linkedin_request.md` | `LinkedIN One liner` |
| `prompts/website_summary.md` | `AI Agent` (System 2) |

The difference is what happens around them. The n8n version asked the model to
keep subjects under 11 words. This one asks *and then checks*, and feeds the
failure back for a retry. Same prompt, enforced instead of hoped for.
