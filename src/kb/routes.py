"""API routes for kb Web UI."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kb.core.context import AppContext
from kb.core.rag import rag_query, rag_query_stream
from kb.core.search import cosine_similarity, hybrid_search
from kb.core import services
from kb.data.attachments import store_attachment


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


from kb.core.serializers import note_row_to_dict, note_to_response


def create_api_router(ctx: AppContext) -> APIRouter:
    """Create an APIRouter with all API endpoints.

    Accepts an AppContext that owns all service resources (db, embedding,
    llm, vector_store). Resources are shared across all requests and
    cleaned up by the caller on shutdown.
    """
    router = APIRouter()
    vault_path = ctx.vault

    @router.get("/notes")
    def list_notes(
        category: str | None = Query(None),
        tag: str | None = Query(None),
        limit: int = Query(50),
        sort: str | None = Query(None),
    ):
        rows = ctx.db.list_notes(
            category=category, tag=tag, limit=limit, sort=sort,
        )
        return [note_row_to_dict(ctx.db, row) for row in rows]

    @router.post("/notes")
    def create_note(body: NoteCreate):
        try:
            parsed = services.create_note(
                vault_path, ctx.db,
                body.title, body.content,
                body.category, body.tags, body.description,
            )
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        return note_to_response(parsed)

    @router.get("/notes/{file_id:path}/related")
    def get_related_notes(file_id: str, limit: int = Query(5, ge=1, le=20)):
        if ctx.embedding is None:
            return []
        try:
            _, note = services.resolve_note(vault_path, file_id)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Note not found")

        embed_result = ctx.embedding.embed(note.content)
        records = ctx.vector_store.search(embed_result.vector, limit=limit * 3 + 1)

        results = []
        seen_ids: set[str] = {file_id}
        for r in records:
            if r.id in seen_ids:
                continue
            seen_ids.add(r.id)
            row = ctx.db.get_note(r.id)
            if row is not None:
                item = note_row_to_dict(ctx.db, row)
                item["score"] = round(cosine_similarity(r.vector, embed_result.vector), 4)
                results.append(item)
            if len(results) >= limit:
                break
        return results

    @router.get("/notes/{file_id:path}")
    def get_note(file_id: str):
        try:
            _, note = services.resolve_note(vault_path, file_id)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Note not found")
        return note_to_response(note)

    @router.put("/notes/{file_id:path}")
    def update_note(file_id: str, body: NoteUpdate):
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        try:
            note = services.update_note(vault_path, ctx.db, file_id, **fields)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal blocked")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Note not found")
        return note_to_response(note)

    @router.delete("/notes/{file_id:path}")
    def delete_note(file_id: str):
        try:
            services.delete_note(vault_path, ctx.db, file_id)
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
        if mode == "hybrid" and ctx.embedding is not None:
            results = hybrid_search(q, ctx.db, ctx.embedding, ctx.vector_store, limit)
            return [
                {"file_id": r.file_id, "title": r.title,
                 "score": r.score, "source": r.source}
                for r in results
            ]
        rows = ctx.db.search_fulltext(q, limit=limit)
        return [note_row_to_dict(ctx.db, row) for row in rows]

    @router.get("/semantic-search")
    def semantic_search(q: str = Query(..., min_length=1), limit: int = Query(20)):
        if ctx.embedding is None:
            return []
        embed_result = ctx.embedding.embed(q)
        records = ctx.vector_store.search(embed_result.vector, limit=limit)

        results = []
        for r in records:
            row = ctx.db.get_note(r.id)
            if row is not None:
                item = note_row_to_dict(ctx.db, row)
                item["score"] = cosine_similarity(r.vector, embed_result.vector)
                item["chunk_text"] = r.text
                results.append(item)
        return results

    @router.get("/tags")
    def get_tags():
        return {"tags": ctx.db.list_all_tags()}

    @router.get("/categories")
    def get_categories(with_count: bool = Query(False)):
        cats = ctx.db.list_all_categories()
        if not with_count:
            return {"categories": cats}
        return {
            "categories": [
                {"name": c, "count": ctx.db.count_notes_by_category(c)}
                for c in cats
            ]
        }

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
        return {"notes_count": len(ctx.db.get_all_hashes())}

    @router.get("/attachments/stats")
    def get_attachments_stats():
        att_dir = vault_path / "attachments"
        if not att_dir.is_dir():
            return {"count": 0}
        count = sum(1 for f in att_dir.iterdir() if f.is_file())
        return {"count": count}

    @router.post("/index")
    def trigger_index():
        from kb.core.indexer import index_files
        count, vec_count = index_files(vault_path, ctx.db, full=True, embedding_provider=ctx.embedding)
        return {"indexed": count, "vectors": vec_count}

    @router.post("/chat/ask")
    def chat_ask(body: ChatRequest):
        if ctx.llm is None or ctx.embedding is None:
            raise HTTPException(status_code=400, detail="LLM and embedding config required")

        response = rag_query(body.query, ctx.db, ctx.embedding, ctx.vector_store, ctx.llm, top_k=body.top_k)
        return {"answer": response.text, "model": response.model, "tokens_used": response.tokens_used}

    @router.post("/chat")
    async def chat_stream(body: ChatRequest):
        if ctx.llm is None or ctx.embedding is None:
            raise HTTPException(status_code=400, detail="LLM and embedding config required")

        async def generate():
            for chunk in rag_query_stream(body.query, ctx.db, ctx.embedding, ctx.vector_store, ctx.llm, top_k=body.top_k):
                yield f"data: {json.dumps({'text': chunk.text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return router
