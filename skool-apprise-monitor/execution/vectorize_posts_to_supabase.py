#!/usr/bin/env python3
"""
Vectorize scraped Skool posts to Supabase pgvector.

Reads the JSON output from skool_post_scraper.py and:
1. Generates embeddings for post content (title + content + comments)
2. Upserts to `skool_posts` table in Supabase
3. Cross-references authors against leads database

Usage:
    python execution/vectorize_posts_to_supabase.py
    python execution/vectorize_posts_to_supabase.py --input .tmp/skool_posts_makerschool_latest.json
    python execution/vectorize_posts_to_supabase.py --community makerschool
    python execution/vectorize_posts_to_supabase.py --resume

Table schema (run in Supabase SQL Editor):
    See get_create_table_sql() output

Requires:
    pip install supabase openai python-dotenv
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TABLE_NAME = "skool_posts"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
BATCH_SIZE = 25
CHECKPOINT_INTERVAL = 50


def get_create_table_sql():
    return f"""
-- Skool posts table with pgvector embeddings
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id TEXT PRIMARY KEY,
    community TEXT NOT NULL,
    title TEXT,
    slug TEXT,
    content TEXT,
    author_name TEXT,
    author_id TEXT,
    author_profile_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    likes INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    pinned BOOLEAN DEFAULT FALSE,
    category TEXT,
    category_id TEXT,
    post_url TEXT,
    -- Comments stored as JSONB array
    comments JSONB DEFAULT '[]'::jsonb,
    -- Cross-reference fields
    in_database BOOLEAN DEFAULT FALSE,
    lead_services TEXT,
    lead_industries TEXT,
    lead_summary TEXT,
    -- Embedding
    embedding_text TEXT,
    embedding vector({EMBEDDING_DIMENSION}),
    -- Timestamps
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS skool_posts_embedding_idx
ON {TABLE_NAME}
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- Common query indexes
CREATE INDEX IF NOT EXISTS skool_posts_community_idx ON {TABLE_NAME} (community);
CREATE INDEX IF NOT EXISTS skool_posts_author_idx ON {TABLE_NAME} (author_name);
CREATE INDEX IF NOT EXISTS skool_posts_category_idx ON {TABLE_NAME} (category);
CREATE INDEX IF NOT EXISTS skool_posts_created_idx ON {TABLE_NAME} (created_at DESC);
CREATE INDEX IF NOT EXISTS skool_posts_in_database_idx ON {TABLE_NAME} (in_database);

