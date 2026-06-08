"""Tests for dashboard API endpoints (v1)."""
import pytest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kb.core.context import AppContext


@pytest.fixture
def tmp_vault(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "attachments").mkdir()
    (tmp_path / "attachments" / "img.png").write_bytes(b"fake")
    (tmp_path / "attachments" / "doc.pdf").write_bytes(b"fake")
    (tmp_path / ".kb").mkdir()
    ctx = AppContext.from_config(_fake_config(), vault=tmp_path,
                                 with_embedding=False, with_llm=False)

    from kb.data.models import Note

    note1 = Note(
        file_id="notes/tech/docker.md", title="Docker 基础",
        content="Docker 是一个容器化平台。", category="tech",
        tags=["docker", "container"], status="published",
        file_hash="abc123",
        source_project="kb", content_type="markdown",
    )
    note2 = Note(
        file_id="notes/life/reading.md", title="阅读习惯",
        content="每天阅读一小时。", category="life",
        tags=["reading", "life"], status="published",
        file_hash="def456",
        source_project="kb", content_type="markdown",
    )
    ctx.db.upsert_note(note1)
    ctx.db.upsert_note(note2)

    from kb.api.v1 import create_v1_router
    router = create_v1_router(ctx)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    return tmp_path, client


def _fake_config():
    from kb.core.config import (
        KBConfig, SearchConfig, EmbeddingConfig,
        LLMConfig, RAGConfig, ServerConfig,
    )
    return KBConfig(
        vault_path=Path("."),
        search=SearchConfig(max_results=20),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
        llm=LLMConfig(provider="ollama", model="qwen2.5:7b"),
        rag=RAGConfig(top_k=5),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )


def test_get_dashboard(tmp_vault):
    """GET /api/v1/dashboard returns notes and attachments counts."""
    tmp_path, client = tmp_vault
    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["error"] is None
    data = payload["data"]
    assert data["notes_count"] == 2
    assert data["attachments_count"] >= 1


def test_get_taxonomy(tmp_vault):
    """GET /api/v1/taxonomy returns categories, tags, source projects, content types."""
    tmp_path, client = tmp_vault
    resp = client.get("/api/v1/taxonomy")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["error"] is None
    data = payload["data"]
    assert isinstance(data["tags"], list)
    assert isinstance(data["categories"], list)
    for item in data["categories"]:
        assert "name" in item
        assert "count" in item
        assert isinstance(item["count"], int)


def test_list_notes_sort(tmp_vault):
    """GET /api/v1/notes respects pagination envelope."""
    tmp_path, client = tmp_vault
    resp = client.get("/api/v1/notes", params={"limit": 5})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["error"] is None
    notes = payload["data"]
    assert len(notes) >= 2
    for note in notes:
        assert {"file_id", "title", "tags", "category"}.issubset(note)


def test_get_source_projects(tmp_vault):
    """GET /api/v1/sources returns source project info."""
    tmp_path, client = tmp_vault
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["error"] is None
    data = payload["data"]
    assert "sources" in data


def test_get_health(tmp_vault):
    """GET /api/v1/health returns notes_count, vectors_count, coverage."""
    tmp_path, client = tmp_vault
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["error"] is None
    data = payload["data"]
    assert "status" in data
    assert isinstance(data["checks"], list)
    assert "notes_count" in data["summary"]
    assert "vectors_count" in data["summary"]
    assert "coverage" in data["summary"]
    assert data["summary"]["notes_count"] == 2
