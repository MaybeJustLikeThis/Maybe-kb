# Knowledge Import Indexing Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reliable ingest and indexing foundation for document/image import by preserving complete note metadata, keeping vector indexes in sync after writes, returning RAG sources, and making MCP basic tools start without embedding/LLM dependencies.

**Architecture:** This plan implements Phase 1 only from `docs/superpowers/specs/2026-06-02-knowledge-import-indexing-design.md`. It keeps `ingest()` as the single note creation path, extends the existing `indexer.py` with single-note vector updates, wraps RAG answers with traceable sources, and changes MCP provider usage to lazy initialization so keyword search/read remain available even when semantic providers are unavailable.

**Tech Stack:** Python 3.11+, dataclasses, Typer, FastAPI, FastMCP, SQLite FTS5, LanceDB, pytest.

---

## Scope Check

The design spec covers three phases:

- Phase 1: reliable ingest metadata, single-note vector indexing, RAG sources, MCP lightweight startup.
- Phase 2: import service/API/CLI for PDF/DOCX/images.
- Phase 3: Web import UI, import status display, richer MCP import tools, OCR/caption.

This implementation plan intentionally covers Phase 1 only. Phase 2 and Phase 3 need separate plans after Phase 1 passes because they touch independent API/CLI/Web flows.

## File Structure

Phase 1 will touch these files:

- `src/kb/core/models.py`
  - Extend `IngestRequest` with metadata needed by imported documents and images.
- `src/kb/core/ingest.py`
  - Pass complete metadata through the ingest pipeline.
- `src/kb/core/services.py`
  - Let `create_note()` write attachments and parser metadata through `Note.extra_frontmatter`.
- `src/kb/data/database.py`
  - Add `get_attachments()` so RAG/source serializers can read attachment paths from the DB.
- `src/kb/core/indexer.py`
  - Add single-note vector indexing and reuse it from batch indexing.
- `src/kb/core/context.py`
  - Add lazy `ensure_embedding()` and `ensure_llm()` helpers.
- `src/kb/core/rag.py`
  - Introduce `RAGSource` and `RAGResponse`, build sources from search results, and return sources from `rag_query()`.
- `src/kb/api/v1.py`
  - Preserve create metadata and return sources from `/chat/ask`.
- `src/kb/routes.py`
  - Preserve create metadata for the legacy API.
- `src/kb/mcp_server.py`
  - Start without providers, lazily load providers for semantic/RAG tools, return sources, and best-effort index saved notes.
- `tests/test_models.py`
  - Assert new `IngestRequest` defaults.
- `tests/test_ingest.py`
  - Assert complete metadata persists through ingest.
- `tests/test_indexer.py`
  - Assert single-note vector indexing upserts, replaces, deletes, and is reused by batch indexing.
- `tests/test_rag.py`
  - Assert RAG sources are built and returned.
- `tests/test_api_v1.py`
  - Assert `/api/v1/notes` preserves `source_path` and `content_type`, and `/chat/ask` returns sources.
- `tests/test_mcp_save.py`
  - Assert MCP save preserves new metadata and returns index status.
- `tests/test_mcp_light_startup.py`
  - New tests for MCP keyword search/read without provider initialization.

## Task 1: Preserve Complete Ingest Metadata

**Files:**
- Modify: `src/kb/core/models.py`
- Modify: `src/kb/core/ingest.py`
- Modify: `src/kb/core/services.py`
- Modify: `src/kb/api/v1.py`
- Modify: `src/kb/routes.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_ingest.py`
- Modify: `tests/test_api_v1.py`

- [ ] **Step 1: Write failing model tests for new IngestRequest fields**

Append to `tests/test_models.py`:

```python
def test_ingest_request_metadata_defaults():
    """Import-related metadata defaults are safe empty values."""
    req = IngestRequest(title="T", content="C", source_project="upload")

    assert req.source_path is None
    assert req.content_type == "markdown"
    assert req.attachments == []
    assert req.extra_frontmatter == {}


def test_ingest_request_accepts_import_metadata():
    """IngestRequest carries source and parser metadata end to end."""
    req = IngestRequest(
        title="Imported PDF",
        content="Converted markdown",
        source_project="upload",
        source_path="attachments/2026/06/abc123.pdf",
        content_type="pdf",
        attachments=["attachments/2026/06/abc123.pdf"],
        extra_frontmatter={
            "parser": {
                "name": "markitdown",
                "status": "success",
            },
        },
    )

    assert req.source_path == "attachments/2026/06/abc123.pdf"
    assert req.content_type == "pdf"
    assert req.attachments == ["attachments/2026/06/abc123.pdf"]
    assert req.extra_frontmatter["parser"]["name"] == "markitdown"
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
pytest tests/test_models.py::test_ingest_request_metadata_defaults tests/test_models.py::test_ingest_request_accepts_import_metadata -v
```

