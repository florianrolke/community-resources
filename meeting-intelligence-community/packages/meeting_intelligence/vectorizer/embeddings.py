"""Embedding providers."""

from __future__ import annotations

import hashlib
import math


def deterministic_embedding(text: str, dimension: int) -> list[float]:
    """Small local fallback for tests and demos, not semantic production search."""
    vector = [0.0] * dimension
    for token in (text or "").lower().split():
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dimension
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def embed_text(settings, text: str) -> list[float]:
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(model=settings.embedding_model, input=text)
        return response.data[0].embedding
    return deterministic_embedding(text, settings.embedding_dimension)
