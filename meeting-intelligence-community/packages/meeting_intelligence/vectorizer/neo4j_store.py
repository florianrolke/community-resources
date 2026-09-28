"""Neo4j graph and vector storage for meeting transcripts."""

from __future__ import annotations

from neo4j import GraphDatabase

from .chunking import chunk_text
from .embeddings import embed_text


def driver(settings):
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def ensure_schema(settings) -> None:
    with driver(settings) as drv, drv.session() as session:
        session.run("CREATE CONSTRAINT meeting_source_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.source_id IS UNIQUE")
        session.run("CREATE CONSTRAINT person_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE")
        session.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:TranscriptChunk) REQUIRE c.id IS UNIQUE")
        session.run("CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE")
        session.run("CREATE CONSTRAINT project_name IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE")
        session.run(
            f"""
            CREATE VECTOR INDEX transcript_chunk_embedding IF NOT EXISTS
            FOR (c:TranscriptChunk) ON (c.embedding)
            OPTIONS {{indexConfig: {{
              `vector.dimensions`: {settings.embedding_dimension},
              `vector.similarity_function`: 'cosine'
            }}}}
            """
        )
        session.run(
            f"""
            CREATE VECTOR INDEX meeting_summary_embedding IF NOT EXISTS
            FOR (m:Meeting) ON (m.summary_embedding)
            OPTIONS {{indexConfig: {{
              `vector.dimensions`: {settings.embedding_dimension},
              `vector.similarity_function`: 'cosine'
            }}}}
            """
        )


def vectorize_meeting_artifact(settings, artifact: dict) -> None:
    ensure_schema(settings)
    participant = artifact.get("participant", {})
    summary = artifact.get("summary", {})
    transcript = artifact.get("transcript_text", "")
    chunks = chunk_text(transcript, settings.chunk_words, settings.chunk_overlap_words)
    summary_text = "\n".join(summary.get("meeting_summary") or [])
    summary_embedding = embed_text(settings, summary_text or artifact.get("title", ""))

    with driver(settings) as drv, drv.session() as session:
        session.execute_write(_upsert_meeting, artifact, participant, summary, summary_embedding)
        for chunk in chunks:
            chunk_id = f"{artifact['source_id']}:{chunk['chunk_index']}"
            embedding = embed_text(settings, chunk["text"])
            session.execute_write(_upsert_chunk, artifact["source_id"], chunk_id, chunk, embedding)


def _upsert_meeting(tx, artifact: dict, participant: dict, summary: dict, summary_embedding: list[float]):
    tx.run(
        """
        MERGE (m:Meeting {source_id: $source_id})
        SET m.title = $title,
            m.meeting_date = $meeting_date,
            m.doc_url = $doc_url,
            m.gmail_draft_id = $draft_id,
            m.summary = $summary_text,
            m.summary_embedding = $summary_embedding
        MERGE (p:Person {email: $email})
        SET p.name = $name
        MERGE (p)-[:MET_AT]->(m)
        MERGE (p)-[:MENTIONED_IN]->(m)
        """,
        source_id=artifact["source_id"],
        title=artifact.get("title", ""),
        meeting_date=artifact.get("meeting_date", ""),
        doc_url=(artifact.get("doc") or {}).get("doc_url", ""),
        draft_id=(artifact.get("gmail") or {}).get("draft_id", ""),
        summary_text="\n".join(summary.get("meeting_summary") or []),
        summary_embedding=summary_embedding,
        email=participant.get("email") or f"unknown-{artifact['source_id']}@local",
        name=participant.get("name", "Meeting Participant"),
    )
    for topic in summary.get("topics") or []:
        tx.run(
            """
            MATCH (m:Meeting {source_id: $source_id})
            MERGE (t:Topic {name: $topic})
            MERGE (m)-[:DISCUSSED]->(t)
            """,
            source_id=artifact["source_id"],
            topic=topic,
        )
    for item in summary.get("projects_mentioned") or []:
        name = item.get("name") if isinstance(item, dict) else str(item)
        if name:
            tx.run(
                """
                MATCH (m:Meeting {source_id: $source_id})
                MERGE (p:Project {name: $name})
                SET p.description = coalesce($context, p.description)
                MERGE (m)-[:DISCUSSED]->(p)
                """,
                source_id=artifact["source_id"],
                name=name,
                context=item.get("context", "") if isinstance(item, dict) else "",
            )
    for action in summary.get("action_items") or []:
        tx.run(
            """
            MATCH (m:Meeting {source_id: $source_id})
            CREATE (a:ActionItem {text: $text})
            MERGE (m)-[:HAS_ACTION_ITEM]->(a)
            """,
            source_id=artifact["source_id"],
            text=action,
        )


def _upsert_chunk(tx, source_id: str, chunk_id: str, chunk: dict, embedding: list[float]):
    tx.run(
        """
        MATCH (m:Meeting {source_id: $source_id})
        MERGE (c:TranscriptChunk {id: $chunk_id})
        SET c.text = $text,
            c.chunk_index = $chunk_index,
            c.word_start = $word_start,
            c.word_end = $word_end,
            c.content_hash = $content_hash,
            c.embedding = $embedding
        MERGE (m)-[:HAS_CHUNK]->(c)
        """,
        source_id=source_id,
        chunk_id=chunk_id,
        text=chunk["text"],
        chunk_index=chunk["chunk_index"],
        word_start=chunk["word_start"],
        word_end=chunk["word_end"],
        content_hash=chunk["content_hash"],
        embedding=embedding,
    )


def search_transcripts(settings, query: str, limit: int = 5) -> list[dict]:
    embedding = embed_text(settings, query)
    with driver(settings) as drv, drv.session() as session:
        result = session.run(
            """
            CALL db.index.vector.queryNodes('transcript_chunk_embedding', $limit, $embedding)
            YIELD node, score
            MATCH (m:Meeting)-[:HAS_CHUNK]->(node)
            RETURN score, node.text AS text, m.title AS title, m.source_id AS source_id, m.meeting_date AS meeting_date
            ORDER BY score DESC
            """,
            limit=limit,
            embedding=embedding,
        )
        return [dict(record) for record in result]


def person_history(settings, email: str) -> list[dict]:
    with driver(settings) as drv, drv.session() as session:
        result = session.run(
            """
            MATCH (p:Person {email: $email})-[:MET_AT]->(m:Meeting)
            RETURN m.source_id AS source_id, m.title AS title, m.meeting_date AS meeting_date, m.doc_url AS doc_url
            ORDER BY m.meeting_date DESC
            """,
            email=email,
        )
        return [dict(record) for record in result]