Expected: FAIL with `AttributeError` or `TypeError` because `IngestRequest` does not define these fields yet.

- [ ] **Step 3: Extend IngestRequest**

In `src/kb/core/models.py`, update `IngestRequest` to:

```python
@dataclass(frozen=True)
class IngestRequest:
    """Unified input for the note ingest pipeline.

    All entry points (CLI, MCP, API, indexer) assemble this and pass it
    to ingest(). source_project determines which SourceConfig is used for
    default values.
    """

    title: str
    content: str
    source_project: str
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    description: str | None = None
    source_path: str | None = None
    source_context: str | None = None
    content_type: str = "markdown"
    attachments: list[str] = field(default_factory=list)
    extra_frontmatter: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run model tests to verify they pass**

Run:

```bash
pytest tests/test_models.py::test_ingest_request_metadata_defaults tests/test_models.py::test_ingest_request_accepts_import_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Write failing ingest metadata persistence test**

Append to `tests/test_ingest.py`:

```python
def test_ingest_persists_import_metadata(tmp_path: Path, db: Database):
    """ingest() writes source, content type, attachments, and parser metadata."""
    req = IngestRequest(
        title="Imported PDF",
        content="# Imported PDF\n\nConverted body",
        source_project="upload",
        source_path="attachments/2026/06/abc123.pdf",
        source_context="user upload",
        content_type="pdf",
        attachments=["attachments/2026/06/abc123.pdf"],
        extra_frontmatter={
            "parser": {
                "name": "markitdown",
                "status": "success",
            },
        },
        category="document",
        tags=["imported"],
    )

    note = ingest(req, tmp_path, db)

    assert note.source_path == "attachments/2026/06/abc123.pdf"
    assert note.source_context == "user upload"
    assert note.content_type == "pdf"
    assert note.attachments == ["attachments/2026/06/abc123.pdf"]
    assert note.extra_frontmatter["parser"]["name"] == "markitdown"

    row = db.get_note(note.file_id)
    assert row is not None
    assert row["source_path"] == "attachments/2026/06/abc123.pdf"
    assert row["content_type"] == "pdf"
    assert db.get_attachments(note.file_id) == ["attachments/2026/06/abc123.pdf"]

    text = (tmp_path / note.file_id).read_text(encoding="utf-8")
    assert "source_path: attachments/2026/06/abc123.pdf" in text
    assert "content_type: pdf" in text
    assert "attachments:" in text
    assert "parser:" in text
    assert "name: markitdown" in text
```

- [ ] **Step 6: Run ingest metadata test to verify it fails**

Run:

```bash
pytest tests/test_ingest.py::test_ingest_persists_import_metadata -v
```

Expected: FAIL because `Database.get_attachments()` does not exist and ingest does not pass metadata through.

- [ ] **Step 7: Add Database.get_attachments()**

In `src/kb/data/database.py`, add this method after `get_tags()`:

```python
    def get_attachments(self, file_id: str) -> list[str]:
        """Get attachment paths for a note."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT attachment_path FROM note_attachments WHERE note_id = ? "
            "ORDER BY attachment_path",
            (file_id,),
        ).fetchall()
        return [r["attachment_path"] for r in rows]
```

- [ ] **Step 8: Extend services.create_note()**

In `src/kb/core/services.py`, update the signature:

```python
def create_note(
    vault_path: Path,
    db: Database,
    title: str,
    content: str,
    category: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
    source_project: str | None = None,
    source_path: str | None = None,
    source_context: str | None = None,
    content_type: str = "markdown",
    attachments: list[str] | None = None,
    extra_frontmatter: dict | None = None,
) -> Note:
```

In the `Note(...)` constructor inside `create_note()`, add:

```python
        attachments=list(attachments) if attachments else [],
        extra_frontmatter=dict(extra_frontmatter) if extra_frontmatter else {},
```

Keep the existing `source_path` and `content_type` assignments.

- [ ] **Step 9: Pass metadata through ingest()**

In `src/kb/core/ingest.py`, update the `services.create_note()` call:

