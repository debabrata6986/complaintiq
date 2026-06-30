"""Knowledge Base router — list / search / CRUD policies & docs.

Extended with:
- Vector DB indexing on create/delete (Feature 2)
- Hybrid retrieval for search (Feature 3)
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from auth_utils import get_current_user, require_roles
from db import get_db
from models import KBDocument, KBDocumentCreate, UserPublic
from hybrid_retrieval import hybrid_knowledge_search
from vector_db import index_kb_document, delete_kb_document

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KBDocument])
async def list_docs(
    domain: str | None = None,
    doc_type: str | None = None,
    user: UserPublic = Depends(get_current_user),
):
    db = get_db()
    q: dict = {}
    if domain:
        q["$or"] = [{"domain": domain}, {"domain": "general"}]
    if doc_type:
        q["doc_type"] = doc_type
    docs = await db.kb_documents.find(q, {"_id": 0}).limit(500).to_list(length=500)
    return [KBDocument(**d) for d in docs]


@router.get("/search")
async def search(
    q: str,
    domain: str | None = None,
    k: int = 5,
    user: UserPublic = Depends(get_current_user),
):
    db = get_db()
    query: dict = {}
    if domain:
        query["$or"] = [{"domain": domain}, {"domain": "general"}]
    docs = await db.kb_documents.find(query, {"_id": 0}).limit(500).to_list(length=500)
    # Hybrid retrieval (semantic + TF-IDF)
    matches = hybrid_knowledge_search(q, docs, "content", k=k, min_score=0.0)
    return {
        "query": q,
        "results": [
            {**d, "score": score, "retrieval_method": "hybrid"} for d, score in matches
        ],
    }


@router.post("", response_model=KBDocument)
async def create_doc(
    payload: KBDocumentCreate,
    background: BackgroundTasks,
    user: UserPublic = Depends(require_roles("admin", "manager")),
):
    db = get_db()
    doc = KBDocument(**payload.model_dump()).model_dump()
    await db.kb_documents.insert_one(doc)
    doc.pop("_id", None)
    # Background-index into vector DB (Feature 2 + 10)
    background.add_task(
        index_kb_document,
        doc["id"],
        doc["content"],
        {"title": doc["title"], "doc_type": doc["doc_type"], "domain": doc.get("domain", "general")},
    )
    return KBDocument(**doc)


@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: str,
    background: BackgroundTasks,
    user: UserPublic = Depends(require_roles("admin")),
):
    db = get_db()
    res = await db.kb_documents.delete_one({"id": doc_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    background.add_task(delete_kb_document, doc_id)
    return {"deleted": True}
