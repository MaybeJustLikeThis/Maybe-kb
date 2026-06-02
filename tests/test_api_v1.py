"""Tests for the normalized /api/v1 contract."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kb.core.config import KBConfig, ServerConfig
from kb.server import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client with a temp kb project."""
    monkeypatch.chdir(tmp_path)
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


def assert_success_envelope(payload: dict) -> None:
    """Assert the standard v1 success envelope shape."""
    assert set(payload) == {"data", "meta", "error"}
    assert payload["error"] is None
    assert isinstance(payload["meta"], dict)


def assert_error_envelope(payload: dict, code: str) -> None:
    """Assert the standard v1 error envelope shape."""
    assert set(payload) == {"data", "meta", "error"}
    assert payload["data"] is None
    assert isinstance(payload["meta"], dict)
    assert payload["error"]["code"] == code
    assert isinstance(payload["error"]["message"], str)
    assert isinstance(payload["error"]["details"], dict)


def test_v1_list_notes_returns_success_envelope(client: TestClient) -> None:
    """GET /api/v1/notes returns an empty paginated envelope."""
    response = client.get("/api/v1/notes")

    assert response.status_code == 200
    payload = response.json()
    assert_success_envelope(payload)
    assert payload["data"] == []
    assert payload["meta"] == {"limit": 50, "offset": 0, "total": 0}


def test_api_list_notes_returns_valid_json_structure(client: TestClient) -> None:
    """GET /api/notes returns a list of note summaries."""
    client.post("/api/notes", json={"title": "Legacy API Note", "content": "Body"})

    response = client.get("/api/notes")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    note = payload[0]
    assert {"file_id", "title", "tags", "category"}.issubset(note)
    assert note["title"] == "Legacy API Note"


def test_v1_get_missing_note_returns_error_envelope(client: TestClient) -> None:
    """GET /api/v1/notes/{file_id} returns NOTE_NOT_FOUND envelope."""
    response = client.get("/api/v1/notes/missing.md")

    assert response.status_code == 404
    payload = response.json()
    assert_error_envelope(payload, "NOTE_NOT_FOUND")


