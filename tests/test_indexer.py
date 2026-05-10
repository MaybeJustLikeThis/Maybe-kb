"""Tests for SQLite indexer and index operations."""
import pytest
from pathlib import Path
from kb.data.database import Database
from kb.core.models import Note
from kb.core.indexer import index_files, index_vectors


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


def test_index_vectors_empty_changed_ids(db: Database, tmp_path: Path):
    """index_vectors with empty set() should return 0."""
    pytest.importorskip("sentence_transformers")
    from kb.data.embedding import LocalEmbeddingProvider

    vault = tmp_path
    db.initialize()

    provider = LocalEmbeddingProvider()
    count = index_vectors(vault, db, provider, set())
    assert count == 0


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
