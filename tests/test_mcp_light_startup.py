"""Tests for MCP startup without semantic provider initialization."""
from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from kb.core.config import KBConfig, EmbeddingConfig, LLMConfig
from kb.data.models import Note
from kb.data.database import Database


def _prepare_vault(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()
    db = Database(tmp_path / ".kb" / "kb.db")
    db.initialize()
    db.upsert_note(Note(
        file_id="notes/a.md",
        title="Local Search Note",
        content="keyword-only content",
        tags=["keyword"],
    ))
    db.close()


def test_mcp_creation_does_not_initialize_embedding_or_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """MCP keyword tools start without cold-starting embedding or LLM."""
    _prepare_vault(tmp_path)
    embedding_called = False

    def fail_embedding(config):
        nonlocal embedding_called
        embedding_called = True
        raise RuntimeError("embedding factory should not run at startup")

    def fail_llm(config):
        raise RuntimeError("llm factory should not run at startup")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", fail_llm)

    from kb.mcp_server import create_mcp_server

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
        llm=LLMConfig(provider="ollama"),
    )
    mcp = create_mcp_server(config)
    assert not embedding_called

    async def _run():
        result = await mcp.call_tool("kb_search", {
            "query": "keyword",
            "limit": 5,
        })
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "Local Search Note" in data

    anyio.run(_run)


def test_mcp_save_does_not_cold_start_embedding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """MCP writes return quickly and do not load embeddings on the write path."""
    _prepare_vault(tmp_path)
    embedding_called = False

    def fail_embedding(config):
        nonlocal embedding_called
        embedding_called = True
        raise RuntimeError("embedding unavailable in test")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", lambda c: None)

    from kb.mcp_server import create_mcp_server

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
    )
    mcp = create_mcp_server(config)
    assert not embedding_called

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "Lazy MCP Save",
            "content": "Body",
            "source_project": "manual",
        })
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "Lazy MCP Save" in data
        assert "embedding provider is not initialized" in data

    anyio.run(_run)
    assert not embedding_called


def test_mcp_hybrid_search_falls_back_to_fulltext_when_embedding_cold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Hybrid search should not cold-start embeddings in MCP stdio."""
    _prepare_vault(tmp_path)
    embedding_called = False

    def fail_embedding(config):
        nonlocal embedding_called
        embedding_called = True
        raise RuntimeError("embedding unavailable in test")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", lambda c: None)

    from kb.mcp_server import create_mcp_server

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
    )
    mcp = create_mcp_server(config)
    assert not embedding_called

    async def _run():
        result = await mcp.call_tool("kb_hybrid_search", {
            "query": "keyword",
            "limit": 5,
        })
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "Local Search Note" in data
        assert "fulltext_fallback" in data

    anyio.run(_run)
    assert not embedding_called
