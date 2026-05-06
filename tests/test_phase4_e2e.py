"""Phase 4 end-to-end tests: CLI ask, API chat, MCP RAG, config template."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def kb_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a kb project with notes, cd into it."""
    import os
    os.chdir(tmp_path)

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "python-async.md").write_text(
        "---\ntitle: Python Async\ntags: python, async\ncategory: tech\n---\n\n"
        "asyncio 是 Python 的异步编程标准库，基于事件循环和协程。\n",
        encoding="utf-8",
    )
    (notes_dir / "docker.md").write_text(
        "---\ntitle: Docker Tips\ntags: docker, devops\ncategory: tech\n---\n\n"
        "Docker 容器通过 docker-compose 编排多服务。\n",
        encoding="utf-8",
    )
    return tmp_path


# ── Config template tests ──────────────────────────────────────────────

def test_init_generates_full_config(kb_project: Path):
    """kb init creates config.toml with all 6 sections."""
    from kb.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    config = (kb_project / "config.toml").read_text(encoding="utf-8")
    assert "[general]" in config
    assert "[search]" in config
    assert "[embedding]" in config
    assert "[llm]" in config
    assert "[rag]" in config
    assert "[server]" in config
    assert "top_k = 5" in config
    assert 'provider = "ollama"' in config
    assert 'provider = "local"' in config


def test_load_config_reads_all_sections(kb_project: Path):
    """load_config reads rag, llm, embedding, server from config.toml."""
    from kb.cli import app
    from kb.core.config import load_config

    runner.invoke(app, ["init"])
    config = load_config(kb_project)

    assert config.rag.top_k == 5
    assert config.llm.provider == "ollama"
    assert config.embedding.provider == "local"
    assert config.server.port == 8420


# ── CLI ask command tests ──────────────────────────────────────────────

def test_cli_ask_command_help(kb_project: Path):
    """kb ask --help shows options."""
    from kb.cli import app

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["ask", "--help"])
    assert result.exit_code == 0
    assert "--stream" in result.output


def test_cli_ask_with_mocked_llm(kb_project: Path, monkeypatch: pytest.MonkeyPatch):
    """kb ask returns LLM response via mock."""
    from kb.cli import app
    from kb.data.embedding import EmbeddingResult

    runner.invoke(app, ["init", "--import-existing"])

    class FakeLLM:
        def generate(self, prompt, *, system_prompt=""):
            from kb.data.llm import LLMResponse
            return LLMResponse(text="Python asyncio answer", tokens_used=10, model="mock")
        def generate_stream(self, prompt, *, system_prompt=""):
            yield None
        @property
        def model_name(self):
            return "mock"

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 512

    monkeypatch.setattr("kb.data.llm.create_llm_provider", lambda c: FakeLLM())
    monkeypatch.setattr("kb.data.embedding.create_embedding_provider", lambda c: FakeEmbedding())

    result = runner.invoke(app, ["ask", "什么是 Python 异步？", "--top-k", "3"])
    assert result.exit_code == 0
    assert "Python" in result.output or "asyncio" in result.output


def test_cli_ask_stream_with_mocked_llm(kb_project: Path, monkeypatch: pytest.MonkeyPatch):
    """kb ask --stream streams chunks."""
    from kb.cli import app
    from kb.data.llm import LLMResponse
    from kb.data.embedding import EmbeddingResult

    runner.invoke(app, ["init", "--import-existing"])

    class FakeLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="mock", tokens_used=0, model="mock")
        def generate_stream(self, prompt, *, system_prompt=""):
            yield LLMResponse(text="chunk1", tokens_used=0, model="mock")
            yield LLMResponse(text="chunk2", tokens_used=0, model="mock")
        @property
        def model_name(self):
            return "mock"

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 512

    monkeypatch.setattr("kb.data.llm.create_llm_provider", lambda c: FakeLLM())
    monkeypatch.setattr("kb.data.embedding.create_embedding_provider", lambda c: FakeEmbedding())

    result = runner.invoke(app, ["ask", "test", "--stream"])
    assert result.exit_code == 0
    assert "chunk1chunk2" in result.output


# ── API chat endpoint tests ────────────────────────────────────────────

