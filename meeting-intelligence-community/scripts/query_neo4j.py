"""Run a semantic transcript query against Neo4j."""

from __future__ import annotations

import argparse
import json

from meeting_intelligence.core.config import settings
from meeting_intelligence.vectorizer.neo4j_store import search_transcripts


def main() -> int:
    parser = argparse.ArgumentParser(description="Search meeting transcripts")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(search_transcripts(settings(), args.query, args.limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
