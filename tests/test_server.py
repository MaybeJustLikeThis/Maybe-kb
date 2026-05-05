"""Tests for FastAPI server endpoints."""
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from kb.server import create_app
from kb.config import KBConfig, ServerConfig


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a test client with a temp kb project."""
    os.chdir(tmp_path)
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / "attachments").mkdir()
    (vault / ".kb").mkdir()

    kb_config = KBConfig(
        vault_path=vault.resolve(),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )
    app = create_app(kb_config)
    return TestClient(app)


def test_create_note(client):
    """POST /api/notes creates a note."""
    resp = client.post("/api/notes", json={
        "title": "Test Note",
        "content": "# Hello\n\nWorld",
        "category": "tech",
        "tags": ["python", "web"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Note"
    assert data["tags"] == ["python", "web"]
    assert data["category"] == "tech"
    assert data["file_id"] is not None


def test_list_notes(client):
    """GET /api/notes lists notes."""
    client.post("/api/notes", json={"title": "Note A", "content": "A", "tags": ["python"]})
    client.post("/api/notes", json={"title": "Note B", "content": "B", "tags": ["go"]})

    resp = client.get("/api/notes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_list_notes_filter_by_category(client):
    """GET /api/notes?category= filters by category."""
    client.post("/api/notes", json={"title": "A", "category": "tech", "content": "A"})
    client.post("/api/notes", json={"title": "B", "category": "life", "content": "B"})

    resp = client.get("/api/notes", params={"category": "tech"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "A"


def test_list_notes_filter_by_tag(client):
    """GET /api/notes?tag= filters by tag."""
    client.post("/api/notes", json={"title": "A", "tags": ["python"], "content": "A"})
    client.post("/api/notes", json={"title": "B", "tags": ["go"], "content": "B"})

    resp = client.get("/api/notes", params={"tag": "python"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "A"


def test_get_note(client):
    """GET /api/notes/{file_id} returns a note."""
    create_resp = client.post("/api/notes", json={"title": "Detail", "content": "Content here"})
    file_id = create_resp.json()["file_id"]

    resp = client.get(f"/api/notes/{file_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Detail"
    assert resp.json()["content"].rstrip("\n") == "Content here"


def test_get_note_not_found(client):
    """GET /api/notes/{file_id} returns 404 if not found."""
    resp = client.get("/api/notes/nonexistent.md")
    assert resp.status_code == 404


def test_update_note(client):
    """PUT /api/notes/{file_id} updates a note."""
    create_resp = client.post("/api/notes", json={"title": "Old", "content": "Old"})
    file_id = create_resp.json()["file_id"]

    resp = client.put(f"/api/notes/{file_id}", json={
        "title": "New Title",
        "content": "New Content",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"
    assert resp.json()["content"] == "New Content"


def test_delete_note(client):
    """DELETE /api/notes/{file_id} deletes a note."""
    create_resp = client.post("/api/notes", json={"title": "Delete Me", "content": "x"})
    file_id = create_resp.json()["file_id"]

    resp = client.delete(f"/api/notes/{file_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/notes/{file_id}")
    assert resp.status_code == 404


def test_search(client):
    """GET /api/search finds notes by content."""
    client.post("/api/notes", json={"title": "Vue 状态管理", "content": "Pinia 是推荐方案"})
    client.post("/api/notes", json={"title": "Docker", "content": "容器部署"})

    resp = client.get("/api/search", params={"q": "Pinia"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any("Vue" in r["title"] for r in data)


def test_get_tags(client):
    """GET /api/tags returns all tags."""
    client.post("/api/notes", json={"title": "A", "tags": ["python", "web"]})
    client.post("/api/notes", json={"title": "B", "tags": ["python", "fastapi"]})

    resp = client.get("/api/tags")
    assert resp.status_code == 200
    tags = resp.json()["tags"]
    assert "python" in tags
    assert "web" in tags
    assert "fastapi" in tags


def test_get_categories(client):
    """GET /api/categories returns all categories."""
    client.post("/api/notes", json={"title": "A", "category": "tech", "content": "A"})
    client.post("/api/notes", json={"title": "B", "category": "life", "content": "B"})

    resp = client.get("/api/categories")
    assert resp.status_code == 200
    cats = resp.json()["categories"]
    assert "tech" in cats
    assert "life" in cats
