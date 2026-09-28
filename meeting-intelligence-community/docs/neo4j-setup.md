# Neo4j Setup

## Docker Compose Default

The default stack runs Neo4j Community Edition:

```bash
docker compose -f deploy/docker-compose.yml up -d neo4j
python scripts/init_neo4j.py
```

Open Neo4j Browser at:

```text
http://localhost:7474
```

Default credentials:

```env
NEO4J_USER=neo4j
NEO4J_PASSWORD=meeting-intelligence-password
```

Change the password before using this in production.

## Aura or External Neo4j

Set:

```env
NEO4J_URI=neo4j+s://your-aura-host.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

## What Gets Written

Nodes:

- `Person`
- `Meeting`
- `TranscriptChunk`
- `Topic`
- `Project`
- `ActionItem`

Relationships:

- `(Person)-[:MET_AT]->(Meeting)`
- `(Person)-[:MENTIONED_IN]->(Meeting)`
- `(Meeting)-[:HAS_CHUNK]->(TranscriptChunk)`
- `(Meeting)-[:DISCUSSED]->(Topic|Project)`
- `(Meeting)-[:HAS_ACTION_ITEM]->(ActionItem)`

Vector indexes:

- `transcript_chunk_embedding`
- `meeting_summary_embedding`

## Verification Queries

```cypher
MATCH (n) RETURN labels(n), count(n);
SHOW VECTOR INDEXES;
MATCH (m:Meeting)-[:HAS_CHUNK]->(c:TranscriptChunk)
RETURN m.title, c.chunk_index, left(c.text, 120)
LIMIT 5;
```

Semantic query:

```bash
python scripts/query_neo4j.py "outreach copy improvements"
```