```python
    return services.create_note(
        vault_path=vault,
        db=db,
        title=request.title,
        content=request.content,
        category=category,
        tags=tags,
        description=request.description,
        source_project=request.source_project,
        source_path=request.source_path,
        source_context=request.source_context,
        content_type=request.content_type,
        attachments=request.attachments,
        extra_frontmatter=request.extra_frontmatter,
    )
```

- [ ] **Step 10: Preserve metadata in /api/v1 note creation**

In `src/kb/api/v1.py`, update the `IngestRequest(...)` in `create_note()`:

```python
                IngestRequest(
                    title=body.title,
                    content=body.content,
                    source_project=body.source_project or "manual",
                    tags=body.tags,
                    category=body.category,
                    description=body.description,
                    source_path=body.source_path,
                    source_context=body.source_context,
                    content_type=body.content_type,
                ),
```

- [ ] **Step 11: Preserve metadata in legacy /api note creation**

In `src/kb/routes.py`, update the legacy `IngestRequest(...)` in `create_note()` to include:

```python
                    source_path=body.source_path,
                    source_context=body.source_context,
                    content_type=body.content_type,
```

- [ ] **Step 12: Add API metadata persistence assertion**

In `tests/test_api_v1.py`, add this test near the other create tests:

```python
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
```

- [ ] **Step 13: Run focused metadata tests**

Run:

```bash
pytest tests/test_models.py tests/test_ingest.py::test_ingest_persists_import_metadata tests/test_api_v1.py::test_v1_create_note_preserves_import_metadata -v
```

Expected: PASS.

- [ ] **Step 14: Commit metadata work**

Run:

```bash
git add src/kb/core/models.py src/kb/core/ingest.py src/kb/core/services.py src/kb/data/database.py src/kb/api/v1.py src/kb/routes.py tests/test_models.py tests/test_ingest.py tests/test_api_v1.py
git commit -m "feat: preserve ingest import metadata"
```

## Task 2: Add Single-Note Vector Indexing

**Files:**
- Modify: `src/kb/core/indexer.py`
- Modify: `tests/test_indexer.py`

- [ ] **Step 1: Write fake embedding/vector helpers in indexer tests**

Append to `tests/test_indexer.py`:

```python
from kb.data.embedding import EmbeddingProvider, EmbeddingResult


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for indexer tests."""

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=[float(len(text)), 1.0, 0.0],
            dimension=3,
            tokens_used=len(text),
        )

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        return 3


class FakeVectorStore:
    """In-memory stand-in for VectorStore."""

    def __init__(self) -> None:
        self.records: dict[str, list[VectorRecord]] = {}
        self.deleted: list[str] = []
        self.closed = False

    def upsert_chunks(self, file_id: str, chunks: list[VectorRecord]) -> None:
        self.records[file_id] = list(chunks)

    def delete_note(self, file_id: str) -> None:
        self.deleted.append(file_id)
        self.records.pop(file_id, None)

    def close(self) -> None:
        self.closed = True
```

- [ ] **Step 2: Write failing tests for single-note vector indexing**

Append to `tests/test_indexer.py`:

```python
def test_index_note_vectors_upserts_single_note(db: Database, tmp_path: Path):
    """index_note_vectors embeds one DB note and upserts its chunks."""
    from kb.core.indexer import index_note_vectors

    db.initialize()
    db.upsert_note(Note(
        file_id="notes/a.md",
        title="A",
        content="first paragraph\n\nsecond paragraph",
    ))
    store = FakeVectorStore()

    count = index_note_vectors(
        tmp_path,
        db,
        FakeEmbeddingProvider(),
        "notes/a.md",
        vector_store=store,
    )

    assert count >= 1
    assert "notes/a.md" in store.records
    assert store.records["notes/a.md"][0].id == "notes/a.md"
    assert store.records["notes/a.md"][0].text
    assert store.closed is False


def test_index_note_vectors_deletes_missing_note(db: Database, tmp_path: Path):
    """Missing DB rows delete stale vector chunks for that note."""
    from kb.core.indexer import index_note_vectors

    db.initialize()
    store = FakeVectorStore()
    store.records["notes/missing.md"] = [
        VectorRecord(
            id="notes/missing.md",
            chunk_id=0,
            vector=[1.0],
            text="old",
        )
    ]

    count = index_note_vectors(
        tmp_path,
        db,
        FakeEmbeddingProvider(),
        "notes/missing.md",
        vector_store=store,
    )

    assert count == 0
    assert "notes/missing.md" in store.deleted
    assert "notes/missing.md" not in store.records


def test_index_note_vectors_deletes_empty_content(db: Database, tmp_path: Path):
    """Empty note content removes vector chunks instead of leaving stale records."""
    from kb.core.indexer import index_note_vectors

    db.initialize()
    db.upsert_note(Note(file_id="notes/empty.md", title="Empty", content=""))
    store = FakeVectorStore()
    store.records["notes/empty.md"] = [
        VectorRecord(id="notes/empty.md", chunk_id=0, vector=[1.0], text="old")
    ]

    count = index_note_vectors(
        tmp_path,
        db,
        FakeEmbeddingProvider(),
        "notes/empty.md",
        vector_store=store,
    )

    assert count == 0
    assert "notes/empty.md" in store.deleted
```

