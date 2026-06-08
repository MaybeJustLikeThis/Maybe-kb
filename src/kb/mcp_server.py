"""MCP server exposing knowledge base tools for Claude Code integration."""
from __future__ import annotations

from pathlib import Path

from kb.core.config import KBConfig
from kb.core.context import AppContext
from kb.core.indexer import index_note_if_possible
from kb.core.rag import rag_query
from kb.core.search import hybrid_search
from kb.core.serializers import note_row_to_dict
from kb.core import services


def create_mcp_server(config: KBConfig):
    """Create MCP server with knowledge base tools.

    All tools call the shared services module for CRUD operations.
    Resources are initialized once via AppContext and shared across tools.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("kb")
    ctx = AppContext.from_config(
        config,
        with_embedding=False,
        with_llm=False,
        allow_lazy_embedding=True,
        allow_lazy_llm=True,
    )
    mcp._kb_context = ctx
    vault = ctx.vault
    db = ctx.db

    def _blank_to_none(value: str) -> str | None:
        stripped = value.strip()
        return stripped or None

    def _create_note(
        *,
        title: str,
        content: str,
        source_project: str,
        tags: str,
        description: str,
        source_context: str,
        category: str,
        include_content: bool = True,
    ) -> dict:
        """Shared logic for kb_add and kb_save."""
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        cat = _blank_to_none(category)
        desc = _blank_to_none(description)
        sctx = _blank_to_none(source_context)
        src_cfg = config.sources.get(source_project)
        try:
            note = ingest(
                IngestRequest(
                    title=title,
                    content=content,
                    source_project=source_project,
                    tags=tag_list,
                    category=cat,
                    description=desc,
                    source_context=sctx,
                ),
                vault, db,
                source_config=src_cfg,
                notes_dir=ctx.notes_dir,
            )
        except ValueError as e:
            return {"error": str(e)}
        indexed_vectors, index_error = index_note_if_possible(ctx, note.file_id)
        result: dict = {
            "file_id": note.file_id,
            "title": note.title,
            "source_project": note.source_project,
            "tags": note.tags,
            "indexed_vectors": indexed_vectors,
            "index_error": index_error,
        }
        if include_content:
            result["content"] = note.content
        return result

    @mcp.tool()
    def kb_search(query: str, limit: int = 20) -> list[dict]:
        """Full-text search using FTS5 + jieba Chinese tokenization."""
        rows = db.search_fulltext(query, limit=limit)
        return [note_row_to_dict(db, dict(row)) for row in rows]

    @mcp.tool()
    def kb_semantic_search(query: str, limit: int = 20) -> list[dict]:
        """Semantic search using BGE-small-zh embedding + LanceDB cosine similarity."""
        provider = ctx.ensure_embedding()
        if provider is None:
            return [{"error": "embedding provider is not configured"}]
        embed_result = provider.embed(query)
        records = ctx.vector_store.search(embed_result.vector, limit=limit)
        results = []
        for r in records:
            row = db.get_note(r.id)
            if row is not None:
                item = note_row_to_dict(db, dict(row))
                item["chunk_text"] = r.text
                results.append(item)
        return results

    @mcp.tool()
    def kb_hybrid_search(query: str, limit: int = 20) -> list[dict]:
        """Hybrid search (FTS5 + semantic) with RRF fusion."""
        provider = ctx.ensure_embedding()
        if provider is None:
            return [{"error": "embedding provider is not configured"}]
        results = hybrid_search(query, db, provider, ctx.vector_store, limit)
        return [
            {"file_id": r.file_id, "title": r.title,
             "score": r.score, "source": r.source}
            for r in results
        ]

    @mcp.tool()
    def kb_read(file_id: str) -> dict:
        """Read a note's full content. Returns error dict if not found or blocked."""
        try:
            _, note = services.resolve_note(vault, file_id)
        except FileNotFoundError:
            return {"error": "not_found", "file_id": file_id}
        except ValueError:
            return {"error": "path_traversal_blocked", "file_id": file_id}
        return {
            "file_id": note.file_id,
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "category": note.category,
            "description": note.description,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "status": note.status,
            "source_project": note.source_project,
            "source_path": note.source_path,
            "source_context": note.source_context,
            "content_type": note.content_type,
        }

    @mcp.tool()
    def kb_list(category: str = "", tag: str = "", limit: int = 50) -> list[dict]:
        """List notes with optional category/tag filter."""
        rows = db.list_notes(
            category=category or None,
            tag=tag or None,
            limit=limit,
        )
        return [note_row_to_dict(db, dict(row)) for row in rows]

    @mcp.tool()
    def kb_add(
        title: str,
        content: str,
        category: str = "",
        tags: str = "",
        description: str = "",
        source_project: str = "manual",
        source_context: str = "",
    ) -> dict:
        """Create a new note. tags is comma-separated."""
        return _create_note(
            title=title, content=content, source_project=source_project,
            tags=tags, description=description, source_context=source_context,
            category=category, include_content=True,
        )

    @mcp.tool()
    def kb_save(
        title: str,
        content: str,
        source_project: str,
        tags: str = "",
        description: str = "",
        source_context: str = "",
        category: str = "",
    ) -> dict:
        """Save a knowledge note to the vault. tags is comma-separated.

        Choose source_project from the configured sources (blog, agent, manual).

        Write well-structured Markdown content. A good note has a clear title,
        explains the core idea up front, provides context (why it matters),
        and ends with actionable takeaways or open questions.

        Use description to summarize longer notes (articles, postmortems,
        design docs) for better search recall. Skip it for short notes and
        code snippets where the title is already enough.

        Tag your note with a Type-* tag to classify it across all sources:
        Type-Troubleshooting, Type-DesignDecision, Type-CodeSnippet,
        Type-TechArticle, Type-Document. Combine with topic tags freely
        (e.g. tags: "Type-Troubleshooting, Python, memory-leak").
        """
        return _create_note(
            title=title, content=content, source_project=source_project,
            tags=tags, description=description, source_context=source_context,
            category=category, include_content=False,
        )

    @mcp.tool()
    def kb_rag_query(query: str, top_k: int = 5) -> dict:
        """RAG query: hybrid search + LLM answer over your knowledge base."""
        from kb.core.rag import rag_source_to_dict

        provider = ctx.ensure_embedding()
        llm = ctx.ensure_llm()
        if provider is None or llm is None:
            return {"error": "LLM and embedding config required"}
        response = rag_query(
            query,
            db,
            provider,
            ctx.vector_store,
            llm,
            top_k=top_k,
        )
        return {
            "answer": response.text,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "sources": [
                rag_source_to_dict(source)
                for source in response.sources
            ],
        }

    return mcp