def test_api_chat_ask_with_mock(kb_project: Path, monkeypatch: pytest.MonkeyPatch):
    """POST /api/chat/ask returns RAG answer."""
    from kb.cli import app
    from kb.server import create_app
    from kb.core.config import load_config
    from kb.data.llm import LLMResponse
    from kb.data.embedding import EmbeddingResult
    from fastapi.testclient import TestClient

    runner.invoke(app, ["init", "--import-existing"])
    config = load_config(kb_project)

    class FakeLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="RAG answer", tokens_used=5, model="mock")
        def generate_stream(self, prompt, *, system_prompt=""):
            yield None
        @property
        def model_name(self):
            return "mock"

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 512

    monkeypatch.setattr("kb.routes.create_llm_provider", lambda c: FakeLLM())
    monkeypatch.setattr("kb.routes.create_embedding_provider", lambda c: FakeEmbedding())

    web_app = create_app(config)
    client = TestClient(web_app)

    r = client.post("/api/chat/ask", json={"query": "test", "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "RAG answer"
    assert data["model"] == "mock"
    assert "tokens_used" in data


def test_api_chat_stream_with_mock(kb_project: Path, monkeypatch: pytest.MonkeyPatch):
    """POST /api/chat streams SSE chunks."""
    from kb.cli import app
    from kb.server import create_app
    from kb.core.config import load_config
    from kb.data.llm import LLMResponse
    from kb.data.embedding import EmbeddingResult
    from fastapi.testclient import TestClient

    runner.invoke(app, ["init", "--import-existing"])
    config = load_config(kb_project)

    class FakeLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="mock", tokens_used=0, model="mock")
        def generate_stream(self, prompt, *, system_prompt=""):
            yield LLMResponse(text="Hello", tokens_used=0, model="mock")
            yield LLMResponse(text=" World", tokens_used=0, model="mock")
        @property
        def model_name(self):
            return "mock"

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 512

    monkeypatch.setattr("kb.routes.create_llm_provider", lambda c: FakeLLM())
    monkeypatch.setattr("kb.routes.create_embedding_provider", lambda c: FakeEmbedding())

    web_app = create_app(config)
    client = TestClient(web_app)

    r = client.post("/api/chat", json={"query": "test", "top_k": 3})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")

    lines = [l for l in r.text.strip().split("\n") if l.startswith("data: ")]
    assert len(lines) >= 2
    import json
    chunks = [json.loads(l[6:]) for l in lines]
    assert chunks[0]["text"] == "Hello"


def test_api_chat_ask_rejects_empty_query(kb_project: Path):
    """POST /api/chat/ask with empty query returns 422."""
    from kb.cli import app
    from kb.server import create_app
    from kb.core.config import load_config
    from fastapi.testclient import TestClient

    runner.invoke(app, ["init"])
    config = load_config(kb_project)
    web_app = create_app(config)
    client = TestClient(web_app)

    r = client.post("/api/chat/ask", json={"query": ""})
    assert r.status_code == 422


def test_api_chat_requires_llm_config(kb_project: Path):
    """Chat endpoints return 400 when no LLM config provided."""
    from kb.cli import app
    from kb.core.config import load_config
    from kb.routes import create_api_router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    runner.invoke(app, ["init"])
    config = load_config(kb_project)

    router = create_api_router(
        config.vault_path,
        config.vault_path / ".kb" / "kb.db",
        embedding_config=config.embedding,
        llm_config=None,
    )
    app_fastapi = FastAPI()
    app_fastapi.include_router(router, prefix="/api")
    client = TestClient(app_fastapi)

    r = client.post("/api/chat/ask", json={"query": "test"})
    assert r.status_code == 400


# ── MCP RAG tool test ──────────────────────────────────────────────────

def test_mcp_rag_tool_registered():
    """kb_rag_query is registered as an MCP tool."""
    from kb.core.config import KBConfig
    from kb.mcp_server import create_mcp_server

    config = KBConfig(vault_path=Path("/tmp/mcp-rag-test"))
    server = create_mcp_server(config)
    tool_names = [t.name for t in server._tool_manager._tools.values()]
    assert "kb_rag_query" in tool_names
    assert "kb_hybrid_search" in tool_names
    assert "kb_search" in tool_names


def test_mcp_rag_query_returns_answer(monkeypatch: pytest.MonkeyPatch):
    """kb_rag_query MCP tool returns answer dict."""
    from kb.core.config import KBConfig
    from kb.mcp_server import create_mcp_server
    from kb.data.llm import LLMResponse
    from kb.data.embedding import EmbeddingResult

    class FakeLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="MCP answer", tokens_used=5, model="mock")
        def generate_stream(self, prompt, *, system_prompt=""):
            yield None
        @property
        def model_name(self):
            return "mock"

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 512

    monkeypatch.setattr("kb.mcp_server.create_llm_provider", lambda c: FakeLLM())
    monkeypatch.setattr("kb.mcp_server.create_embedding_provider", lambda c: FakeEmbedding())

    config = KBConfig(vault_path=Path("/tmp/mcp-rag-test"))
    server = create_mcp_server(config)

    tool = next(
        t for t in server._tool_manager._tools.values()
        if t.name == "kb_rag_query"
    )
    result = tool.fn(query="What is Python?", top_k=3)
    assert result["answer"] == "MCP answer"
    assert result["model"] == "mock"
    assert result["tokens_used"] == 5


