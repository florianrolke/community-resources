"""Initialize Neo4j constraints and vector indexes."""

from meeting_intelligence.core.config import settings
from meeting_intelligence.vectorizer.neo4j_store import ensure_schema


def main() -> int:
    ensure_schema(settings())
    print("Neo4j schema and vector indexes are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
