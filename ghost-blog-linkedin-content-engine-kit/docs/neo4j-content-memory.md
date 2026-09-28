# Neo4j Content Memory

Neo4j is optional, but it makes the content engine much stronger. It lets the blog pull related stories, quotes, questions, meeting notes, and community examples from your own graph.

## Environment

Set at least:

```text
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

Optional secondary graphs:

```text
NEO4J_CONTENT_URI=
NEO4J_CONTENT_USER=
NEO4J_CONTENT_PASSWORD=
NEO4J_SKOOL_URI=
NEO4J_SKOOL_PASSWORD=
```

## Research Command

```bash
python scripts/neo4j_question_mining.py research --topic "AI agency first client" --slug ai-agency-first-client --max-nodes 500
```

The script scans common text-like properties and extracts question candidates. It writes:

- `.tmp/neo4j-question-mining/<slug>/raw-nodes.json`
- `.tmp/neo4j-question-mining/<slug>/question-candidates.json`
- `theme-notes/graph-faq-research/<slug>-graph-questions.md`

## Content Strategy

Use Neo4j to make posts enhance each other rather than compete:

- Pull adjacent stories into case studies.
- Find repeated questions that deserve FAQs.
- Link posts into pillars.
- Refresh older ranking posts instead of creating near-duplicates.

