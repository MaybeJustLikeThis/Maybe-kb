"""MCP server exposing knowledge base tools for Claude Code integration."""
from __future__ import annotations

from pathlib import Path

from kb.core.config import KBConfig
from kb.core.rag import rag_query
from kb.core.search import hybrid_search
from kb.core import services
from kb.data.database import Database
from kb.data.embedding import create_embedding_provider
from kb.data.llm import create_llm_provider
from kb.data.vector import VectorStore


def create_mcp_server(config: KBConfig):
    """Create MCP server with knowledge base tools.

    Follows the same factory pattern as create_api_router() in routes.py.
    All tools call the shared services module for CRUD operations.
    Database is lazy-initialized on first tool call.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("kb")
    vault = config.vault_path
    db_path = vault / ".kb" / "kb.db"
    provider = create_embedding_provider(config.embedding)

    _initialized = False

    def get_db() -> Database:
        nonlocal _initialized
        db = Database(db_path)
        if not _initialized:
            db.initialize()
            _initialized = True
        return db

    @mcp.tool()
    def kb_search(query: str, limit: int = 20) -> list[dict]:
        """Full-text search using FTS5 + jieba Chinese tokenization."""
        db = get_db()
        rows = db.search_fulltext(query, limit=limit)
        return [_tool_note_dict(dict(row), db) for row in rows]

    @mcp.tool()
    def kb_semantic_search(query: str, limit: int = 20) -> list[dict]:
        """Semantic search using BGE-small-zh embedding + LanceDB cosine similarity."""
        db = get_db()
        embed_result = provider.embed(query)
        store = VectorStore(vault / ".kb" / "vectors.lance")
        try:
            records = store.search(embed_result.vector, limit=limit)
        finally:
            store.close()
        results = []
        for r in records:
            row = db.get_note(r.id)
            if row is not None:
                item = _tool_note_dict(dict(row), db)
                item["chunk_text"] = r.text
                results.append(item)
        return results

    @mcp.tool()
    def kb_hybrid_search(query: str, limit: int = 20) -> list[dict]:
        """Hybrid search (FTS5 + semantic) with RRF fusion."""
        db = get_db()
        store = VectorStore(vault / ".kb" / "vectors.lance")
        try:
            results = hybrid_search(query, db, provider, store, limit)
        finally:
            store.close()
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
        }

    @mcp.tool()
    def kb_list(category: str = "", tag: str = "", limit: int = 50) -> list[dict]:
        """List notes with optional category/tag filter."""
        db = get_db()
        rows = db.list_notes(
            category=category or None,
            tag=tag or None,
            limit=limit,
        )
        return [_tool_note_dict(dict(row), db) for row in rows]

    @mcp.tool()
    def kb_add(title: str, content: str, category: str = "",
               tags: str = "", description: str = "") -> dict:
        """Create a new note. tags is comma-separated."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        cat = category if category else None
        db = get_db()
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
    def kb_rag_query(query: str, top_k: int = 5) -> dict:
        """RAG query: hybrid search + LLM answer over your knowledge base."""
        llm = create_llm_provider(config.llm)
        db = get_db()
        store = VectorStore(vault / ".kb" / "vectors.lance")
        try:
            response = rag_query(query, db, provider, store, llm, top_k=top_k)
        finally:
            store.close()
        return {
            "answer": response.text,
            "model": response.model,
            "tokens_used": response.tokens_used,
        }

    return mcp


def _tool_note_dict(row: dict, db: Database) -> dict:
    """Build note dict from DB row with tags."""
    tags = db.get_tags(row.get("id", ""))
    return {
        "file_id": row.get("id", ""),
        "title": row.get("title", ""),
        "description": row.get("description"),
        "category": row.get("category"),
        "tags": tags,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "status": row.get("status", "published"),
    }
