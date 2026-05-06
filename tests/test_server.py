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


def test_path_traversal_blocked(client):
    """Path traversal via ../ is blocked with 403."""
    # URL-encode dots to prevent HTTP client from normalizing the path
    resp = client.get("/api/notes/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    assert resp.status_code == 403


def test_path_traversal_delete_blocked(client):
    """Path traversal via DELETE is blocked with 403."""
    resp = client.delete("/api/notes/%2e%2e%2fWindows%2fSystem32")
    assert resp.status_code == 403


def test_create_note_path_traversal_blocked(client):
    """POST /api/notes sanitizes path-traversal chars in title."""
    resp = client.post("/api/notes", json={
        "title": "../../etc/hosts",
        "content": "evil",
    })
    assert resp.status_code == 200
    file_id = resp.json()["file_id"]
    assert file_id.startswith("notes/")
    assert "/../" not in file_id  # no path traversal escape


def test_put_path_traversal_blocked(client):
    """PUT with path traversal is blocked with 403."""
    resp = client.put(
        "/api/notes/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        json={"title": "evil"},
    )
    assert resp.status_code == 403


def test_nested_note_still_works(client):
    """Legitimate nested note paths should still work."""
    create_resp = client.post("/api/notes", json={
        "title": "Nested Note",
        "content": "Nested content",
        "category": "tech",
    })
    file_id = create_resp.json()["file_id"]
    resp = client.get(f"/api/notes/{file_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Nested Note"


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
    assert resp.json()["content"].rstrip("\n") == "New Content"


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


def test_get_index_status(client):
    """GET /api/index returns notes count."""
    client.post("/api/notes", json={"title": "A", "content": "a"})
    client.post("/api/notes", json={"title": "B", "content": "b"})

    resp = client.get("/api/index")
    assert resp.status_code == 200
    assert resp.json()["notes_count"] == 2


def test_trigger_index(client):
    """POST /api/index re-indexes notes and returns count."""
    client.post("/api/notes", json={"title": "X", "content": "hello"})
    client.post("/api/notes", json={"title": "Y", "content": "world"})

    resp = client.post("/api/index")
    assert resp.status_code == 200
    assert resp.json()["indexed"] >= 2


def test_upload_attachment(client):
    """POST /api/attachments uploads a file and returns its path."""
    from io import BytesIO

    resp = client.post(
        "/api/attachments",
        files={"file": ("test.txt", BytesIO(b"hello world"), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "path" in data
    assert data["path"].startswith("attachments/")
    assert data["path"].endswith(".txt")


def test_semantic_search_requires_query(client):
    """GET /api/semantic-search without q returns 422."""
    resp = client.get("/api/semantic-search")
    assert resp.status_code == 422


def test_semantic_search_empty_store(client):
    """GET /api/semantic-search with empty vector store returns []."""
    resp = client.get("/api/semantic-search", params={"q": "测试查询"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_semantic_search_finds_similar(client):
    """Semantic search returns notes after vectors are populated."""
    from kb.vector import VectorStore, VectorRecord
    from kb.embedding import LocalEmbeddingProvider

    resp1 = client.post("/api/notes", json={
        "title": "Python Async", "content": "asyncio 协程并发编程",
    })
    resp2 = client.post("/api/notes", json={
        "title": "Unrelated", "content": "今天天气很好适合散步",
    })
    fid1 = resp1.json()["file_id"]
    fid2 = resp2.json()["file_id"]

    provider = LocalEmbeddingProvider("BAAI/bge-small-zh-v1.5")
    v1 = provider.embed("asyncio 协程并发编程").vector
    v2 = provider.embed("今天天气很好适合散步").vector

    vault = Path.cwd()
    (vault / ".kb").mkdir(exist_ok=True)
    store = VectorStore(vault / ".kb" / "vectors.lance")
    store.upsert_chunks(fid1, [
        VectorRecord(id=fid1, chunk_id=0, vector=v1, text="asyncio 协程并发编程"),
    ])
    store.upsert_chunks(fid2, [
        VectorRecord(id=fid2, chunk_id=0, vector=v2, text="今天天气很好适合散步"),
    ])
    store.close()

    resp = client.get("/api/semantic-search", params={"q": "异步编程", "limit": "5"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any("Python" in r["title"] for r in data)