- [ ] **Step 3: Run single-note index tests to verify they fail**

Run:

```bash
pytest tests/test_indexer.py::test_index_note_vectors_upserts_single_note tests/test_indexer.py::test_index_note_vectors_deletes_missing_note tests/test_indexer.py::test_index_note_vectors_deletes_empty_content -v
```

Expected: FAIL with `ImportError` because `index_note_vectors` does not exist.

- [ ] **Step 4: Implement index_note_vectors()**

In `src/kb/core/indexer.py`, add this function before `index_vectors()`:

```python
def index_note_vectors(
    vault: Path,
    db: Database,
    provider: EmbeddingProvider,
    file_id: str,
    *,
    vector_store: VectorStore | None = None,
) -> int:
    """Generate embeddings for one note and upsert LanceDB chunks.

    If the note no longer exists or has empty content, stale vector chunks
    are deleted and 0 is returned.
    """
    owns_store = vector_store is None
    store = vector_store or VectorStore(vault / ".kb" / "vectors.lance")

    try:
        row = db.get_note(file_id)
        if row is None:
            store.delete_note(file_id)
            return 0

        content = row["content"] or ""
        chunks = chunk_text(content)
        if not chunks:
            store.delete_note(file_id)
            return 0

        embed_results = provider.embed_batch(chunks)
        records = [
            VectorRecord(
                id=file_id,
                chunk_id=i,
                vector=result.vector,
                text=chunks[i],
            )
            for i, result in enumerate(embed_results)
        ]
        store.upsert_chunks(file_id, records)
        return len(records)
    finally:
        if owns_store:
            store.close()
```

- [ ] **Step 5: Refactor index_vectors() to reuse index_note_vectors()**

Replace the body of `index_vectors()` after `indexed = 0` with:

```python
    store = VectorStore(vault / ".kb" / "vectors.lance")
    indexed = 0

    try:
        for file_id in changed_ids:
            indexed += index_note_vectors(
                vault,
                db,
                provider,
                file_id,
                vector_store=store,
            )
    finally:
        store.close()

    return indexed
```

- [ ] **Step 6: Run focused indexer tests**

Run:

```bash
pytest tests/test_indexer.py::test_index_note_vectors_upserts_single_note tests/test_indexer.py::test_index_note_vectors_deletes_missing_note tests/test_indexer.py::test_index_note_vectors_deletes_empty_content tests/test_indexer.py::test_index_vectors_empty_changed_ids -v
```

Expected: PASS.

- [ ] **Step 7: Commit single-note indexing**

Run:

```bash
git add src/kb/core/indexer.py tests/test_indexer.py
git commit -m "feat: add single note vector indexing"
```

## Task 3: Update API Write Paths to Keep Vector Indexes in Sync

**Files:**
- Modify: `src/kb/api/v1.py`
- Modify: `tests/test_api_v1.py`

- [ ] **Step 1: Write failing API test for indexing after create**

Append to `tests/test_api_v1.py`:

```python
def test_v1_create_note_updates_vector_index(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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
```

- [ ] **Step 2: Write failing API test for indexing after update**

Append to `tests/test_api_v1.py`:

```python
def test_v1_update_note_updates_vector_index(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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
```

- [ ] **Step 3: Run API indexing tests to verify they fail**

Run:

```bash
pytest tests/test_api_v1.py::test_v1_create_note_updates_vector_index tests/test_api_v1.py::test_v1_update_note_updates_vector_index -v
```

Expected: FAIL because `kb.api.v1.index_note_vectors` is not imported or called.

- [ ] **Step 4: Import and call index_note_vectors in API create/update**

In `src/kb/api/v1.py`, change the indexer import:

```python
from kb.core.indexer import index_files, index_note_vectors
```

