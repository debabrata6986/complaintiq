"""Hybrid retrieval engine for ComplaintIQ.

Combines TF-IDF cosine similarity (the existing engine) with semantic
embedding similarity (sentence-transformers + ChromaDB) using configurable
weighted ranking.

This module replaces direct calls to `similarity.top_k_similar` in the
agent workflow.  The original `similarity.py` is preserved as the TF-IDF
backend and used as fallback when embeddings are unavailable.

Hybrid score = α * semantic_score + (1 - α) * tfidf_score
    where α = cfg.hybrid.semantic_weight
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from config import cfg
from similarity import top_k_similar as tfidf_top_k  # original TF-IDF engine

logger = logging.getLogger("complaintiq.hybrid")

# ---------------------------------------------------------------------------
# Hybrid duplicate complaint detection
# ---------------------------------------------------------------------------

def hybrid_similar_complaints(
    query: str,
    corpus: list[dict[str, Any]],
    text_field: str = "description",
    k: int = 5,
    min_score: float | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Hybrid semantic + TF-IDF complaint similarity.

    Args:
        query: The query text (new complaint description).
        corpus: List of complaint dicts with at least `id` and `text_field`.
        text_field: Field in each corpus dict containing the complaint text.
        k: Number of top results to return.
        min_score: Minimum hybrid score threshold.

    Returns:
        Sorted list of (complaint_dict, hybrid_score) tuples.
    """
    if min_score is None:
        min_score = cfg.hybrid.min_score_duplicate

    if not corpus:
        return []

    # --- TF-IDF scores (always available) ---
    tfidf_results = tfidf_top_k(query, corpus, text_field, k=len(corpus), min_score=0.0)
    tfidf_map: dict[str, float] = {}
    for doc, score in tfidf_results:
        doc_id = doc.get("id", id(doc))
        tfidf_map[str(doc_id)] = float(score)

    # Normalise TF-IDF scores to [0, 1]
    if tfidf_map:
        max_tfidf = max(tfidf_map.values()) or 1.0
        tfidf_map = {k: v / max_tfidf for k, v in tfidf_map.items()}

    # --- Semantic scores (may fail gracefully) ---
    semantic_map: dict[str, float] = {}
    try:
        from embeddings import get_embedder
        embedder = get_embedder()
        texts = [str(doc.get(text_field, "")) for doc in corpus]
        query_vec = embedder.encode_one(query)
        corpus_vecs = embedder.encode_batch(texts)
        sims = embedder.cosine_similarity_one_to_many(query_vec, corpus_vecs)
        for i, doc in enumerate(corpus):
            doc_id = str(doc.get("id", i))
            semantic_map[doc_id] = float(max(0.0, sims[i]))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Semantic embedding unavailable for complaint search: %s", exc)

    # --- Combine scores ---
    α = cfg.hybrid.semantic_weight if semantic_map else 0.0
    β = 1.0 - α  # tfidf weight
    scored: list[tuple[dict[str, Any], float]] = []
    for doc in corpus:
        doc_id = str(doc.get("id", id(doc)))
        sem = semantic_map.get(doc_id, 0.0)
        tfidf = tfidf_map.get(doc_id, 0.0)
        hybrid = α * sem + β * tfidf
        if hybrid >= min_score:
            scored.append((doc, round(hybrid, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ---------------------------------------------------------------------------
# Hybrid knowledge base retrieval
# ---------------------------------------------------------------------------

def hybrid_knowledge_search(
    query: str,
    corpus: list[dict[str, Any]],
    text_field: str = "content",
    k: int = 5,
    min_score: float | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Hybrid semantic + TF-IDF knowledge base retrieval.

    Args:
        query: The combined query string (summary + description + intent).
        corpus: List of KB document dicts.
        text_field: Field containing document content.
        k: Number of top results.
        min_score: Minimum hybrid score threshold.

    Returns:
        Sorted list of (doc_dict, hybrid_score) tuples.
    """
    if min_score is None:
        min_score = cfg.hybrid.min_score_knowledge

    if not corpus:
        return []

    # --- TF-IDF ---
    tfidf_results = tfidf_top_k(query, corpus, text_field, k=len(corpus), min_score=0.0)
    tfidf_map: dict[str, float] = {}
    for doc, score in tfidf_results:
        doc_id = str(doc.get("id", id(doc)))
        tfidf_map[doc_id] = float(score)

    if tfidf_map:
        max_tfidf = max(tfidf_map.values()) or 1.0
        tfidf_map = {k: v / max_tfidf for k, v in tfidf_map.items()}

    # --- Semantic ---
    semantic_map: dict[str, float] = {}
    try:
        from embeddings import get_embedder
        embedder = get_embedder()
        texts = [str(doc.get(text_field, "")) for doc in corpus]
        query_vec = embedder.encode_one(query)
        corpus_vecs = embedder.encode_batch(texts)
        sims = embedder.cosine_similarity_one_to_many(query_vec, corpus_vecs)
        for i, doc in enumerate(corpus):
            doc_id = str(doc.get("id", i))
            semantic_map[doc_id] = float(max(0.0, sims[i]))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Semantic embedding unavailable for knowledge search: %s", exc)

    # --- Combine ---
    α = cfg.hybrid.semantic_weight if semantic_map else 0.0
    β = 1.0 - α
    scored: list[tuple[dict[str, Any], float]] = []
    for doc in corpus:
        doc_id = str(doc.get("id", id(doc)))
        sem = semantic_map.get(doc_id, 0.0)
        tfidf = tfidf_map.get(doc_id, 0.0)
        hybrid = α * sem + β * tfidf
        if hybrid >= min_score:
            scored.append((doc, round(hybrid, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ---------------------------------------------------------------------------
# Retrieval metadata: expose which method contributed to a result
# ---------------------------------------------------------------------------

def retrieval_info(query: str, corpus: list[dict[str, Any]], text_field: str = "content") -> dict:
    """Diagnostic breakdown of hybrid retrieval weights used."""
    sem_available = False
    try:
        from embeddings import get_embedder
        get_embedder()._load()
        sem_available = True
    except Exception:
        pass

    α = cfg.hybrid.semantic_weight if sem_available else 0.0
    return {
        "semantic_weight": α,
        "tfidf_weight": 1.0 - α,
        "semantic_available": sem_available,
        "corpus_size": len(corpus),
    }
