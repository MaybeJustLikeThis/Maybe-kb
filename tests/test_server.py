"""Tests for FastAPI server endpoints (v1)."""
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from kb.server import create_app
from kb.core.config import GeneralConfig, KBConfig, ServerConfig


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


def test_create_app_does_not_initialize_ai_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating the web app should not load embedding or LLM providers."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / "attachments").mkdir()
    (vault / ".kb").mkdir()

    def fail_embedding(config):
        raise AssertionError("embedding provider should be lazy")

    def fail_llm(config):
        raise AssertionError("llm provider should be lazy")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", fail_llm)

    kb_config = KBConfig(
        vault_path=vault.resolve(),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )

    app = create_app(kb_config)

    assert app.title == "kb"


def test_v1_create_note_does_not_initialize_ai_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic note creation should stay lightweight."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / "attachments").mkdir()
    (vault / ".kb").mkdir()

    def fail_embedding(config):
        raise AssertionError("embedding provider should be lazy")

    def fail_llm(config):
        raise AssertionError("llm provider should be lazy")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", fail_llm)

    kb_config = KBConfig(
        vault_path=vault.resolve(),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )
    client = TestClient(create_app(kb_config))

    response = client.post("/api/v1/notes", json={
        "title": "Lightweight Note",
        "content": "No model load needed",
    })

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Lightweight Note"