def test_v1_create_get_update_delete_note(client: TestClient) -> None:
    """V1 note CRUD returns normalized envelopes."""
    create_resp = client.post("/api/v1/notes", json={
        "title": "API V1 Note",
        "content": "Hello v1",
        "category": "tech",
        "tags": ["api", "v1"],
        "source_project": "kb",
        "content_type": "markdown",
    })
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    assert_success_envelope(create_body)
    created = create_body["data"]
    assert created["title"] == "API V1 Note"
    assert created["content"].rstrip("\n") == "Hello v1"
    assert created["tags"] == ["api", "v1"]
    file_id = created["file_id"]

    get_resp = client.get(f"/api/v1/notes/{file_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()["data"]
    assert detail["file_id"] == file_id
    assert detail["content"].rstrip("\n") == "Hello v1"

    update_resp = client.put(f"/api/v1/notes/{file_id}", json={
        "title": "API V1 Note Updated",
        "content": "Updated body",
    })
    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["title"] == "API V1 Note Updated"
    assert updated["content"].rstrip("\n") == "Updated body"

    delete_resp = client.delete(f"/api/v1/notes/{file_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"] == {"ok": True}

    missing_resp = client.get(f"/api/v1/notes/{file_id}")
    assert missing_resp.status_code == 404
    assert_error_envelope(missing_resp.json(), "NOTE_NOT_FOUND")


def test_v1_create_note_preserves_import_metadata(client: TestClient) -> None:
    """POST /api/v1/notes preserves source_path and content_type."""
    response = client.post("/api/v1/notes", json={
        "title": "Imported API PDF",
        "content": "Converted body",
        "category": "document",
        "source_project": "upload",
        "source_path": "attachments/2026/06/api.pdf",
        "source_context": "api upload",
        "content_type": "pdf",
    })

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    note = body["data"]
    assert note["source_project"] == "upload"
    assert note["source_path"] == "attachments/2026/06/api.pdf"
    assert note["source_context"] == "api upload"
    assert note["content_type"] == "pdf"

    detail = client.get(f"/api/v1/notes/{note['file_id']}").json()["data"]
    assert detail["source_path"] == "attachments/2026/06/api.pdf"
    assert detail["content_type"] == "pdf"


def test_v1_path_traversal_returns_error_envelope(client: TestClient) -> None:
    """Path traversal attempts return the v1 error envelope."""
    response = client.get("/api/v1/notes/%2e%2e%2foutside")

    assert response.status_code == 403
    assert_error_envelope(response.json(), "PATH_TRAVERSAL_BLOCKED")


def test_v1_search_returns_consistent_search_results(client: TestClient) -> None:
    """Search modes return the normalized SearchResult shape."""
    client.post("/api/v1/notes", json={
        "title": "Searchable",
        "content": "Pinia and Vue API client",
        "category": "tech",
        "tags": ["vue"],
    })

    response = client.get("/api/v1/search", params={"q": "Pinia", "mode": "fulltext"})
    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["meta"]["limit"] == 20
    assert body["meta"]["offset"] == 0
    assert body["meta"]["total"] >= 1
    first = body["data"][0]
    assert set(first.keys()) == {"note", "score", "source", "chunk_text"}
    assert first["source"] == "fulltext"
    assert first["note"]["title"] == "Searchable"
    assert "content" not in first["note"]


def test_v1_taxonomy_returns_unified_taxonomy(client: TestClient) -> None:
    """Taxonomy combines tags, categories, and source dimensions."""
    client.post("/api/v1/notes", json={
        "title": "Taxonomy Note",
        "content": "Body",
        "category": "tech",
        "tags": ["python"],
        "source_project": "kb",
        "content_type": "markdown",
    })

    response = client.get("/api/v1/taxonomy")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "python" in data["tags"]
    assert data["categories"][0]["name"] == "tech"
    assert data["source_projects"][0]["name"] == "kb"
    assert data["content_types"][0]["name"] == "markdown"


def test_v1_dashboard_returns_summary(client: TestClient) -> None:
    """Dashboard returns one summary payload for dashboard widgets."""
    client.post("/api/v1/notes", json={
        "title": "Dashboard Note",
        "content": "Body",
        "source_project": "kb",
        "content_type": "markdown",
    })

    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["notes_count"] == 1
    assert "attachments_count" in data
    assert data["index_health"]["notes_count"] == 1


def test_v1_dashboard_activity_returns_empty_envelope(client: TestClient) -> None:
    """Dashboard activity returns an empty list for an empty knowledge base."""
    response = client.get("/api/v1/dashboard/activity")

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["data"] == []


def test_v1_dashboard_activity_returns_recent_notes(client: TestClient) -> None:
    """Dashboard activity is derived from recent note metadata."""
    first = client.post("/api/v1/notes", json={
        "title": "First Activity Note",
        "content": "First body",
        "category": "ops",
        "tags": ["alpha"],
        "source_project": "kb",
    }).json()["data"]
    second = client.post("/api/v1/notes", json={
        "title": "Second Activity Note",
        "content": "Second body",
        "category": "ops",
        "tags": ["beta"],
        "source_project": "kb",
    }).json()["data"]

    response = client.get("/api/v1/dashboard/activity", params={"limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["kind"] == "note_updated"
    assert item["title"] in {first["title"], second["title"]}
    assert item["description"]
    assert item["timestamp"]
    assert {"file_id", "title"}.issubset(set(item["note"]))


def test_v1_index_rebuild_returns_envelope(client: TestClient) -> None:
    """Index rebuild returns command result in the v1 envelope."""
    client.post("/api/v1/notes", json={"title": "Index Me", "content": "hello"})

    response = client.post("/api/v1/index/rebuild")
    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["data"]["indexed"] >= 1
    assert "vectors" in body["data"]


def test_v1_create_note_updates_vector_index(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating a note attempts single-note vector indexing when embedding exists."""
    calls: list[str] = []

    def fake_index_note_vectors(vault, db, provider, file_id, *, vector_store=None):
        calls.append(file_id)
        return 1

    monkeypatch.setattr("kb.api.v1.index_note_vectors", fake_index_note_vectors)

    response = client.post("/api/v1/notes", json={
        "title": "Vector Indexed",
        "content": "This body should be indexed.",
        "source_project": "manual",
    })

    assert response.status_code == 200
    note = response.json()["data"]
    assert calls == [note["file_id"]]


def test_v1_update_note_updates_vector_index(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updating a note attempts single-note vector indexing when embedding exists."""
    calls: list[str] = []

    def fake_index_note_vectors(vault, db, provider, file_id, *, vector_store=None):
        calls.append(file_id)
        return 1

    monkeypatch.setattr("kb.api.v1.index_note_vectors", fake_index_note_vectors)

    created = client.post("/api/v1/notes", json={
        "title": "Update Vector Indexed",
        "content": "Original body",
    }).json()["data"]
    calls.clear()

    response = client.put(f"/api/v1/notes/{created['file_id']}", json={
        "content": "Updated body",
    })

    assert response.status_code == 200
    assert calls == [created["file_id"]]


def test_v1_attachment_upload_returns_envelope(client: TestClient) -> None:
    """Attachment upload returns the stored relative path in the v1 envelope."""
    from io import BytesIO

    response = client.post(
        "/api/v1/attachments",
        files={"file": ("sample.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["data"]["path"].startswith("attachments/")


def test_v1_chat_without_providers_returns_error_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chat reports missing providers through the v1 error envelope."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "attachments").mkdir()
    (tmp_path / ".kb").mkdir()
    kb_config = KBConfig(
        vault_path=tmp_path.resolve(),
        server=ServerConfig(host="127.0.0.1", port=8420),
        embedding=None,
        llm=None,
    )
    client = TestClient(create_app(kb_config))

    response = client.post("/api/v1/chat/ask", json={"query": "hello"})

    assert response.status_code == 400
    assert_error_envelope(response.json(), "PROVIDER_NOT_CONFIGURED")


def test_v1_chat_ask_returns_sources(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/v1/chat/ask returns RAG sources from rag_query."""
    from kb.core.rag import RAGResponse, RAGSource

    def fake_rag_query(query, db, embed_provider, store, llm, top_k=5):
        return RAGResponse(
            text="Answer",
            tokens_used=7,
            model="mock",
            sources=[
                RAGSource(
                    file_id="notes/a.md",
                    title="A",
                    snippet="source snippet",
                    source_project="upload",
                    source_path="attachments/a.pdf",
                    content_type="pdf",
                    attachments=["attachments/a.pdf"],
                )
            ],
        )

    monkeypatch.setattr("kb.api.v1.rag_query", fake_rag_query)

    response = client.post("/api/v1/chat/ask", json={"query": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["data"]["answer"] == "Answer"
    assert body["data"]["sources"][0]["file_id"] == "notes/a.md"
    assert body["data"]["sources"][0]["attachments"] == ["attachments/a.pdf"]
