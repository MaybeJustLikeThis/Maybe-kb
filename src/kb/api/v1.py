"""Normalized /api/v1 routes."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from kb.api import responses
from kb.api.schemas import (
    ApiResponse,
    ChatRequest,
    NoteCreateRequest,
    NoteUpdateRequest,
    OpenTarget,
    SystemHealth,
)
from kb.core import queries, services
from kb.core.context import AppContext
from kb.core.health import get_system_health
from kb.core.indexer import index_files, index_note_vectors
from kb.core.open_targets import build_obsidian_open_target
from kb.core.rag import rag_query, rag_query_stream, rag_source_to_dict
from kb.core.serializers import note_to_detail
from kb.data.attachments import store_attachment


def _not_found_or_path_error(exc: Exception):
    if isinstance(exc, FileNotFoundError):
        return responses.note_not_found()
    if isinstance(exc, ValueError):
        return responses.path_traversal_blocked()
    raise exc


def create_v1_router(ctx: AppContext) -> APIRouter:
    """Create the normalized v1 API router."""
    router = APIRouter()

    def _index_note_if_possible(file_id: str) -> int:
        if ctx.embedding is None:
            return 0
        return index_note_vectors(
            ctx.vault,
            ctx.db,
            ctx.embedding,
            file_id,
            vector_store=ctx.vector_store,
            index_dir=ctx.index_dir,
        )

    @router.get("/notes")
    def list_notes(
        category: str | None = Query(None),
        tag: str | None = Query(None),
        source_project: str | None = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        result = queries.list_notes(
            ctx,
            category=category,
            tag=tag,
            source_project=source_project,
            limit=limit,
            offset=offset,
        )
        return responses.page(
            result.items,
            limit=result.limit,
            offset=result.offset,
            total=result.total,
        )

    @router.post("/notes")
    def create_note(body: NoteCreateRequest):
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        try:
            note = ingest(
                IngestRequest(
                    title=body.title,
                    content=body.content,
                    source_project=body.source_project or "manual",
                    tags=body.tags,
                    category=body.category,
                    description=body.description,
                    source_path=body.source_path,
                    source_context=body.source_context,
                    content_type=body.content_type,
                ),
                ctx.vault, ctx.db,
                notes_dir=ctx.notes_dir,
            )
            _index_note_if_possible(note.file_id)
        except ValueError:
            return responses.path_traversal_blocked()
        return responses.ok(note_to_detail(note))

    @router.get("/notes/{file_id:path}/related")
    def get_related_notes(file_id: str, limit: int = Query(5, ge=1, le=20)):
        try:
            return responses.ok(queries.get_related_notes(ctx, file_id, limit))
        except (FileNotFoundError, ValueError) as exc:
            return _not_found_or_path_error(exc)

    @router.get(
        "/notes/{file_id:path}/open-target",
        response_model=ApiResponse[OpenTarget],
    )
    def get_note_open_target(file_id: str):
        if ctx.config is None or not ctx.config.obsidian.enabled:
            return responses.provider_not_configured(
                "Obsidian integration is disabled",
            )
        try:
            return responses.ok(build_obsidian_open_target(ctx.config, file_id))
        except (FileNotFoundError, ValueError) as exc:
            return _not_found_or_path_error(exc)

    @router.get("/notes/{file_id:path}")
    def get_note(file_id: str):
        try:
            return responses.ok(queries.get_note_detail(ctx, file_id))
        except (FileNotFoundError, ValueError) as exc:
            return _not_found_or_path_error(exc)

    @router.put("/notes/{file_id:path}")
    def update_note(file_id: str, body: NoteUpdateRequest):
        fields = {
            key: value
            for key, value in body.model_dump().items()
            if value is not None
        }
        try:
            note = services.update_note(ctx.vault, ctx.db, file_id, **fields)
            _index_note_if_possible(note.file_id)
        except (FileNotFoundError, ValueError) as exc:
            return _not_found_or_path_error(exc)
        return responses.ok(note_to_detail(note))

    @router.delete("/notes/{file_id:path}")
    def delete_note(file_id: str):
        try:
            services.delete_note(ctx.vault, ctx.db, file_id)
        except (FileNotFoundError, ValueError) as exc:
            return _not_found_or_path_error(exc)
        return responses.ok({"ok": True})

    @router.get("/search")
    def search_notes(
        q: str = Query(..., min_length=1),
        mode: str = Query("fulltext", pattern="^(fulltext|semantic|hybrid)$"),
        limit: int = Query(20, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        result = queries.search_notes(
            ctx,
            query=q,
            mode=mode,
            limit=limit,
            offset=offset,
        )
        return responses.page(
            result.items,
            limit=result.limit,
            offset=result.offset,
            total=result.total,
        )

    @router.get("/taxonomy")
    def get_taxonomy():
        return responses.ok(queries.get_taxonomy(ctx))

    @router.get("/dashboard")
    def get_dashboard():
        return responses.ok(queries.get_dashboard_stats(ctx))

    @router.get("/health", response_model=ApiResponse[SystemHealth])
    def get_health():
        return responses.ok(get_system_health(ctx))

    @router.get("/sources")
    def get_sources():
        sources = []
        if ctx.config and ctx.config.sources:
            for name, s in ctx.config.sources.items():
                sources.append({
                    "name": name,
                    "label": s.label,
                    "description": s.description,
                    "icon": s.icon,
                })
        return responses.ok({"sources": sources})

    @router.get("/dashboard/activity")
    def get_dashboard_activity(limit: int = Query(8, ge=1, le=20)):
        return responses.ok(queries.get_dashboard_activity(ctx, limit))

    @router.post("/index/rebuild")
    def rebuild_index():
        try:
            indexed, vectors = index_files(
                ctx.vault,
                ctx.db,
                full=True,
                embedding_provider=ctx.ensure_embedding(),
                notes_dir=ctx.notes_dir,
                attachments_dir=ctx.attachments_dir,
                index_dir=ctx.index_dir,
            )
        except Exception:
            return responses.operation_failed(
                "INDEX_REBUILD_FAILED",
                "Index rebuild failed",
            )
        return responses.ok({"indexed": indexed, "vectors": vectors})

    @router.post("/attachments")
    async def upload_attachment(file: UploadFile = File(...)):
        import tempfile

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=Path(file.filename or "").suffix,
            ) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)
            rel_path = store_attachment(
                tmp_path,
                ctx.vault,
                attachments_dir=ctx.attachments_dir,
            )
        except Exception:
            return responses.operation_failed(
                "ATTACHMENT_UPLOAD_FAILED",
                "Attachment upload failed",
            )
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        return responses.ok({"path": rel_path})

    @router.post("/import")
    async def import_file_endpoint(
        file: UploadFile = File(...),
        title: str = Form(""),
        category: str = Form(""),
        tags: str = Form(""),
    ):
        """Import a file (PDF, DOCX, CSV, etc.) into the knowledge base."""
        import tempfile
        from kb.core.import_file import import_file, ImportFileError

        tmp_path: Path | None = None
        try:
            suffix = Path(file.filename or ".bin").suffix
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix,
            ) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
            override_title = title.strip() or None
            override_category = category.strip() or None
            src_cfg = ctx.config.sources.get("imported") if ctx.config else None

            # Use original filename as default title
            if override_title is None and file.filename:
                override_title = Path(file.filename).stem

            note = import_file(
                tmp_path,
                vault=ctx.vault,
                db=ctx.db,
                notes_dir=ctx.notes_dir,
                attachments_dir=ctx.attachments_dir,
                title=override_title,
                category=override_category,
                tags=tag_list,
                source_config=src_cfg,
            )
            _index_note_if_possible(note.file_id)
        except ImportFileError as exc:
            return responses.operation_failed(
                "IMPORT_FAILED",
                str(exc),
            )
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        return responses.ok({
            "file_id": note.file_id,
            "title": note.title,
            "category": note.category,
            "content_type": note.content_type,
            "source_project": note.source_project,
        })

    @router.post("/chat/ask")
    def chat_ask(body: ChatRequest):
        embedding = ctx.ensure_embedding()
        llm = ctx.ensure_llm()
        if llm is None or embedding is None:
            return responses.provider_not_configured(
                "LLM and embedding config required",
            )
        response = rag_query(
            body.query,
            ctx.db,
            embedding,
            ctx.vector_store,
            llm,
            top_k=body.top_k,
        )
        return responses.ok({
            "answer": response.text,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "sources": [
                rag_source_to_dict(source)
                for source in response.sources
            ],
        })

    @router.post("/chat/stream")
    async def chat_stream(body: ChatRequest):
        embedding = ctx.ensure_embedding()
        llm = ctx.ensure_llm()
        if llm is None or embedding is None:
            return responses.provider_not_configured(
                "LLM and embedding config required",
            )

        async def generate():
            for chunk in rag_query_stream(
                body.query,
                ctx.db,
                embedding,
                ctx.vector_store,
                llm,
                top_k=body.top_k,
            ):
                yield (
                    "data: "
                    + json.dumps({
                        "data": {"text": chunk.text, "done": False},
                        "meta": {},
                        "error": None,
                    })
                    + "\n\n"
                )
            yield (
                "data: "
                + json.dumps({
                    "data": {"text": None, "done": True},
                    "meta": {},
                    "error": None,
                })
                + "\n\n"
            )

        return StreamingResponse(generate(), media_type="text/event-stream")

    return router
