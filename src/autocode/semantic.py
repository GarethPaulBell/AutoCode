"""Semantic search and embedding helpers extracted from `code_db.py`.

Provides:
- _get_embedding(text)
- _cosine_similarity(a,b)
- semantic_search_functions(query, top_k)

This module detects OpenAI availability independently to avoid coupling with the top-level module.
"""
from __future__ import annotations

import math
import hashlib
from typing import List

# Optional OpenAI detection
try:
    import openai
    HAVE_OPENAI = True
except Exception:
    openai = None
    HAVE_OPENAI = False


def _get_embedding(text: str):
    """Return an embedding vector for the provided text.
    Falls back to a deterministic hash-based pseudo-embedding when OpenAI is unavailable.
    """
    if HAVE_OPENAI and openai is not None:
        try:
            openai_version = getattr(openai, "__version__", "0.0.0")
            major_version = int(openai_version.split(".")[0])
            if major_version >= 1:
                resp = openai.embeddings.create(input=[text], model="text-embedding-ada-002")
                return resp.data[0].embedding
            else:
                resp = openai.Embedding.create(input=[text], model="text-embedding-ada-002")
                return resp["data"][0]["embedding"]
        except Exception:
            # If OpenAI call fails for any reason, fall back to hash-based embedding
            pass

    h = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in h[:64]]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_search_functions(db, query: str, top_k: int = 5):
    """Return top_k most semantically similar functions in the database to the query.

    `db` is expected to be the CodeDatabase instance; this function keeps the module independent
    from the concrete implementation of the DB by only relying on objects with `name`,
    `description`, and `code_snippet` attributes.
    """
    query_emb = _get_embedding(query)
    scored = []
    for func in db.functions.values():
        text = f"{func.name}\n{func.description}\n{func.code_snippet}"
        func_emb = _get_embedding(text)
        score = _cosine_similarity(query_emb, func_emb)
        scored.append((score, func))
    scored.sort(reverse=True, key=lambda x: x[0])
    results = []
    for score, func in scored[:top_k]:
        results.append({
            "id": func.function_id,
            "name": func.name,
            "description": func.description,
            "modules": getattr(func, "modules", []),
            "tags": getattr(func, "tags", []),
            "similarity": score,
        })
    return results
