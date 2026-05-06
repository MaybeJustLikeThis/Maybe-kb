"""API routes for kb Web UI."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kb.core.config import EmbeddingConfig, LLMConfig
from kb.core.models import Note
from kb.core.rag import rag_query, rag_query_stream
from kb.core.search import hybrid_search
from kb.core import services
from kb.data.attachments import store_attachment
from kb.data.database import Database
from kb.data.embedding import create_embedding_provider
from kb.data.llm import create_llm_provider
from kb.data.vector import VectorStore


class NoteResponse(BaseModel):
    file_id: str
    title: str
    description: str | None = None
    content: str = ""
    category: str | None = None
    tags: list[str] = []
    attachments: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    status: str = "published"


class NoteCreate(BaseModel):
    title: str = Field(..., max_length=300)
    content: str = Field(default="", max_length=500_000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=50)
    description: str | None = Field(default=None, max_length=500)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, max_length=500_000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=20)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


def _note_to_response(note: Note) -> NoteResponse:
    """Convert internal Note to API response model."""
    return NoteResponse(
        file_id=note.file_id,
        title=note.title,
        description=note.description,
        content=note.content,
        category=note.category,
        tags=note.tags,
        attachments=note.attachments,
        created_at=note.created_at,
        updated_at=note.updated_at,
        status=note.status,
    )


def _build_note_dict(row, db: Database) -> dict:
    """Build a note dict from a DB row, including tags."""
    tags = db.get_tags(row["id"])
    return {
        "file_id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "category": row["category"],
        "tags": tags,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
    }


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def create_api_router(
    vault_path: Path,
    db_path: Path,
    embedding_config: EmbeddingConfig | None = None,
    llm_config: LLMConfig | None = None,
) -> APIRouter:
    """Create an APIRouter with all API endpoints."""
    router = APIRouter()

    _initialized = False

    def get_db() -> Database:
        nonlocal _initialized
        db = Database(db_path)
        if not _initialized:
            db.initialize()
            _initialized = True
        return db

    @router.get("/notes")
    def list_notes(
        category: str | None = Query(None),
        tag: str | None = Query(None),
        limit: int = Query(50),
    ):
        db = get_db()
        rows = db.list_notes(category=category, tag=tag, limit=limit)
        return [_build_note_dict(row, db) for row in rows]

    @router.post("/notes")
    def create_note(body: NoteCreate):
        try:
            parsed = services.create_note(
                vault_path, get_db(),
                body.title, body.content,
                body.category, body.tags, body.description,
            )
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        return _note_to_response(parsed)

    @router.get("/notes/{file_id:path}")
    def get_note(file_id: str):
        try:
            _, note = services.resolve_note(vault_path, file_id)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Note not found")
        return _note_to_response(note)

    @router.put("/notes/{file_id:path}")
    def update_note(file_id: str, body: NoteUpdate):
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        try:
            note = services.update_note(vault_path, get_db(), file_id, **fields)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Note not found")
        return _note_to_response(note)

    @router.delete("/notes/{file_id:path}")
    def delete_note(file_id: str):
        try:
            services.delete_note(vault_path, get_db(), file_id)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"ok": True}

    @router.get("/search")
    def search_notes(
        q: str = Query(..., min_length=1),
        limit: int = Query(20),
        mode: str = Query("fts5"),
    ):
        if mode == "hybrid" and embedding_config is not None:
            provider = create_embedding_provider(embedding_config)
            store = VectorStore(vault_path / ".kb" / "vectors.lance")
            try:
                results = hybrid_search(q, get_db(), provider, store, limit)
            finally:
                store.close()
            return [
                {"file_id": r.file_id, "title": r.title,
                 "score": r.score, "source": r.source}
                for r in results
            ]
        db = get_db()
        rows = db.search_fulltext(q, limit=limit)
        return [_build_note_dict(row, db) for row in rows]

    @router.get("/semantic-search")
    def semantic_search(q: str = Query(..., min_length=1), limit: int = Query(20)):
        if embedding_config is None:
            return []
        provider = create_embedding_provider(embedding_config)
        store = VectorStore(vault_path / ".kb" / "vectors.lance")
        try:
            embed_result = provider.embed(q)
            records = store.search(embed_result.vector, limit=limit)
        finally:
            store.close()

        db = get_db()
        results = []
        for r in records:
            row = db.get_note(r.id)
            if row is not None:
                item = _build_note_dict(row, db)
                item["score"] = _cosine_similarity(r.vector, embed_result.vector)
                item["chunk_text"] = r.text
                results.append(item)
        return results

    @router.get("/tags")
    def get_tags():
        return {"tags": get_db().list_all_tags()}

    @router.get("/categories")
    def get_categories():
        return {"categories": get_db().list_all_categories()}

    @router.post("/attachments")
    async def upload_attachment(file: UploadFile = File(...)):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        rel_path = store_attachment(tmp_path, vault_path)
        tmp_path.unlink()
        return {"path": rel_path}

    @router.get("/index")
    def get_index_status():
        db = get_db()
        return {"notes_count": len(db.get_all_hashes())}

    @router.post("/index")
    def trigger_index():
        from kb.cli import _index_files
        db = get_db()
        provider = create_embedding_provider(embedding_config) if embedding_config else None
        count, vec_count = _index_files(vault_path, db, full=True, embedding_provider=provider)
        return {"indexed": count, "vectors": vec_count}

    @router.post("/chat/ask")
    def chat_ask(body: ChatRequest):
        if llm_config is None or embedding_config is None:
            raise HTTPException(status_code=400, detail="LLM and embedding config required")

        db = get_db()
        provider = create_embedding_provider(embedding_config)
        llm = create_llm_provider(llm_config)
        store = VectorStore(vault_path / ".kb" / "vectors.lance")
        try:
            response = rag_query(body.query, db, provider, store, llm, top_k=body.top_k)
        finally:
            store.close()
        return {"answer": response.text, "model": response.model, "tokens_used": response.tokens_used}

    @router.post("/chat")
    async def chat_stream(body: ChatRequest):
        if llm_config is None or embedding_config is None:
            raise HTTPException(status_code=400, detail="LLM and embedding config required")

        db = get_db()
        provider = create_embedding_provider(embedding_config)
        llm = create_llm_provider(llm_config)
        store = VectorStore(vault_path / ".kb" / "vectors.lance")

        async def generate():
            try:
                for chunk in rag_query_stream(body.query, db, provider, store, llm, top_k=body.top_k):
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            finally:
                store.close()

        return StreamingResponse(generate(), media_type="text/event-stream")

    return router
