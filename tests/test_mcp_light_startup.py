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
    """MCP keyword tools start even when embedding and LLM factories fail."""
    _prepare_vault(tmp_path)

    def fail_embedding(config):
        raise RuntimeError("embedding factory should not run at startup")

    def fail_llm(config):
        raise RuntimeError("llm factory should not run at startup")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", fail_llm)

    from kb.mcp_server import create_mcp_server

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
    )
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_search", {
            "query": "keyword",
            "limit": 5,
        })
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "Local Search Note" in data

    anyio.run(_run)