# ── Format context integration tests ───────────────────────────────────

def test_search_result_to_context_roundtrip():
    """Verify SearchResult → format_context → build_rag_prompt chain."""
    from kb.core.search import SearchResult
    from kb.core.rag import format_context, build_rag_prompt
    from kb.data.database import Database
    from kb.core.models import Note

    db = Database(Path("/tmp/phase4-roundtrip.db"))
    db.initialize()
    db.upsert_note(Note(
        file_id="a", title="Note A", content="Content A", tags=[],
        category="", created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    ))
    db.upsert_note(Note(
        file_id="b", title="Note B", content="Content B", tags=[],
        category="", created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    ))
    try:
        results = [
            SearchResult(file_id="a", title="Note A", score=0.9, source="hybrid"),
            SearchResult(file_id="b", title="Note B", score=0.5, source="fts5"),
        ]
        context = format_context(results, db)
        assert "Note A" in context
        assert "Content A" in context
        assert "[1]" in context
        assert "[2]" in context

        prompt = build_rag_prompt("test query", context)
        assert "test query" in prompt
        assert "Note A" in prompt
    finally:
        db.close()


def test_rag_query_orchestration_with_mocks(monkeypatch: pytest.MonkeyPatch):
    """Full rag_query orchestration with all providers mocked."""
    from kb.core.rag import rag_query
    from kb.data.database import Database
    from kb.data.llm import LLMResponse
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult
    from kb.core.models import Note

    db = Database(Path("/tmp/phase4-orch.db"))
    db.initialize()
    db.upsert_note(Note(
        file_id="test-id", title="Test Note", content="Python async content.",
        tags=["python"], category="tech",
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    ))
    try:
        class MockLLM:
            def generate(self, prompt, *, system_prompt=""):
                return LLMResponse(text="Generated answer", tokens_used=3, model="mock")
            @property
            def model_name(self):
                return "mock"

        class MockEmbedding(EmbeddingProvider):
            def embed(self, text):
                return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
            def embed_batch(self, texts):
                return [self.embed(t) for t in texts]
            @property
            def dimension(self):
                return 512

        class MockStore:
            def search(self, query_vector, limit=20):
                return []
            def close(self):
                pass

        response = rag_query("test query", db, MockEmbedding(), MockStore(), MockLLM(), top_k=3)
        assert isinstance(response, LLMResponse)
        assert response.text == "Generated answer"
        assert response.model == "mock"
    finally:
        db.close()


# ── ChatHistory integration test ───────────────────────────────────────

def test_chat_history_full_workflow(tmp_path: Path):
    """Full session lifecycle: create → add → list → get → delete."""
    from kb.data.chat_history import ChatHistory

    ch = ChatHistory(tmp_path / "ch.db")
    ch.initialize()

    s1 = ch.create_session("Session 1")
    s2 = ch.create_session("Session 2")
    assert s1.session_id != s2.session_id
    assert s1.title == "Session 1"

    ch.add_message(s1.session_id, "user", "Hello")
    ch.add_message(s1.session_id, "assistant", "Hi there!")
    ch.add_message(s2.session_id, "user", "Question 2")

    msgs = ch.get_messages(s1.session_id)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"

    sessions = ch.list_sessions()
    assert sessions[0].session_id == s2.session_id

    ch.delete_session(s1.session_id)
    assert ch.get_messages(s1.session_id) == []

    ch.close()