def test_create_note(client):
    """POST /api/v1/notes creates a note."""
    resp = client.post("/api/v1/notes", json={
        "title": "Test Note",
        "content": "# Hello\n\nWorld",
        "category": "tech",
        "tags": ["python", "web"],
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Test Note"
    assert data["tags"] == ["python", "web"]
    assert data["category"] == "tech"
    assert data["file_id"] is not None


def test_list_notes(client):
    """GET /api/v1/notes lists notes."""
    client.post("/api/v1/notes", json={"title": "Note A", "content": "A", "tags": ["python"]})
    client.post("/api/v1/notes", json={"title": "Note B", "content": "B", "tags": ["go"]})

    resp = client.get("/api/v1/notes")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2


def test_list_notes_filter_by_category(client):
    """GET /api/v1/notes?category= filters by category."""
    client.post("/api/v1/notes", json={"title": "A", "category": "tech", "content": "A"})
    client.post("/api/v1/notes", json={"title": "B", "category": "life", "content": "B"})

    resp = client.get("/api/v1/notes", params={"category": "tech"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "A"


def test_list_notes_filter_by_tag(client):
    """GET /api/v1/notes?tag= filters by tag."""
    client.post("/api/v1/notes", json={"title": "A", "tags": ["python"], "content": "A"})
    client.post("/api/v1/notes", json={"title": "B", "tags": ["go"], "content": "B"})

    resp = client.get("/api/v1/notes", params={"tag": "python"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "A"


def test_get_note(client):
    """GET /api/v1/notes/{file_id} returns a note."""
    create_resp = client.post("/api/v1/notes", json={"title": "Detail", "content": "Content here"})
    file_id = create_resp.json()["data"]["file_id"]

    resp = client.get(f"/api/v1/notes/{file_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Detail"
    assert data["content"].rstrip("\n") == "Content here"


def test_get_note_not_found(client):
    """GET /api/v1/notes/{file_id} returns 404 if not found."""
    resp = client.get("/api/v1/notes/nonexistent.md")
    assert resp.status_code == 404


def test_path_traversal_blocked(client):
    """Path traversal via ../ is blocked with 403."""
    resp = client.get("/api/v1/notes/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    assert resp.status_code == 403


def test_path_traversal_delete_blocked(client):
    """Path traversal via DELETE is blocked with 403."""
    resp = client.delete("/api/v1/notes/%2e%2e%2fWindows%2fSystem32")
    assert resp.status_code == 403


def test_create_note_path_traversal_blocked(client):
    """POST /api/v1/notes sanitizes path-traversal chars in title."""
    resp = client.post("/api/v1/notes", json={
        "title": "../../etc/hosts",
        "content": "evil",
    })
    assert resp.status_code == 200
    file_id = resp.json()["data"]["file_id"]
    assert file_id.startswith("notes/")
    assert "/../" not in file_id  # no path traversal escape


def test_put_path_traversal_blocked(client):
    """PUT with path traversal is blocked with 403."""
    resp = client.put(
        "/api/v1/notes/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        json={"title": "evil"},
    )
    assert resp.status_code == 403


def test_nested_note_still_works(client):
    """Legitimate nested note paths should still work."""
    create_resp = client.post("/api/v1/notes", json={
        "title": "Nested Note",
        "content": "Nested content",
        "category": "tech",
    })
    file_id = create_resp.json()["data"]["file_id"]
    resp = client.get(f"/api/v1/notes/{file_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Nested Note"


def test_update_note(client):
    """PUT /api/v1/notes/{file_id} updates a note."""
    create_resp = client.post("/api/v1/notes", json={"title": "Old", "content": "Old"})
    file_id = create_resp.json()["data"]["file_id"]

    resp = client.put(f"/api/v1/notes/{file_id}", json={
        "title": "New Title",
        "content": "New Content",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "New Title"
    assert data["content"].rstrip("\n") == "New Content"


def test_delete_note(client):
    """DELETE /api/v1/notes/{file_id} deletes a note."""
    create_resp = client.post("/api/v1/notes", json={"title": "Delete Me", "content": "x"})
    file_id = create_resp.json()["data"]["file_id"]

    resp = client.delete(f"/api/v1/notes/{file_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/notes/{file_id}")
    assert resp.status_code == 404


def test_search(client):
    """GET /api/v1/search finds notes by content."""
    client.post("/api/v1/notes", json={"title": "Vue 状态管理", "content": "Pinia 是推荐方案"})
    client.post("/api/v1/notes", json={"title": "Docker", "content": "容器部署"})

    resp = client.get("/api/v1/search", params={"q": "Pinia"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any("Vue" in r["note"]["title"] for r in data)


def test_get_tags(client):
    """GET /api/v1/taxonomy returns tags."""
    client.post("/api/v1/notes", json={"title": "A", "tags": ["python", "web"], "content": "A"})
    client.post("/api/v1/notes", json={"title": "B", "tags": ["python", "fastapi"], "content": "B"})

    resp = client.get("/api/v1/taxonomy")
    assert resp.status_code == 200
    data = resp.json()["data"]
    tags = data["tags"]
    assert "python" in tags
    assert "web" in tags
    assert "fastapi" in tags


def test_get_categories(client):
    """GET /api/v1/taxonomy returns categories."""
    client.post("/api/v1/notes", json={"title": "A", "category": "tech", "content": "A"})
    client.post("/api/v1/notes", json={"title": "B", "category": "life", "content": "B"})

    resp = client.get("/api/v1/taxonomy")
    assert resp.status_code == 200
    data = resp.json()["data"]
    cat_names = [c["name"] for c in data["categories"]]
    assert "tech" in cat_names
    assert "life" in cat_names


def test_get_index_status(client):
    """GET /api/v1/dashboard returns notes count via index_health."""
    client.post("/api/v1/notes", json={"title": "A", "content": "a"})
    client.post("/api/v1/notes", json={"title": "B", "content": "b"})

    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["notes_count"] == 2


def test_trigger_index(client):
    """POST /api/v1/index/rebuild re-indexes notes and returns count."""
    client.post("/api/v1/notes", json={"title": "X", "content": "hello"})
    client.post("/api/v1/notes", json={"title": "Y", "content": "world"})

    resp = client.post("/api/v1/index/rebuild")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["indexed"] >= 2


def test_upload_attachment(client):
    """POST /api/v1/attachments uploads a file and returns its path."""
    from io import BytesIO

    resp = client.post(
        "/api/v1/attachments",
        files={"file": ("test.txt", BytesIO(b"hello world"), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "path" in data
    assert data["path"].startswith("attachments/")
    assert data["path"].endswith(".txt")


def test_v1_routes_use_configured_vault_subpaths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """V1 create, rebuild, upload use configured vault paths."""
    from io import BytesIO

    index_calls: list[dict] = []

    def fake_index_files(vault, db, **kwargs):
        index_calls.append(kwargs)
        return 1, 0

    monkeypatch.setattr("kb.core.indexer.index_files", fake_index_files)
    monkeypatch.setattr("kb.api.v1.index_files", fake_index_files)
    config = KBConfig(
        vault_path=tmp_path.resolve(),
        general=GeneralConfig(
            notes_dir="knowledge",
            attachments_dir="media",
            index_dir="state/index",
        ),
        embedding=None,
        llm=None,
        server=ServerConfig(host="127.0.0.1", port=8420),
    )
    custom_client = TestClient(create_app(config))

    created = custom_client.post("/api/v1/notes", json={
        "title": "Custom Paths",
        "content": "Body",
        "category": "tech",
    }).json()["data"]
    upload = custom_client.post(
        "/api/v1/attachments",
        files={"file": ("sample.txt", BytesIO(b"hello"), "text/plain")},
    ).json()["data"]
    rebuild = custom_client.post("/api/v1/index/rebuild")

    assert created["file_id"].startswith("knowledge/tech/")
    assert (tmp_path / created["file_id"]).is_file()
    assert upload["path"].startswith("media/")
    assert (tmp_path / upload["path"]).is_file()
    assert rebuild.status_code == 200
    assert len(index_calls) == 1


def test_semantic_search_requires_query(client):
    """GET /api/v1/search without q returns 422."""
    resp = client.get("/api/v1/search")
    assert resp.status_code == 422


def test_semantic_search_empty_store(client):
    """GET /api/v1/search?mode=semantic with empty vector store returns empty list."""
    resp = client.get("/api/v1/search", params={"q": "测试查询", "mode": "semantic"})
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_semantic_search_finds_similar(client):
    """Semantic search returns notes after vectors are populated."""
    from kb.data.vector import VectorStore, VectorRecord
    from kb.data.embedding import LocalEmbeddingProvider

    resp1 = client.post("/api/v1/notes", json={
        "title": "Python Async", "content": "asyncio 协程并发编程",
    })
    resp2 = client.post("/api/v1/notes", json={
        "title": "Unrelated", "content": "今天天气很好适合散步",
    })
    fid1 = resp1.json()["data"]["file_id"]
    fid2 = resp2.json()["data"]["file_id"]

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

    resp = client.get("/api/v1/search", params={"q": "异步编程", "mode": "semantic", "limit": "5"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert any("Python" in r["note"]["title"] for r in data)


def test_get_note_path_traversal_blocked(client):
    """GET /api/v1/notes/../outside returns 403."""
    resp = client.get("/api/v1/notes/%2e%2e%2foutside")
    assert resp.status_code == 403


def test_get_note_not_found_body(client):
    """GET /api/v1/notes/nonexistent-note returns 404 with error envelope."""
    resp = client.get("/api/v1/notes/nonexistent-note")
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["error"] is not None


def test_update_note_path_traversal_blocked(client):
    """PUT /api/v1/notes/../outside with json body returns 403."""
    resp = client.put(
        "/api/v1/notes/%2e%2e%2foutside",
        json={"title": "evil"},
    )
    assert resp.status_code == 403


def test_delete_note_path_traversal_blocked(client):
    """DELETE /api/v1/notes/../outside returns 403."""
    resp = client.delete("/api/v1/notes/%2e%2e%2foutside")
    assert resp.status_code == 403


def test_search_mode_validation(client):
    """GET /api/v1/search?q=test&mode=fulltext returns 200, data is list."""
    client.post("/api/v1/notes", json={"title": "Test", "content": "Some content"})
    resp = client.get("/api/v1/search", params={"q": "test", "mode": "fulltext"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_semantic_search_empty_results(client):
    """GET /api/v1/search?q=xyzabc123&mode=fulltext returns 200, data is list."""
    resp = client.get("/api/v1/search", params={"q": "xyzabc123", "mode": "fulltext"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_tags_endpoint(client):
    """GET /api/v1/taxonomy returns 200, data has 'tags' key."""
    resp = client.get("/api/v1/taxonomy")
    assert resp.status_code == 200
    assert "tags" in resp.json()["data"]
    assert isinstance(resp.json()["data"]["tags"], list)


def test_categories_endpoint(client):
    """GET /api/v1/taxonomy returns 200, data has 'categories' key."""
    resp = client.get("/api/v1/taxonomy")
    assert resp.status_code == 200
    assert "categories" in resp.json()["data"]
    assert isinstance(resp.json()["data"]["categories"], list)


def test_index_status_endpoint(client):
    """GET /api/v1/dashboard returns 200, data has 'notes_count' key."""
    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    assert "notes_count" in resp.json()["data"]


def test_trigger_index_endpoint(client):
    """POST /api/v1/index/rebuild returns 200, data has 'indexed' and 'vectors' keys."""
    client.post("/api/v1/notes", json={"title": "X", "content": "hello"})
    resp = client.post("/api/v1/index/rebuild")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "indexed" in data
    assert "vectors" in data


def test_list_notes_default(client):
    """GET /api/v1/notes returns 200, data is list."""
    resp = client.get("/api/v1/notes")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_list_notes_by_tag(client):
    """GET /api/v1/notes?tag=python returns 200, data is list."""
    client.post("/api/v1/notes", json={"title": "Note P", "tags": ["python"], "content": "x"})
    resp = client.get("/api/v1/notes", params={"tag": "python"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert all("python" in n.get("tags", []) for n in data)


def test_list_notes_by_category(client):
    """GET /api/v1/notes?category=tech returns 200, data is list."""
    client.post("/api/v1/notes", json={"title": "Note C", "category": "tech", "content": "x"})
    resp = client.get("/api/v1/notes", params={"category": "tech"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert all(n.get("category") == "tech" for n in data)