Add this helper inside `create_v1_router()` before the route definitions:

```python
    def _index_note_if_possible(file_id: str) -> int:
        if ctx.embedding is None:
            return 0
        return index_note_vectors(
            ctx.vault,
            ctx.db,
            ctx.embedding,
            file_id,
            vector_store=ctx.vector_store,
        )
```

In `create_note()`, after `note = ingest(...)` and before returning:

```python
            _index_note_if_possible(note.file_id)
```

In `update_note()`, after `note = services.update_note(...)` and before returning:

```python
            _index_note_if_possible(note.file_id)
```

- [ ] **Step 5: Run focused API write-path tests**

Run:

```bash
pytest tests/test_api_v1.py::test_v1_create_note_updates_vector_index tests/test_api_v1.py::test_v1_update_note_updates_vector_index -v
```

Expected: PASS.

- [ ] **Step 6: Commit API write-path indexing**

Run:

```bash
git add src/kb/api/v1.py tests/test_api_v1.py
git commit -m "feat: index api note writes"
```

## Task 4: Return Traceable RAG Sources

**Files:**
- Modify: `src/kb/core/rag.py`
- Modify: `src/kb/api/v1.py`
- Modify: `tests/test_rag.py`
- Modify: `tests/test_api_v1.py`

- [ ] **Step 1: Write failing source-building test**

Append to `tests/test_rag.py`:

```python
def test_build_rag_sources_includes_note_metadata(tmp_path):
    """RAG sources expose note identity, snippet, source, and attachments."""
    from kb.core.rag import build_rag_sources
    from kb.data.database import Database

    db = Database(tmp_path / ".kb" / "test.db")
    db.initialize()
    db.upsert_note(Note(
        file_id="notes/doc/imported.md",
        title="Imported Doc",
        content="Important imported content for the user.",
        source_project="upload",
        source_path="attachments/2026/06/doc.pdf",
        content_type="pdf",
        attachments=["attachments/2026/06/doc.pdf"],
    ))
    result = SearchResult(
        file_id="notes/doc/imported.md",
        title="Imported Doc",
        score=0.5,
        source="hybrid",
    )

    sources = build_rag_sources([result], db, snippet_chars=12)

    assert len(sources) == 1
    source = sources[0]
    assert source.file_id == "notes/doc/imported.md"
    assert source.title == "Imported Doc"
    assert source.snippet == "Important im..."
    assert source.source_project == "upload"
    assert source.source_path == "attachments/2026/06/doc.pdf"
    assert source.content_type == "pdf"
    assert source.attachments == ["attachments/2026/06/doc.pdf"]
```

- [ ] **Step 2: Write failing rag_query response test**

Append to `tests/test_rag.py`:

```python
def test_rag_query_returns_sources(tmp_path):
    """rag_query returns answer metadata plus traceable sources."""
    from kb.core.rag import RAGResponse, rag_query
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult
    from kb.data.vector import VectorRecord

    db = Database(tmp_path / ".kb" / "rag.db")
    db.initialize()
    db.upsert_note(Note(
        file_id="notes/a.md",
        title="Source A",
        content="Pinia store setup notes",
        tags=["pinia"],
        attachments=["attachments/a.png"],
    ))

    class MockLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="Mocked answer", tokens_used=10, model="mock")

        @property
        def model_name(self):
            return "mock"

    class MockEmbedding(EmbeddingProvider):
        def embed(self, text):
            return EmbeddingResult(vector=[0.1, 0.2, 0.3], dimension=3, tokens_used=0)

        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

        @property
        def dimension(self):
            return 3

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return [
                VectorRecord(
                    id="notes/a.md",
                    chunk_id=0,
                    vector=[0.1, 0.2, 0.3],
                    text="Pinia store setup notes",
                )
            ]

    response = rag_query(
        "Pinia",
        db,
        MockEmbedding(),
        MockVectorStore(),
        MockLLM(),
        top_k=3,
    )

    assert isinstance(response, RAGResponse)
    assert response.text == "Mocked answer"
    assert response.sources[0].file_id == "notes/a.md"
    assert response.sources[0].attachments == ["attachments/a.png"]
```

- [ ] **Step 3: Run RAG source tests to verify they fail**

Run:

```bash
pytest tests/test_rag.py::test_build_rag_sources_includes_note_metadata tests/test_rag.py::test_rag_query_returns_sources -v
```

Expected: FAIL because `RAGResponse` and `build_rag_sources` do not exist.

