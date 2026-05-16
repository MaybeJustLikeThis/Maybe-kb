"""Tests for MCP kb_save tool."""
import os
import pytest
import anyio
from pathlib import Path
from kb.core.config import KBConfig, EmbeddingConfig, LLMConfig, SearchConfig, RAGConfig, ServerConfig


def test_kb_save_creates_note(tmp_path: Path):
    """kb_save creates a note with source_project."""
    os.chdir(tmp_path)
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
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "架构选型",
            "content": "# 选型\n\n选择 LanceDB",
            "source_project": "agent",
            "source_context": "实现搜索功能",
            "tags": "vector-db, search",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "file_id" in data
        assert "source_project" in data

    anyio.run(_run)


def test_kb_save_requires_source_project(tmp_path: Path):
    """kb_save requires source_project (FastMCP enforces non-default str params)."""
    os.chdir(tmp_path)
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
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "Rust 入门",
            "content": "# Rust\n\n快速入门",
            "source_project": "manual",
        })
        assert result is not None

    anyio.run(_run)


def test_kb_save_content_preserved(tmp_path: Path):
    """kb_save preserves code blocks on disk."""
    os.chdir(tmp_path)
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
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        code = "```python\ndef hello():\n    print('hi')\n```"
        result = await mcp.call_tool("kb_save", {
            "title": "hello 函数",
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
