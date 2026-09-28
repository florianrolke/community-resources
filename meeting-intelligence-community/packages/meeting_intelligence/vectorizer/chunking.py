"""Transcript chunking utilities."""

from __future__ import annotations

import hashlib


def chunk_text(text: str, words_per_chunk: int = 420, overlap_words: int = 60) -> list[dict]:
    words = (text or "").split()
    if not words:
        return []
    chunks = []
    start = 0
    index = 0
    step = max(1, words_per_chunk - overlap_words)
    while start < len(words):
        end = min(len(words), start + words_per_chunk)
        chunk = " ".join(words[start:end])
        chunks.append({
            "chunk_index": index,
            "text": chunk,
            "word_start": start,
            "word_end": end,
            "content_hash": hashlib.sha1(chunk.encode("utf-8")).hexdigest(),
        })
        if end >= len(words):
            break
        start += step
        index += 1
    return chunks