- [ ] **Step 4: Add RAGSource and RAGResponse dataclasses**

In `src/kb/core/rag.py`, add imports:

```python
from dataclasses import dataclass, field
```

Then add after `RAG_SYSTEM_PROMPT`:

```python
@dataclass(frozen=True)
class RAGSource:
    """Traceable source returned with a RAG answer."""

    file_id: str
    title: str
    snippet: str
    source_project: str | None = None
    source_path: str | None = None
    content_type: str = "markdown"
    attachments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RAGResponse:
    """LLM answer plus traceable knowledge-base sources."""

    text: str
    tokens_used: int
    model: str
    sources: list[RAGSource] = field(default_factory=list)
```

- [ ] **Step 5: Add source builder and serializer**

In `src/kb/core/rag.py`, add:

```python
def _snippet(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_rag_sources(
    results: list[SearchResult],
    db: Database,
    snippet_chars: int = 240,
) -> list[RAGSource]:
    """Build traceable source metadata for RAG responses."""
    sources: list[RAGSource] = []
    for result in results:
        note = db.get_note(result.file_id)
        if note is None:
            continue
        content = note["content"] or ""
        sources.append(RAGSource(
            file_id=note["id"],
            title=note["title"],
            snippet=_snippet(content, snippet_chars),
            source_project=note["source_project"],
            source_path=note["source_path"],
            content_type=note["content_type"] or "markdown",
            attachments=db.get_attachments(note["id"]),
        ))
    return sources


def rag_source_to_dict(source: RAGSource) -> dict:
    """Convert RAGSource to an API/MCP-ready dict."""
    return {
        "file_id": source.file_id,
        "title": source.title,
        "snippet": source.snippet,
        "source_project": source.source_project,
        "source_path": source.source_path,
        "content_type": source.content_type,
        "attachments": source.attachments,
    }
```

- [ ] **Step 6: Return RAGResponse from rag_query()**

In `src/kb/core/rag.py`, replace `rag_query()` with:

```python
def rag_query(
    query: str,
    db: Database,
    embed_provider: EmbeddingProvider,
    store: VectorStore,
    llm: LLMProvider,
    top_k: int = 5,
) -> RAGResponse:
    """Run a full RAG query: hybrid search -> format -> generate."""
    results = hybrid_search(query, db, embed_provider, store, limit=top_k)
    context = format_context(results, db)
    prompt = build_rag_prompt(query, context)
    answer = llm.generate(prompt, system_prompt=RAG_SYSTEM_PROMPT)
    return RAGResponse(
        text=answer.text,
        tokens_used=answer.tokens_used,
        model=answer.model,
        sources=build_rag_sources(results, db),
    )
```

Leave `rag_query_stream()` unchanged in Phase 1.

- [ ] **Step 7: Update existing RAG tests for RAGResponse**

In `tests/test_rag.py`, update `test_rag_query_returns_llm_response()`:

```python
def test_rag_query_returns_llm_response():
    """Verify rag_query signature and orchestration pattern with mocks."""
    from kb.core.rag import RAGResponse, rag_query
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult

    class MockLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="Mocked answer", tokens_used=10, model="mock")

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

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return []

        def close(self):
            pass

    db = Database(Path("/tmp/rag-test.db"))
    db.initialize()

    response = rag_query("test", db, MockEmbedding(), MockVectorStore(), MockLLM(), top_k=3)

    assert isinstance(response, RAGResponse)
    assert response.text == "Mocked answer"
    assert response.sources == []
```

- [ ] **Step 8: Update /api/v1/chat/ask sources response**

In `src/kb/api/v1.py`, import `rag_source_to_dict`:

```python
from kb.core.rag import rag_query, rag_query_stream, rag_source_to_dict
```

In `chat_ask()`, change `"sources": []` to:

```python
            "sources": [
                rag_source_to_dict(source)
                for source in response.sources
            ],
```

- [ ] **Step 9: Add API chat sources test**

Append to `tests/test_api_v1.py`:

```python
def test_v1_chat_ask_returns_sources(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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
```

- [ ] **Step 10: Run RAG and API source tests**

Run:

```bash
pytest tests/test_rag.py tests/test_api_v1.py::test_v1_chat_ask_returns_sources -v
```

Expected: PASS.

- [ ] **Step 11: Commit RAG sources**

Run:

```bash
git add src/kb/core/rag.py src/kb/api/v1.py tests/test_rag.py tests/test_api_v1.py
git commit -m "feat: return sources from rag queries"
```

