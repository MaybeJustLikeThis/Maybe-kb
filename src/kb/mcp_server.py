"""MCP server exposing knowledge base tools for Claude Code integration."""
from __future__ import annotations

from pathlib import Path

from kb.core.config import KBConfig
from kb.core.context import AppContext
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
    ctx = AppContext.from_config(config)
    vault = ctx.vault
    db = ctx.db
    provider = ctx.embedding
    llm = ctx.llm
    store = ctx.vector_store

    @mcp.tool()
    def kb_search(query: str, limit: int = 20) -> list[dict]:
        """Full-text search using FTS5 + jieba Chinese tokenization."""
        rows = db.search_fulltext(query, limit=limit)
        return [note_row_to_dict(db, dict(row)) for row in rows]

    @mcp.tool()
    def kb_semantic_search(query: str, limit: int = 20) -> list[dict]:
        """Semantic search using BGE-small-zh embedding + LanceDB cosine similarity."""
        embed_result = provider.embed(query)
        records = store.search(embed_result.vector, limit=limit)
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
        results = hybrid_search(query, db, provider, store, limit)
        return [
            {"file_id": r.file_id, "title": r.title,
             "score": r.score, "source": r.source}
            for r in results
        ]

    @mcp.tool()
    def kb_read(file_id: str) -> dict | None:
        """Read a note's full content. Returns None if not found or blocked."""
        try:
            _, note = services.resolve_note(vault, file_id)
        except (ValueError, FileNotFoundError):
            return None
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
    def kb_add(title: str, content: str, category: str = "",
               tags: str = "", description: str = "") -> dict:
        """Create a new note. tags is comma-separated."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        cat = category if category else None
        try:
            note = services.create_note(
                vault, db, title, content,
                category=cat, tags=tag_list, description=description or None,
            )
        except ValueError:
            return {"error": "Path traversal blocked"}
        return {
            "file_id": note.file_id,
            "title": note.title,
            "content": note.content,
        }

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

        Examples: technical analysis, troubleshooting logs, design decisions,
        code patterns, document summaries, research notes.
        """
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        try:
            note = services.create_note(
                vault, db, title, content,
                category=category or None,
                description=description or None,
                source_project=source_project or None,
                source_context=source_context or None,
                tags=tag_list,
            )
        except ValueError:
            return {"error": "Path traversal blocked"}
        return {
            "file_id": note.file_id,
            "title": note.title,
            "source_project": note.source_project,
            "tags": note.tags,
        }

    @mcp.tool()
    def kb_rag_query(query: str, top_k: int = 5) -> dict:
        """RAG query: hybrid search + LLM answer over your knowledge base."""
        response = rag_query(query, db, provider, store, llm, top_k=top_k)
        return {
            "answer": response.text,
            "model": response.model,
            "tokens_used": response.tokens_used,
        }

    return mcp
