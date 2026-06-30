"""ChromaDB vector database integration for ComplaintIQ.

Manages two persistent collections:
  - complaints: stores complaint embeddings + metadata
  - knowledge_base: stores KB document embeddings + metadata

Provides:
  - Upsert (add / update) by document ID
  - Top-K semantic search with optional metadata filtering
  - Batch indexing
  - Background indexing support

The module is designed to be imported anywhere in the backend. The ChromaDB
client is a singleton created on first use (lazy loading).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Sequence

import numpy as np

from config import cfg
from embeddings import get_embedder

logger = logging.getLogger("complaintiq.vector_db")

# ---------------------------------------------------------------------------
# ChromaDB client singleton
# ---------------------------------------------------------------------------

_CLIENT = None
_CLIENT_LOCK = threading.Lock()


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                try:
                    import chromadb
                    persist_dir = cfg.vector_db.persist_directory
                    os.makedirs(persist_dir, exist_ok=True)
                    _CLIENT = chromadb.PersistentClient(path=persist_dir)
                    logger.info("ChromaDB initialised at %s", persist_dir)
                except ImportError as exc:
                    raise ImportError(
                        "chromadb is not installed. Run: pip install chromadb"
                    ) from exc
    return _CLIENT


# ---------------------------------------------------------------------------
# Collection accessors (lazy creation)
# ---------------------------------------------------------------------------

def _get_collection(name: str):
    """Get or create a ChromaDB collection."""
    client = _get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _complaints_col():
    return _get_collection(cfg.vector_db.complaints_collection)


def _knowledge_col():
    return _get_collection(cfg.vector_db.knowledge_collection)


# ---------------------------------------------------------------------------
# Complaint indexing
# ---------------------------------------------------------------------------

def index_complaint(
    complaint_id: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Embed and upsert a single complaint into the vector store."""
    try:
        embedder = get_embedder()
        vec = embedder.encode_one(description)
        col = _complaints_col()
        col.upsert(
            ids=[complaint_id],
            embeddings=[vec.tolist()],
            documents=[description[:512]],  # ChromaDB stores a text excerpt
            metadatas=[_clean_meta(metadata or {})],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to index complaint %s: %s", complaint_id, exc)


def index_complaints_batch(
    records: Sequence[dict[str, Any]],
    id_field: str = "id",
    text_field: str = "description",
) -> int:
    """Batch-index complaints. Returns count of successfully indexed records."""
    if not records:
        return 0
    try:
        embedder = get_embedder()
        texts = [str(r.get(text_field, "")) for r in records]
        vecs = embedder.encode_batch(texts, show_progress=False)
        col = _complaints_col()
        ids = [str(r[id_field]) for r in records]
        metas = [_clean_meta({
            "domain": r.get("domain", ""),
            "status": r.get("status", ""),
            "intent": (r.get("analysis") or {}).get("intent", "") if isinstance(r.get("analysis"), dict) else "",
            "severity": (r.get("analysis") or {}).get("severity", "") if isinstance(r.get("analysis"), dict) else "",
        }) for r in records]
        col.upsert(
            ids=ids,
            embeddings=[v.tolist() for v in vecs],
            documents=[t[:512] for t in texts],
            metadatas=metas,
        )
        return len(ids)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Batch complaint indexing failed: %s", exc)
        return 0


def search_similar_complaints(
    query: str,
    k: int | None = None,
    domain: str | None = None,
    exclude_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return top-k semantically similar complaints.

    Returns list of dicts: {id, document, distance, metadata}
    """
    k = k or cfg.vector_db.top_k_complaints
    try:
        embedder = get_embedder()
        vec = embedder.encode_one(query)
        col = _complaints_col()

        where: dict[str, Any] | None = None
        if domain:
            where = {"domain": {"$eq": domain}}

        results = col.query(
            query_embeddings=[vec.tolist()],
            n_results=min(k + (1 if exclude_id else 0), max(col.count(), 1)),
            where=where,
            include=["documents", "distances", "metadatas"],
        )
        items = []
        ids_ = results.get("ids", [[]])[0]
        docs_ = results.get("documents", [[]])[0]
        dists_ = results.get("distances", [[]])[0]
        metas_ = results.get("metadatas", [[]])[0]
        for cid, doc, dist, meta in zip(ids_, docs_, dists_, metas_):
            if exclude_id and cid == exclude_id:
                continue
            # ChromaDB cosine distance: similarity = 1 - distance
            similarity = max(0.0, 1.0 - float(dist))
            items.append({
                "id": cid,
                "document": doc,
                "similarity": round(similarity, 4),
                "metadata": meta or {},
            })
        return items[:k]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vector search failed (complaints): %s", exc)
        return []


# ---------------------------------------------------------------------------
# Knowledge base indexing
# ---------------------------------------------------------------------------

def index_kb_document(
    doc_id: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Embed and upsert a KB document."""
    try:
        embedder = get_embedder()
        vec = embedder.encode_one(content)
        col = _knowledge_col()
        col.upsert(
            ids=[doc_id],
            embeddings=[vec.tolist()],
            documents=[content[:512]],
            metadatas=[_clean_meta(metadata or {})],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to index KB doc %s: %s", doc_id, exc)


def index_kb_batch(
    records: Sequence[dict[str, Any]],
    id_field: str = "id",
    text_field: str = "content",
) -> int:
    """Batch-index KB documents. Returns count indexed."""
    if not records:
        return 0
    try:
        embedder = get_embedder()
        texts = [str(r.get(text_field, "")) for r in records]
        vecs = embedder.encode_batch(texts, show_progress=False)
        col = _knowledge_col()
        ids = [str(r[id_field]) for r in records]
        metas = [_clean_meta({
            "title": r.get("title", ""),
            "doc_type": r.get("doc_type", ""),
            "domain": r.get("domain", "general"),
        }) for r in records]
        col.upsert(
            ids=ids,
            embeddings=[v.tolist() for v in vecs],
            documents=[t[:512] for t in texts],
            metadatas=metas,
        )
        return len(ids)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Batch KB indexing failed: %s", exc)
        return 0


def search_knowledge(
    query: str,
    k: int | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Semantic search over KB documents.

    Returns list of dicts: {id, document, similarity, metadata}
    """
    k = k or cfg.vector_db.top_k_knowledge
    try:
        embedder = get_embedder()
        vec = embedder.encode_one(query)
        col = _knowledge_col()
        count = col.count()
        if count == 0:
            return []

        where: dict[str, Any] | None = None
        if domain and domain != "general":
            # include domain-specific AND general docs
            where = {"domain": {"$in": [domain, "general"]}}

        results = col.query(
            query_embeddings=[vec.tolist()],
            n_results=min(k, count),
            where=where,
            include=["documents", "distances", "metadatas"],
        )
        items = []
        ids_ = results.get("ids", [[]])[0]
        docs_ = results.get("documents", [[]])[0]
        dists_ = results.get("distances", [[]])[0]
        metas_ = results.get("metadatas", [[]])[0]
        for did, doc, dist, meta in zip(ids_, docs_, dists_, metas_):
            similarity = max(0.0, 1.0 - float(dist))
            items.append({
                "id": did,
                "document": doc,
                "similarity": round(similarity, 4),
                "metadata": meta or {},
            })
        return items
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vector search failed (knowledge): %s", exc)
        return []


def delete_complaint(complaint_id: str) -> None:
    try:
        _complaints_col().delete(ids=[complaint_id])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to delete complaint from vector store: %s", exc)


def delete_kb_document(doc_id: str) -> None:
    try:
        _knowledge_col().delete(ids=[doc_id])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to delete KB doc from vector store: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_meta(meta: dict[str, Any]) -> dict[str, str]:
    """ChromaDB metadata values must be str/int/float/bool — stringify all."""
    cleaned: dict[str, str] = {}
    for k, v in meta.items():
        if v is None:
            cleaned[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            cleaned[k] = str(v)
        else:
            cleaned[k] = str(v)
    return cleaned


def collection_stats() -> dict[str, Any]:
    """Return counts for each collection (useful for health/debug endpoints)."""
    try:
        return {
            "complaints": _complaints_col().count(),
            "knowledge_base": _knowledge_col().count(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
