"""Tests for SQLite indexer."""
import pytest
from pathlib import Path
from kb.indexer import Database
from kb.models import Note


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