## Task 5: Make MCP Basic Tools Work Without Provider Startup

**Files:**
- Modify: `src/kb/core/context.py`
- Modify: `src/kb/mcp_server.py`
- Create: `tests/test_mcp_light_startup.py`
- Modify: `tests/test_mcp_save.py`

- [ ] **Step 1: Write failing MCP light startup test**

Create `tests/test_mcp_light_startup.py`:

```python
"""Tests for MCP startup without semantic provider initialization."""
from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from kb.core.config import KBConfig, EmbeddingConfig, LLMConfig
from kb.core.models import Note
from kb.data.database import Database


def _prepare_vault(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()
    db = Database(tmp_path / ".kb" / "kb.db")
    db.initialize()
    db.upsert_note(Note(
        file_id="notes/a.md",
        title="Local Search Note",
        content="keyword-only content",
        tags=["keyword"],
    ))
    db.close()


def test_mcp_creation_does_not_initialize_embedding_or_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """MCP keyword tools start even when embedding and LLM factories fail."""
    _prepare_vault(tmp_path)

    def fail_embedding(config):
        raise RuntimeError("embedding factory should not run at startup")

    def fail_llm(config):
        raise RuntimeError("llm factory should not run at startup")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", fail_llm)

    from kb.mcp_server import create_mcp_server

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
    )
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_search", {
            "query": "keyword",
            "limit": 5,
        })
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "Local Search Note" in data

    anyio.run(_run)
```

- [ ] **Step 2: Run MCP light startup test to verify it fails**

Run:

```bash
pytest tests/test_mcp_light_startup.py::test_mcp_creation_does_not_initialize_embedding_or_llm -v
```

Expected: FAIL because `create_mcp_server()` currently initializes providers through `AppContext.from_config(config)`.

- [ ] **Step 3: Add lazy provider helpers to AppContext**

In `src/kb/core/context.py`, add these methods before `close()`:

```python
    def ensure_embedding(self) -> EmbeddingProvider | None:
        """Initialize embedding provider on demand."""
        if self.embedding is not None:
            return self.embedding
        if self.config is None or self.config.embedding is None:
            return None
        self.embedding = create_embedding_provider(self.config.embedding)
        return self.embedding

    def ensure_llm(self) -> LLMProvider | None:
        """Initialize LLM provider on demand."""
        if self.llm is not None:
            return self.llm
        if self.config is None or self.config.llm is None:
            return None
        self.llm = create_llm_provider(self.config.llm)
        return self.llm
```

- [ ] **Step 4: Start MCP without providers**

In `src/kb/mcp_server.py`, change:

```python
    ctx = AppContext.from_config(config)
```

to:

```python
    ctx = AppContext.from_config(
        config,
        with_embedding=False,
        with_llm=False,
    )
```

Remove these closed-over variables:

```python
    provider = ctx.embedding
    llm = ctx.llm
    store = ctx.vector_store
```

- [ ] **Step 5: Lazily load providers in semantic, hybrid, and RAG tools**

In `kb_semantic_search()`, start with:

```python
        provider = ctx.ensure_embedding()
        if provider is None:
            return [{"error": "embedding provider is not configured"}]
        store = ctx.vector_store
```

In `kb_hybrid_search()`, start with:

```python
        provider = ctx.ensure_embedding()
        if provider is None:
            return [{"error": "embedding provider is not configured"}]
        store = ctx.vector_store
```

In `kb_rag_query()`, replace the call body with:

```python
        from kb.core.rag import rag_source_to_dict

        provider = ctx.ensure_embedding()
        llm = ctx.ensure_llm()
        if provider is None or llm is None:
            return {"error": "LLM and embedding config required"}
        response = rag_query(
            query,
            db,
            provider,
            ctx.vector_store,
            llm,
            top_k=top_k,
        )
        return {
            "answer": response.text,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "sources": [
                rag_source_to_dict(source)
                for source in response.sources
            ],
        }
```

- [ ] **Step 6: Write failing MCP save indexing test**

Append to `tests/test_mcp_save.py`:

