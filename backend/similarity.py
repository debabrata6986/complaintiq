"""Lightweight TF-IDF similarity engine used by:
- Duplicate Complaint Detection Agent (compare new complaint vs historical)
- Knowledge Retrieval Agent (RAG over KB documents)

Avoids the 90MB+ download of sentence-transformers while still providing
genuine semantic-style retrieval. The vectorizer is rebuilt on each query
which is acceptable for MVP corpus sizes (< 100K docs).
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def top_k_similar(
    query: str,
    corpus: list[dict[str, Any]],
    text_field: str,
    k: int = 5,
    min_score: float = 0.05,
) -> list[tuple[dict[str, Any], float]]:
    """Returns top-k corpus items with cosine similarity score against the query."""
    if not corpus:
        return []
    texts = [str(item.get(text_field, "")) for item in corpus]
    texts_with_query = texts + [query]
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=20000)
        matrix = vec.fit_transform(texts_with_query)
    except ValueError:
        return []
    q_vec = matrix[-1]
    sims = cosine_similarity(q_vec, matrix[:-1]).flatten()
    idx = np.argsort(sims)[::-1][:k]
    results: list[tuple[dict[str, Any], float]] = []
    for i in idx:
        score = float(sims[i])
        if score >= min_score:
            results.append((corpus[i], round(score, 4)))
    return results
