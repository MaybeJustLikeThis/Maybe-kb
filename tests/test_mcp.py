"""Tests for MCP server."""
import pytest
from pathlib import Path
from kb.core.config import KBConfig, EmbeddingConfig


def test_create_mcp_server_returns_fastmcp():
    config = KBConfig(
        vault_path=Path("/tmp/test-vault"),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)
    assert mcp is not None
    assert mcp.name == "kb"


def test_mcp_tools_registered():
    """All 6 tools are registered."""
    config = KBConfig(
        vault_path=Path("/tmp/test-vault"),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)
    tool_names = {t.name for t in mcp._tool_manager._tools.values()}
    assert tool_names >= {
        "kb_search", "kb_semantic_search", "kb_hybrid_search",
        "kb_read", "kb_list", "kb_add",
    }


def test_kb_add_creates_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_add tool creates a note via services layer."""
    import os as _os
    import anyio
    _os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_add", {
            "title": "MCP Test",
            "content": "# Hello\n\nMCP content.",
            "category": "tech",
            "tags": "mcp, test",
        })
        assert result is not None
        assert len(result) > 0
    anyio.run(_run)


def test_kb_list_with_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_list returns notes filtered by category/tag."""
    import os as _os
    import anyio
    _os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        await mcp.call_tool("kb_add", {"title": "Note A", "content": "A", "category": "tech", "tags": "python"})
        await mcp.call_tool("kb_add", {"title": "Note B", "content": "B", "category": "life", "tags": "diary"})
        result = await mcp.call_tool("kb_list", {"category": "tech"})
        assert result is not None
        result = await mcp.call_tool("kb_list", {"tag": "python"})
        assert result is not None
    anyio.run(_run)


def test_kb_read_returns_full_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_read returns full note content by file_id."""
    import os as _os
    import anyio
    _os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        created = await mcp.call_tool("kb_add", {
            "title": "Read Test",
            "content": "# Read Test\n\nContent body.",
            "category": "ref",
            "tags": "reference, test",
        })
        # kb_add returns list of TextContent; extract file_id from first element
        if isinstance(created, (list, tuple)):
            c0 = created[0]
            file_id = c0.text if hasattr(c0, "text") else str(c0)
        else:
            file_id = str(created)
        result = await mcp.call_tool("kb_read", {"file_id": file_id})
        # result is (content_list, metadata) tuple
        content_list = result[0] if isinstance(result, tuple) else result
        assert content_list is not None
    anyio.run(_run)


def test_kb_read_blocked_path_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_read returns None for path traversal attempt."""
    import os as _os
    import anyio
    _os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        content, _meta = await mcp.call_tool("kb_read", {"file_id": "../etc/passwd"})
        assert len(content) == 0
    anyio.run(_run)


def test_kb_hybrid_search_returns_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_hybrid_search fuses FTS5 and semantic results."""
    import os as _os
    import anyio
    _os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        await mcp.call_tool("kb_add", {
            "title": "Python Guide", "content": "Python async programming with asyncio",
            "category": "tech", "tags": "python",
        })
        await mcp.call_tool("kb_add", {
            "title": "Golang Guide", "content": "Golang concurrency with goroutines",
            "category": "tech", "tags": "golang",
        })
        result = await mcp.call_tool("kb_hybrid_search", {"query": "python 异步", "limit": 5})
        assert result is not None
        assert len(result) > 0
    anyio.run(_run)


def test_mcp_tools_present():
    from kb.mcp_server import create_mcp_server
    from kb.core.config import KBConfig, EmbeddingConfig, LLMConfig, SearchConfig, RAGConfig, ServerConfig
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp)
        config = KBConfig(
            vault_path=vault,
            embedding=EmbeddingConfig(provider="local"),
            llm=LLMConfig(provider="ollama"),
            search=SearchConfig(),
            rag=RAGConfig(),
            server=ServerConfig(),
        )
        mcp = create_mcp_server(config)
        tool_names = [t.name for t in mcp._tool_manager._tools.values()]
        assert "kb_search" in tool_names
        assert "kb_semantic_search" in tool_names
        assert "kb_hybrid_search" in tool_names
        assert "kb_read" in tool_names
        assert "kb_list" in tool_names
        assert "kb_add" in tool_names
        assert "kb_rag_query" in tool_names