```python
def test_kb_save_returns_indexed_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """kb_save best-effort indexes the created note and returns vector count."""
    _prepare_vault(tmp_path, monkeypatch)

    from kb.data.embedding import EmbeddingResult

    class FakeEmbedding:
        def embed(self, text):
            return EmbeddingResult(vector=[1.0, 0.0, 0.0], dimension=3, tokens_used=len(text))

        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

        @property
        def dimension(self):
            return 3

    calls: list[str] = []

    def fake_ensure_embedding(self):
        return FakeEmbedding()

    def fake_index_note_vectors(vault, db, provider, file_id, *, vector_store=None):
        calls.append(file_id)
        return 1

    monkeypatch.setattr("kb.core.context.AppContext.ensure_embedding", fake_ensure_embedding)
    monkeypatch.setattr("kb.mcp_server.index_note_vectors", fake_index_note_vectors)

    config = KBConfig(vault_path=tmp_path.resolve())
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_save", {
            "title": "Indexed MCP Save",
            "content": "Body to index",
            "source_project": "agent",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        import json as _json
        payload = _json.loads(data)
        assert payload["indexed_vectors"] == 1
        assert calls == [payload["file_id"]]

    anyio.run(_run)
```

- [ ] **Step 7: Run MCP save indexing test to verify it fails**

Run:

```bash
pytest tests/test_mcp_save.py::test_kb_save_returns_indexed_count -v
```

Expected: FAIL because `kb_save` does not call `index_note_vectors` or return `indexed_vectors`.

- [ ] **Step 8: Import index_note_vectors in MCP server**

In `src/kb/mcp_server.py`, add:

```python
from kb.core.indexer import index_note_vectors
```

- [ ] **Step 9: Add best-effort note indexing helper in create_mcp_server()**

Inside `create_mcp_server()`, after `_blank_to_none()`, add:

```python
    def _index_note_if_possible(file_id: str) -> tuple[int, str | None]:
        try:
            provider = ctx.ensure_embedding()
            if provider is None:
                return 0, "embedding provider is not configured"
            count = index_note_vectors(
                vault,
                db,
                provider,
                file_id,
                vector_store=ctx.vector_store,
            )
            return count, None
        except Exception as exc:
            return 0, str(exc)
```

- [ ] **Step 10: Return index metadata from kb_add and kb_save**

In `kb_add()`, before the return dict:

```python
        indexed_vectors, index_error = _index_note_if_possible(note.file_id)
```

Add to the returned dict:

```python
            "indexed_vectors": indexed_vectors,
            "index_error": index_error,
```

In `kb_save()`, do the same.

- [ ] **Step 11: Run MCP tests**

Run:

```bash
pytest tests/test_mcp_light_startup.py tests/test_mcp_save.py -v
```

Expected: PASS.

- [ ] **Step 12: Commit MCP lazy startup**

Run:

```bash
git add src/kb/core/context.py src/kb/mcp_server.py tests/test_mcp_light_startup.py tests/test_mcp_save.py
git commit -m "feat: make mcp providers lazy"
```

## Task 6: Final Verification for Phase 1

**Files:**
- No code files should be modified in this task unless verification finds a defect.

- [ ] **Step 1: Run focused backend test set**

Run:

```bash
pytest tests/test_models.py tests/test_ingest.py tests/test_indexer.py tests/test_rag.py tests/test_api_v1.py tests/test_mcp_save.py tests/test_mcp_light_startup.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full Python test suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only intentionally untracked local files remain, such as user screenshots or temporary JSON files. No modified implementation files should remain unstaged.

- [ ] **Step 4: Resolve any verification failures through the owning task**

If Step 1 or Step 2 fails, return to the task that owns the failing behavior and add a focused regression test before changing implementation. After the focused test passes, rerun Step 1 and Step 2. Do not create an empty commit when verification passes without fixes.

## Phase 1 Completion Criteria

Phase 1 is complete only when all of these are true:

- `IngestRequest` accepts and persists source path, content type, attachments, and parser metadata.
- API note creation preserves `source_path` and `content_type`.
- Single-note vector indexing can upsert, replace, and delete chunks without a full rebuild.
- API create/update attempts immediate vector indexing when embedding is available.
- `rag_query()` returns `RAGResponse` with traceable sources.
- `/api/v1/chat/ask` returns non-empty `sources` when RAG has matches.
- MCP `kb_search` and `kb_read` can work without embedding or LLM initialization.
- MCP `kb_save` and `kb_add` return best-effort vector indexing metadata.
- Focused tests and the full suite pass.

## Handoff to Phase 2

After Phase 1 is complete, write a separate plan for Phase 2:

- `ImportRequest` and import service.
- `/api/v1/imports`.
- `kb import` and `kb attach`.
- MarkItDown/fallback parser integration.
- Image split behavior: independent note vs attach to existing note.

Do not begin Phase 2 until Phase 1 is verified and committed.
