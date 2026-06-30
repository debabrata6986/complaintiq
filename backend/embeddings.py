"""Semantic embedding engine for ComplaintIQ.

Wraps sentence-transformers (all-MiniLM-L6-v2) with:
- Thread-safe LRU cache for individual texts
- Batch embedding generation
- Lazy model loading (model downloaded once on first use)
- Graceful degradation: if sentence-transformers is unavailable, raises
  ImportError so callers can fall back to TF-IDF via the hybrid engine.

Usage:
    from embeddings import get_embedder
    embedder = get_embedder()
    vec = embedder.encode_one("my text")             # → np.ndarray (384,)
    vecs = embedder.encode_batch(["a", "b", "c"])    # → np.ndarray (3, 384)
"""
from __future__ import annotations

import hashlib
import logging
import threading
from functools import lru_cache
from typing import Any, Sequence

import numpy as np

from config import cfg

logger = logging.getLogger("complaintiq.embeddings")

# ---------------------------------------------------------------------------
# Internal cache: text → embedding vector
# ---------------------------------------------------------------------------
_CACHE_LOCK = threading.Lock()
_EMBEDDING_CACHE: dict[str, np.ndarray] = {}
_MAX_CACHE = cfg.embedding.cache_size


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


def _cache_get(text: str) -> np.ndarray | None:
    return _EMBEDDING_CACHE.get(_cache_key(text))


def _cache_set(text: str, vec: np.ndarray) -> None:
    key = _cache_key(text)
    with _CACHE_LOCK:
        if len(_EMBEDDING_CACHE) >= _MAX_CACHE:
            # Evict oldest 10 %
            to_delete = list(_EMBEDDING_CACHE.keys())[: _MAX_CACHE // 10]
            for k in to_delete:
                _EMBEDDING_CACHE.pop(k, None)
        _EMBEDDING_CACHE[key] = vec


# ---------------------------------------------------------------------------
# Model wrapper
# ---------------------------------------------------------------------------

class SentenceEmbedder:
    """Thread-safe wrapper around a SentenceTransformer model."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._model_name = cfg.embedding.model_name
        self._dim = cfg.embedding.dimension
        self._batch_size = cfg.embedding.batch_size

    def _load(self) -> Any:
        """Lazy-load the model (downloads ~22 MB on first call)."""
        if self._model is None:
            with self._lock:
                if self._model is None:  # double-check inside lock
                    try:
                        from sentence_transformers import SentenceTransformer
                        logger.info("Loading sentence-transformer model: %s", self._model_name)
                        self._model = SentenceTransformer(self._model_name)
                        logger.info("Model loaded successfully (dim=%d)", self._dim)
                    except ImportError as exc:
                        raise ImportError(
                            "sentence-transformers is not installed. "
                            "Run: pip install sentence-transformers"
                        ) from exc
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    def encode_one(self, text: str, use_cache: bool = True) -> np.ndarray:
        """Encode a single text string → 1-D numpy float32 array."""
        if not text or not text.strip():
            return np.zeros(self._dim, dtype=np.float32)
        text = text.strip()
        if use_cache:
            cached = _cache_get(text)
            if cached is not None:
                return cached
        model = self._load()
        vec = model.encode(text, show_progress_bar=False, convert_to_numpy=True)
        vec = vec.astype(np.float32)
        if use_cache:
            _cache_set(text, vec)
        return vec

    def encode_batch(
        self,
        texts: Sequence[str],
        use_cache: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Encode a list of texts → 2-D numpy float32 array (N, dim).

        Uses the cache for texts that have already been encoded, only
        sending uncached texts through the model.
        """
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)

        results: list[np.ndarray | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, t in enumerate(texts):
            t_clean = (t or "").strip()
            if not t_clean:
                results[i] = np.zeros(self._dim, dtype=np.float32)
                continue
            if use_cache:
                cached = _cache_get(t_clean)
                if cached is not None:
                    results[i] = cached
                    continue
            uncached_indices.append(i)
            uncached_texts.append(t_clean)

        if uncached_texts:
            model = self._load()
            batch_vecs = model.encode(
                uncached_texts,
                batch_size=self._batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            ).astype(np.float32)
            for j, idx in enumerate(uncached_indices):
                vec = batch_vecs[j]
                results[idx] = vec
                if use_cache:
                    _cache_set(uncached_texts[j], vec)

        return np.vstack([r for r in results])  # type: ignore[arg-type]

    def cosine_similarity_one_to_many(
        self,
        query_vec: np.ndarray,
        corpus_vecs: np.ndarray,
    ) -> np.ndarray:
        """Compute cosine similarity of query_vec vs each row of corpus_vecs."""
        if corpus_vecs.shape[0] == 0:
            return np.array([], dtype=np.float32)
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-10
        corpus_normed = corpus_vecs / norms
        return (corpus_normed @ query_norm).astype(np.float32)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_EMBEDDER: SentenceEmbedder | None = None
_EMBEDDER_LOCK = threading.Lock()


def get_embedder() -> SentenceEmbedder:
    """Return the global SentenceEmbedder instance (created once)."""
    global _EMBEDDER
    if _EMBEDDER is None:
        with _EMBEDDER_LOCK:
            if _EMBEDDER is None:
                _EMBEDDER = SentenceEmbedder()
    return _EMBEDDER


def cache_stats() -> dict:
    """Return embedding cache statistics."""
    return {
        "cached_entries": len(_EMBEDDING_CACHE),
        "max_entries": _MAX_CACHE,
        "utilization_pct": round(len(_EMBEDDING_CACHE) / _MAX_CACHE * 100, 1),
    }
