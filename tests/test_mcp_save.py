"""Tests for MCP kb_save tool."""
import anyio
import pytest
from pathlib import Path
from kb.core.config import KBConfig, EmbeddingConfig, LLMConfig, SearchConfig, RAGConfig, ServerConfig


def _prepare_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()


def test_kb_save_creates_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_save creates a note with source_project."""
    _prepare_vault(tmp_path, monkeypatch)

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "Architecture Choice",
            "content": "# Architecture Choice\n\nChoose LanceDB",
            "source_project": "agent",
            "source_context": "implement search",
            "tags": "vector-db, search",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "file_id" in data
        assert "source_project" in data

    anyio.run(_run)


def test_kb_save_requires_source_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_save requires source_project (FastMCP enforces non-default str params)."""
    _prepare_vault(tmp_path, monkeypatch)

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "Rust Intro",
            "content": "# Rust\n\nSimple note content.",
            "source_project": "manual",
        })
        assert result is not None

    anyio.run(_run)


def test_kb_save_content_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_save preserves code blocks on disk."""
    _prepare_vault(tmp_path, monkeypatch)

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        code = "```python\ndef hello():\n    print('hi')\n```"
        result = await mcp.call_tool("kb_save", {
            "title": "hello function",
            "content": code,
            "source_project": "blog",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        import json as _json
        summary = _json.loads(data)
        file_content = (tmp_path / summary["file_id"]).read_text(encoding="utf-8")
        assert "def hello()" in file_content

    anyio.run(_run)


def test_kb_save_tool_registered(tmp_path: Path):
    """kb_save tool is registered."""
    from kb.mcp_server import create_mcp_server

    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()
    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    mcp = create_mcp_server(config)
    tool_names = {t.name for t in mcp._tool_manager._tools.values()}
    assert "kb_save" in tool_names


def test_kb_add_has_source_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_add accepts and stores source_project."""
    _prepare_vault(tmp_path, monkeypatch)

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_add", {
            "title": "MCP Add Test",
            "content": "# Test\n\nContent",
            "source_project": "agent",
            "source_context": "testing kb_add",
            "tags": "test, mcp",
            "category": "test",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "file_id" in data
        assert "source_project" in data
        assert "agent" in data

    anyio.run(_run)


def test_kb_add_rejects_empty_title(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_add returns error dict for empty title."""
    _prepare_vault(tmp_path, monkeypatch)

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_add", {
            "title": "",
            "content": "x",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "error" in data
        assert "title" in data

    anyio.run(_run)


def test_kb_save_returns_indexed_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_save best-effort indexes the created note and returns vector count."""
    _prepare_vault(tmp_path, monkeypatch)

    from kb.data.embedding import EmbeddingResult

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[1.0, 0.0, 0.0], dimension=3, tokens_used=len(text))

        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

        @property
        def dimension(self):
            return 3

    calls: list[str] = []

    def fake_ensure_embedding(self):
        return FakeEmbedding()

    def fake_index_note_vectors(vault, db, provider, file_id, *, vector_store=None):
        calls.append(file_id)
        return 1

    monkeypatch.setattr("kb.core.context.AppContext.ensure_embedding", fake_ensure_embedding)
    monkeypatch.setattr("kb.mcp_server.index_note_vectors", fake_index_note_vectors)

    config = KBConfig(vault_path=tmp_path.resolve())
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "Indexed MCP Save",
            "content": "Body to index",
            "source_project": "agent",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        import json as _json
        payload = _json.loads(data)
        assert payload["indexed_vectors"] == 1
        assert calls == [payload["file_id"]]

    anyio.run(_run)