-- Search function for posts (semantic similarity)
CREATE OR REPLACE FUNCTION search_posts(
    query_embedding vector({EMBEDDING_DIMENSION}),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10,
    filter_community text DEFAULT NULL
)
RETURNS TABLE (
    id text,
    community text,
    title text,
    author_name text,
    content text,
    category text,
    post_url text,
    in_database boolean,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp.id,
        sp.community,
        sp.title,
        sp.author_name,
        sp.content,
        sp.category,
        sp.post_url,
        sp.in_database,
        1 - (sp.embedding <=> query_embedding) as similarity
    FROM {TABLE_NAME} sp
    WHERE 1 - (sp.embedding <=> query_embedding) > match_threshold
      AND (filter_community IS NULL OR sp.community = filter_community)
    ORDER BY sp.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""


def build_embedding_text(post: dict) -> str:
    """Build the text used for embedding generation."""
    parts = []
    if post.get('title'):
        parts.append(f"Title: {post['title']}")
    if post.get('authorName'):
        parts.append(f"Author: {post['authorName']}")
    if post.get('category'):
        parts.append(f"Category: {post['category']}")
    if post.get('content'):
        # Truncate very long posts to keep embedding focused
        content = post['content'][:2000]
        parts.append(f"Content: {content}")

    # Include top comments for richer context
    comments = post.get('comments', [])
    if comments:
        comment_texts = []
        for c in comments[:5]:  # Top 5 comments
            author = c.get('authorName', 'Unknown')
            text = (c.get('content') or '')[:300]
            if text:
                comment_texts.append(f"{author}: {text}")
        if comment_texts:
            parts.append("Comments: " + " | ".join(comment_texts))

    return "\n".join(parts)


def load_posts(input_path: Path) -> list:
    """Load posts from JSON file."""
    print(f"\n[1] Loading posts from {input_path.name}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    posts = data.get('posts', data) if isinstance(data, dict) else data
    print(f"  Loaded {len(posts)} posts")
    return posts


def create_clients():
    """Create Supabase and OpenAI clients."""
    from supabase import create_client
    from openai import OpenAI
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return supabase, openai_client


def check_table(supabase) -> bool:
    """Check if skool_posts table exists."""
    print(f"\n[2] Checking table '{TABLE_NAME}'...")
    try:
        supabase.table(TABLE_NAME).select("id").limit(1).execute()
        print(f"  Table '{TABLE_NAME}' exists")
        return True
    except Exception:
        print(f"  Table '{TABLE_NAME}' does not exist.")
        print("\n  Run this SQL in Supabase SQL Editor:")
        print("  " + "-" * 60)
        print(get_create_table_sql())
        print("  " + "-" * 60)

        # Also save SQL to file
        sql_path = TMP_DIR / "create_skool_posts_table.sql"
        with open(sql_path, 'w') as f:
            f.write(get_create_table_sql())
        print(f"\n  SQL also saved to: {sql_path}")
        return False


def generate_embeddings(openai_client, texts: list) -> list:
    """Generate embeddings in batch."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def load_checkpoint(checkpoint_path: Path) -> set:
    """Load processed IDs from checkpoint."""
    if checkpoint_path.exists():
        with open(checkpoint_path, 'r') as f:
            return set(json.load(f).get('processed_ids', []))
    return set()


def save_checkpoint(checkpoint_path: Path, processed_ids: set):
    """Save processed IDs to checkpoint."""
    with open(checkpoint_path, 'w') as f:
        json.dump({'processed_ids': list(processed_ids)}, f)


def vectorize_posts(supabase, openai_client, posts: list, community: str):
    """Generate embeddings and upsert posts to Supabase."""
    checkpoint_path = TMP_DIR / f"vectorize_posts_{community}_checkpoint.json"
    processed_ids = load_checkpoint(checkpoint_path)

    if processed_ids:
        print(f"  Resuming: {len(processed_ids)} posts already processed")

    to_process = [p for p in posts if p.get('id') and p['id'] not in processed_ids]
    print(f"\n[3] Vectorizing {len(to_process)} posts...")

    if not to_process:
        print("  All posts already processed!")
        return

    inserted = 0
    errors = 0

    for i in range(0, len(to_process), BATCH_SIZE):
        batch = to_process[i:i + BATCH_SIZE]

        try:
            # Build embedding texts
            embedding_texts = [build_embedding_text(p) for p in batch]
            embeddings = generate_embeddings(openai_client, embedding_texts)

            records = []
            for post, embedding, emb_text in zip(batch, embeddings, embedding_texts):
                record = {
                    'id': post['id'],
                    'community': community,
                    'title': post.get('title', ''),
                    'slug': post.get('slug', ''),
                    'content': (post.get('content') or '')[:10000],  # Truncate very long posts
                    'author_name': post.get('authorName', ''),
                    'author_id': post.get('authorId', ''),
                    'author_profile_url': post.get('authorProfileUrl', ''),
                    'created_at': post.get('createdAt'),
                    'likes': post.get('likes', 0),
                    'comment_count': post.get('commentCount', 0),
                    'pinned': post.get('pinned', False),
                    'category': post.get('category', ''),
                    'category_id': post.get('categoryId', ''),
                    'post_url': post.get('postUrl', ''),
                    'comments': json.dumps(post.get('comments', [])),
                    'in_database': post.get('in_database', False),
                    'lead_services': post.get('lead_services', ''),
                    'lead_industries': post.get('lead_industries', ''),
                    'lead_summary': post.get('lead_summary', ''),
                    'embedding_text': emb_text[:5000],
                    'embedding': embedding,
                }
                records.append(record)

            supabase.table(TABLE_NAME).upsert(records).execute()

            inserted += len(batch)
            for p in batch:
                processed_ids.add(p['id'])

            if inserted % CHECKPOINT_INTERVAL == 0:
                save_checkpoint(checkpoint_path, processed_ids)

            pct = (i + len(batch)) / len(to_process) * 100
            print(f"  Progress: {inserted}/{len(to_process)} ({pct:.0f}%)")
            time.sleep(0.5)

        except Exception as e:
            print(f"  Error at batch {i}: {e}")
            errors += 1
            if errors > 5:
                print("  Too many errors, stopping.")
                save_checkpoint(checkpoint_path, processed_ids)
                break
            time.sleep(2)

    save_checkpoint(checkpoint_path, processed_ids)
    print(f"\n  Inserted/updated: {inserted} posts")
    if errors:
        print(f"  Errors: {errors}")

    # Clean checkpoint on full success
    if errors == 0 and checkpoint_path.exists():
        checkpoint_path.unlink()


def verify(supabase, community: str):
    """Verify results."""
    print(f"\n[4] Verifying...")
    try:
        result = supabase.table(TABLE_NAME).select("id", count="exact").eq("community", community).execute()
        total = result.count if hasattr(result, 'count') and result.count else len(result.data)
        print(f"  Total posts for '{community}': {total}")

        result = supabase.table(TABLE_NAME).select(
            "author_name, title, category, likes"
        ).eq("community", community).order("likes", desc=True).limit(5).execute()
        print("  Top posts by likes:")
        for r in result.data:
            print(f"    [{r.get('category','')}] {r['author_name']}: {r['title'][:50]} ({r['likes']} likes)")

        # Count by category
        result = supabase.table(TABLE_NAME).select(
            "category"
        ).eq("community", community).execute()
        cats = {}
        for r in result.data:
            c = r.get('category') or 'Uncategorized'
            cats[c] = cats.get(c, 0) + 1
        print("  Posts by category:")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")

    except Exception as e:
        print(f"  Verification error: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Vectorize Skool posts to Supabase")
    parser.add_argument("--input", type=str, help="Path to posts JSON file")
    parser.add_argument("--community", type=str, default="makerschool", help="Community slug")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--print-sql", action="store_true", help="Print CREATE TABLE SQL and exit")
    args = parser.parse_args()

    print("=" * 60)
    print("SKOOL POST VECTORIZER")
    print("=" * 60)

    if args.print_sql:
        print(get_create_table_sql())
        return

    # Find input file
    if args.input:
        input_path = Path(args.input)
    else:
        # Look for latest scrape output
        input_path = TMP_DIR / f"skool_posts_{args.community}_latest.json"
        if not input_path.exists():
            # Try any matching file
            matches = sorted(TMP_DIR.glob(f"skool_posts_{args.community}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                input_path = matches[0]

    if not input_path.exists():
        print(f"ERROR: No input file found at {input_path}")
        print(f"  Run the scraper first: python execution/skool_post_scraper.py --community {args.community}")
        return

    # Check env
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        return

    try:
        supabase, openai_client = create_clients()
        print("  Clients created OK")
    except ImportError:
        print("ERROR: Missing packages. Run: pip install supabase openai python-dotenv")
        return

    if not check_table(supabase):
        print("\nCreate the table first, then re-run.")
        return

    posts = load_posts(input_path)
    vectorize_posts(supabase, openai_client, posts, args.community)
    verify(supabase, args.community)

    print(f"\n{'=' * 60}")
    print("POST VECTORIZATION COMPLETE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
