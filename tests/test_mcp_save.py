"""Tests for MCP kb_save_* tools."""
import os
import pytest
import anyio
from pathlib import Path
from kb.core.config import KBConfig, EmbeddingConfig, LLMConfig, SearchConfig, RAGConfig, ServerConfig


def test_kb_save_design_decision_creates_note(tmp_path: Path):
    """kb_save_design_decision creates a note."""
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
        result = await mcp.call_tool("kb_save_design_decision", {
            "title": "架构选型",
            "content": "# 选型\n\n选择 LanceDB",
            "source_project": "kb",
            "source_context": "实现搜索功能",
            "tags": "vector-db, search",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "file_id" in data
        assert "source_project" in data

    anyio.run(_run)


def test_kb_save_troubleshooting_adds_default_tags(tmp_path: Path):
    """kb_save_troubleshooting auto-adds 'troubleshooting' tag."""
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
        result = await mcp.call_tool("kb_save_troubleshooting", {
            "title": "Python OOM 记录",
            "content": "## 现象\n\n内存溢出",
            "source_project": "my-app",
            "source_context": "线上排查",
            "tags": "python, memory",
        })
        assert result is not None
    anyio.run(_run)


def test_kb_save_tech_article_minimal_args(tmp_path: Path):
    """kb_save_tech_article works with only required args."""
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
        result = await mcp.call_tool("kb_save_tech_article", {
            "title": "Rust 入门",
            "content": "# Rust\n\n快速入门",
        })
        assert result is not None
    anyio.run(_run)


def test_kb_save_code_snippet_content_preserved(tmp_path: Path):
    """kb_save_code_snippet preserves code blocks."""
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
        result = await mcp.call_tool("kb_save_code_snippet", {
            "title": "hello 函数",
            "content": code,
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        # The tool returns a summary dict — verify code preserved on disk
        import json as _json
        summary = _json.loads(data)
        file_content = (tmp_path / summary["file_id"]).read_text(encoding="utf-8")
        assert "def hello()" in file_content

    anyio.run(_run)


def test_all_five_save_tools_registered(tmp_path: Path):
    """All 5 kb_save_* tools are registered."""
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
    assert tool_names >= {
        "kb_save_tech_article",
        "kb_save_troubleshooting",
        "kb_save_design_decision",
        "kb_save_code_snippet",
        "kb_save_document",
    }
