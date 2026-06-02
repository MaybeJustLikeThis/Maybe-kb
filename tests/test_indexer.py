"""Tests for SQLite indexer and index operations."""
import pytest
from pathlib import Path
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider, EmbeddingResult
from kb.data.vector import VectorRecord
from kb.core.models import Note
from kb.core.indexer import index_files, index_vectors


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


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a fresh database in tmp."""
    db_path = tmp_path / ".kb" / "kb.db"
    db_path.parent.mkdir(parents=True)
    return Database(db_path)


def test_create_tables(db: Database):
    """Tables are created without error."""
    db.initialize()
    db.initialize()  # idempotent


def test_upsert_note(db: Database):
    """A note can be inserted and retrieved."""
    db.initialize()
    note = Note(
        file_id="tech/test.md",
        title="Test Note",
        content="Hello world",
        tags=["python", "test"],
        category="tech",
        status="published",
    )
    db.upsert_note(note)

    row = db.get_note("tech/test.md")
    assert row is not None
    assert row["title"] == "Test Note"
    assert row["category"] == "tech"


def test_upsert_updates_existing(db: Database):
    """Upserting the same file_id updates the record."""
    db.initialize()
    note1 = Note(file_id="test.md", title="V1", content="old")
    note2 = Note(file_id="test.md", title="V2", content="new")

    db.upsert_note(note1)
    db.upsert_note(note2)

    row = db.get_note("test.md")
    assert row["title"] == "V2"


def test_tags_stored(db: Database):
    """Tags are stored in note_tags and tags_text columns."""
    db.initialize()
    note = Note(file_id="test.md", title="T", tags=["vue", "pinia"])
    db.upsert_note(note)

    tags = db.get_tags("test.md")
    assert set(tags) == {"vue", "pinia"}


def test_fulltext_search(db: Database):
    """FTS5 full-text search returns matching notes."""
    db.initialize()
    db.upsert_note(Note(
        file_id="a.md", title="Vue 状态管理", content="Pinia 是新的状态管理库", tags=["vue"],
    ))
    db.upsert_note(Note(
        file_id="b.md", title="Docker 部署", content="使用 Docker 容器化部署", tags=["docker"],
    ))

    results = db.search_fulltext("状态管理")
    ids = [r["id"] for r in results]
    assert "a.md" in ids


def test_fulltext_search_by_tag(db: Database):
    """FTS5 search matches tags."""
    db.initialize()
    db.upsert_note(Note(
        file_id="a.md", title="Test", content="body", tags=["vue", "pinia"],
    ))

    results = db.search_fulltext("vue")
    assert len(results) >= 1
    assert results[0]["id"] == "a.md"


def test_list_notes(db: Database):
    """List notes with optional category/tag filters."""
    db.initialize()
    db.upsert_note(Note(file_id="a.md", title="A", category="tech", tags=["python"]))
    db.upsert_note(Note(file_id="b.md", title="B", category="daily"))
    db.upsert_note(Note(file_id="c.md", title="C", category="tech", tags=["go"]))

    all_notes = db.list_notes()
    assert len(all_notes) == 3

    tech_notes = db.list_notes(category="tech")
    assert len(tech_notes) == 2

    python_notes = db.list_notes(tag="python")
    assert len(python_notes) == 1


def test_delete_note(db: Database):
    """Deleting a note removes it and its FTS entry."""
    db.initialize()
    db.upsert_note(Note(file_id="del.md", title="Delete Me", content="bye"))
    assert db.get_note("del.md") is not None

    db.delete_note("del.md")
    assert db.get_note("del.md") is None


def test_get_file_hash(db: Database):
    """file_hash is stored and retrievable."""
    db.initialize()
    note = Note(file_id="test.md", title="T", file_hash="abc123")
    db.upsert_note(note)

    row = db.get_note("test.md")
    assert row["file_hash"] == "abc123"


def test_get_all_hashes(db: Database):
    """get_all_hashes returns {file_id: hash} mapping."""
    db.initialize()
    db.upsert_note(Note(file_id="a.md", title="A", file_hash="h1"))
    db.upsert_note(Note(file_id="b.md", title="B", file_hash="h2"))

    hashes = db.get_all_hashes()
    assert hashes == {"a.md": "h1", "b.md": "h2"}


# ---------------------------------------------------------------------------
# Indexer integration tests
# ---------------------------------------------------------------------------


def test_index_files_deleted_detection(db: Database, tmp_path: Path):
    """Create note file, index (full=True), verify in db.
    Delete the file, index (full=False), verify note removed from db."""
    vault = tmp_path
    notes_dir = vault / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Create a test note file under vault/notes/
    note_file = notes_dir / "test.md"
    note_file.write_text(
        "---\ntitle: Test Note\n---\nHello world\n", encoding="utf-8"
    )

    db.initialize()

    # Full index -- should pick up the file
    indexed, _ = index_files(vault, db, full=True)
    assert indexed == 1

    row = db.get_note("notes/test.md")
    assert row is not None
    assert row["title"] == "Test Note"

    # Delete the file from disk
    note_file.unlink()

    # Incremental index -- should detect the missing file and remove from db
    indexed, _ = index_files(vault, db, full=False)

    assert db.get_note("notes/test.md") is None


def test_index_files_incremental_skip_unchanged(db: Database, tmp_path: Path):
    """After full index, incremental run returns 0 (file unchanged, skipped)."""
    vault = tmp_path
    notes_dir = vault / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    note_file = notes_dir / "skip.md"
    note_file.write_text(
        "---\ntitle: Skip\n---\nunchanged\n", encoding="utf-8"
    )

    db.initialize()

    # Full index first -- file is picked up
    indexed, _ = index_files(vault, db, full=True)
    assert indexed == 1

    # Incremental index -- nothing changed, should skip
    indexed, _ = index_files(vault, db, full=False)
    assert indexed == 0


def test_index_files_external_sources(db: Database, tmp_path: Path):
    """Index with external_sources copies .md files into vault/notes/ subdirectory."""
    vault = tmp_path

    # Create external directory with a .md file
    external = tmp_path / "external"
    external.mkdir(exist_ok=True)
    ext_file = external / "ext.md"
    ext_file.write_text(
        "---\ntitle: External\ncategories: mycat\n---\nfrom external\n",
        encoding="utf-8",
    )

    db.initialize()

    index_files(vault, db, full=True, external_sources=[external])

    # File should be copied to vault/notes/mycat/ext.md
    dest = vault / "notes" / "mycat" / "ext.md"
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == (
        "---\ntitle: External\ncategories: mycat\n---\nfrom external\n"
    )

    # Also verify the note was indexed into the database
    row = db.get_note("notes/mycat/ext.md")
    assert row is not None
    assert row["title"] == "External"


def test_index_files_external_sources_collects_relative_images(
    db: Database,
    tmp_path: Path,
):
    """External source sync stores local images and persists note attachments."""
    vault = tmp_path
    external = tmp_path / "blog"
    posts = external / "posts"
    posts.mkdir(parents=True)
    (posts / "diagram.png").write_bytes(b"diagram")
    (posts / "post.md").write_text(
        "---\n"
        "title: External Images\n"
        "categories: docs\n"
        "---\n\n"
        "Body\n\n"
        "![Diagram](./diagram.png)\n",
        encoding="utf-8",
    )

    db.initialize()

    indexed, _ = index_files(
        vault,
        db,
        full=True,
        external_sources=[external],
        source_project="blog",
    )

    assert indexed == 1
    dest = vault / "notes" / "docs" / "post.md"
    text = dest.read_text(encoding="utf-8")
    assert "source_project: blog" in text
    assert "attachments:" in text
    assert "attachments/" in text
    assert "![Diagram](attachments/" in text

    row = db.get_note("notes/docs/post.md")
    assert row is not None
    assert row["source_project"] == "blog"
    attachments = db.get_attachments("notes/docs/post.md")
    assert len(attachments) == 1
    assert attachments[0].startswith("attachments/")
    assert (vault / attachments[0]).read_bytes() == b"diagram"


def test_index_files_external_sources_collects_hexo_asset_folder(
    tmp_path: Path,
):
    """Bare image links resolve from the Hexo same-stem asset folder."""
    vault = tmp_path / "vault"
    external = tmp_path / "blog"
    posts = external / "source" / "_posts"
    asset_dir = posts / "hexo-post"
    asset_dir.mkdir(parents=True)
    (asset_dir / "cover.png").write_bytes(b"cover")
    (posts / "hexo-post.md").write_text(
        "---\n"
        "title: Hexo Post\n"
        "categories: blog\n"
        "---\n\n"
        "![Cover](cover.png)\n",
        encoding="utf-8",
    )
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    index_files(vault, db, full=True, external_sources=[external])

    dest = vault / "notes" / "blog" / "hexo-post.md"
    text = dest.read_text(encoding="utf-8")
    assert "![Cover](attachments/" in text
    assert not (vault / "notes" / "blog" / "hexo-post").exists()
    attachments = db.get_attachments("notes/blog/hexo-post.md")
    assert len(attachments) == 1
    assert attachments[0].startswith("attachments/")


def test_index_vectors_empty_changed_ids(db: Database, tmp_path: Path):
    """index_vectors with empty set() should return 0."""
    pytest.importorskip("sentence_transformers")
    from kb.data.embedding import LocalEmbeddingProvider

    vault = tmp_path
    db.initialize()

    provider = LocalEmbeddingProvider()
    count = index_vectors(vault, db, provider, set())
    assert count == 0


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


def test_index_files_full_removes_missing(db: Database, tmp_path: Path):
    """Insert a Note into db with fake file_hash (no file on disk).
    Full index should remove the ghost note from db."""
    vault = tmp_path
    notes_dir = vault / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    db.initialize()

    # Insert a ghost note directly -- no corresponding file on disk
    ghost = Note(
        file_id="notes/ghost.md",
        title="Ghost",
        content="gone",
        file_hash="fakehash",
    )
    db.upsert_note(ghost)
    assert db.get_note("notes/ghost.md") is not None

    # Full index -- should discover no file for ghost.md and purge it
    index_files(vault, db, full=True)

    assert db.get_note("notes/ghost.md") is None
