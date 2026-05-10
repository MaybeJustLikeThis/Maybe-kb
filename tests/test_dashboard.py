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
        file_hash="abc123",
    )
    note2 = Note(
        file_id="notes/life/reading.md", title="阅读习惯",
        content="每天阅读一小时。", category="life",
        tags=["reading", "life"], status="published",
        file_hash="def456",
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
    resp = client.get("/api/notes?limit=5")
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) >= 1
