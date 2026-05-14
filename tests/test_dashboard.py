"""Tests for dashboard API endpoints."""
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

    from kb.core.models import Note

    note1 = Note(
        file_id="notes/tech/docker.md", title="Docker 基础",
        content="Docker 是一个容器化平台。", category="tech",
        tags=["docker", "container"], status="published",
        file_hash="abc123", entry_type="tech-article",
        source_project="kb", content_type="markdown",
    )
    note2 = Note(
        file_id="notes/life/reading.md", title="阅读习惯",
        content="每天阅读一小时。", category="life",
        tags=["reading", "life"], status="published",
        file_hash="def456", entry_type="document",
        source_project="kb", content_type="markdown",
    )
    ctx.db.upsert_note(note1)
    ctx.db.upsert_note(note2)

    from kb.routes import create_api_router
    router = create_api_router(ctx)
    app = FastAPI()
    app.include_router(router, prefix="/api")
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


def test_get_attachments_stats(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/attachments/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert data["count"] >= 1


def test_get_categories_with_count(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/categories?with_count=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert isinstance(data["categories"], list)
    for item in data["categories"]:
        assert "name" in item
        assert "count" in item
        assert isinstance(item["count"], int)


def test_get_categories_without_count(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert isinstance(data["categories"], list)
    if data["categories"]:
        assert isinstance(data["categories"][0], str)


def test_list_notes_sort(tmp_vault):
    tmp_path, client = tmp_vault
    from kb.core.models import Note

    note_a = Note(
        file_id="notes/sort_a.md", title="Sort Note A",
        content="Content A", category="test",
        tags=[], status="published", file_hash="aaa",
    )
    note_a.updated_at = "2026-01-01"
    note_b = Note(
        file_id="notes/sort_b.md", title="Sort Note B",
        content="Content B", category="test",
        tags=[], status="published", file_hash="bbb",
    )
    note_b.updated_at = "2026-06-01"

    # Create a fresh context pointing at the same vault so we control timestamps.
    ctx2 = AppContext.from_config(_fake_config(), vault=tmp_path,
                                  with_embedding=False, with_llm=False)
    ctx2.db.upsert_note(note_a)
    ctx2.db.upsert_note(note_b)

    from kb.routes import create_api_router
    router2 = create_api_router(ctx2)
    app2 = FastAPI()
    app2.include_router(router2, prefix="/api")
    client2 = TestClient(app2)

    resp = client2.get("/api/notes?limit=5")
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) >= 2
    # note_b has later updated_at, should appear first
    assert notes[0]["file_id"] == "notes/sort_b.md"


def test_get_type_distribution(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/type-distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert "types" in data
    assert len(data["types"]) == 2  # tech-article, document
    names = {t["name"] for t in data["types"]}
    assert "tech-article" in names
    assert "document" in names
    for t in data["types"]:
        assert "name" in t
        assert "count" in t
        assert "label" in t


def test_get_source_projects(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/source-projects")
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "kb"
    assert data["projects"][0]["count"] == 2


def test_get_content_type_stats(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/content-type-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "content_types" in data
    assert len(data["content_types"]) >= 1
    assert data["content_types"][0]["name"] == "markdown"
    assert data["content_types"][0]["count"] == 2


def test_get_index_health(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/index-health")
    assert resp.status_code == 200
    data = resp.json()
    assert "notes_count" in data
    assert "vectors_count" in data
    assert "coverage" in data
    assert data["notes_count"] == 2
