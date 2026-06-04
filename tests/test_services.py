"""Tests for shared CRUD service functions."""
import pytest
from pathlib import Path
from kb.core.services import (
    resolve_note,
    save_note_file,
    create_note,
    update_note,
    delete_note,
)
from kb.data.database import Database


def test_create_note_writes_file_and_indexes(tmp_path: Path):
    """create_note writes .md file and inserts into DB."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    note = create_note(vault, db, "Test Note", "# Hello\n\nContent", "tech", ["python"])

    assert note.title == "Test Note"
    assert note.file_id.startswith("notes/tech/")
    assert note.file_id.endswith(".md")
    assert (vault / note.file_id).is_file()
    row = db.get_note(note.file_id)
    assert row is not None
    assert row["title"] == "Test Note"
    assert db.get_tags(note.file_id) == ["python"]
    db.close()


def test_create_note_uses_custom_notes_dir(tmp_path: Path):
    """create_note writes beneath the configured notes root."""
    vault = tmp_path
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    note = create_note(
        vault,
        db,
        "Custom Root",
        "content",
        category="tech",
        notes_dir="knowledge/notes",
    )

    assert note.file_id.startswith("knowledge/notes/tech/")
    assert (vault / note.file_id).is_file()
    assert not (vault / "notes").exists()
    db.close()


@pytest.mark.parametrize(
    ("notes_dir", "category"),
    [
        ("../outside", "tech"),
        ("knowledge/notes", ".."),
    ],
)
def test_create_note_rejects_paths_outside_configured_notes_root(
    tmp_path: Path,
    notes_dir: str,
    category: str,
):
    """create_note blocks configured roots and categories that escape containment."""
    vault = tmp_path
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    with pytest.raises(ValueError):
        create_note(
            vault,
            db,
            "Escape Attempt",
            "content",
            category=category,
            notes_dir=notes_dir,
        )

    db.close()


def test_create_note_slug_collision(tmp_path: Path):
    """Second note with same title gets -2 suffix."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    n1 = create_note(vault, db, "Same Title", "content 1")
    n2 = create_note(vault, db, "Same Title", "content 2")

    assert n1.file_id != n2.file_id
    assert n1.file_id.startswith("notes/未分类/")
    assert n2.file_id.startswith("notes/未分类/")
    assert "-2" in n2.file_id
    db.close()


def test_create_note_no_category_goes_to_weifenlei(tmp_path: Path):
    """Notes without category are stored under 未分类/."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    note = create_note(vault, db, "Random Thought", "content")

    assert note.file_id.startswith("notes/未分类/")
    assert (vault / note.file_id).is_file()
    db.close()


def test_create_note_path_traversal_sanitized(tmp_path: Path):
    """create_note sanitizes path-traversal chars in title via make_slug."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    note = create_note(vault, db, "../../etc/hosts", "evil")
    # make_slug replaces / with -, so path traversal sequences can't form
    assert "/../" not in note.file_id
    db.close()


def test_resolve_note_returns_path_and_parsed_note(tmp_path: Path):
    """resolve_note validates path, checks existence, and parses."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    created = create_note(vault, db, "Test", "content here", tags=["x"])

    full_path, note = resolve_note(vault, created.file_id)
    assert full_path.is_file()
    assert note.title == "Test"
    assert note.content.rstrip("\n") == "content here"
    db.close()


def test_resolve_note_not_found(tmp_path: Path):
    """resolve_note raises FileNotFoundError for missing file."""
    vault = tmp_path
    (vault / "notes").mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_note(vault, "notes/nonexistent.md")


def test_resolve_note_path_traversal_blocked(tmp_path: Path):
    """resolve_note raises ValueError for path traversal."""
    with pytest.raises(ValueError):
        resolve_note(tmp_path, "../etc/passwd")


def test_update_note_modifies_fields(tmp_path: Path):
    """update_note changes specified fields and preserves others."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    created = create_note(vault, db, "Old Title", "Old content", "tech", ["a"])

    updated = update_note(vault, db, created.file_id,
                          title="New Title", content="New content")
    assert updated.title == "New Title"
    assert updated.content.rstrip("\n") == "New content"
    assert updated.category == "tech"
    db.close()


def test_update_note_not_found(tmp_path: Path):
    """update_note raises FileNotFoundError for missing note."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    with pytest.raises(FileNotFoundError):
        update_note(vault, db, "notes/nonexistent.md", title="New")


def test_delete_note_removes_file_and_record(tmp_path: Path):
    """delete_note removes .md file and DB record."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    created = create_note(vault, db, "To Delete", "content")
    delete_note(vault, db, created.file_id)

    assert not (vault / created.file_id).is_file()
    assert db.get_note(created.file_id) is None
    db.close()


def test_delete_note_not_found(tmp_path: Path):
    """delete_note raises FileNotFoundError for missing note."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    with pytest.raises(FileNotFoundError):
        delete_note(vault, db, "notes/nonexistent.md")


def test_note_response_includes_new_fields(tmp_path: Path):
    """note_to_response includes source fields."""
    from kb.core.models import Note
    from kb.core.serializers import note_to_response
    note = Note(
        file_id="notes/x.md", title="X",
        source_project="kb", source_context="testing",
    )
    resp = note_to_response(note)
    assert resp["source_project"] == "kb"
    assert resp["source_context"] == "testing"
    assert resp["content_type"] == "markdown"


def test_note_row_to_dict_includes_new_fields(tmp_path: Path):
    """note_row_to_dict returns new fields from DB row."""
    from kb.core.serializers import note_row_to_dict

    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    note = create_note(vault, db, "Source Test", "content", category="tech", tags=["test"])
    conn = db._connect()
    conn.execute(
        "UPDATE notes SET source_project=?, source_context=? WHERE id=?",
        ("kb", "testing source", note.file_id),
    )
    conn.commit()

    row = db.get_note(note.file_id)
    result = note_row_to_dict(db, row)
    assert result["source_project"] == "kb"
    assert result["source_context"] == "testing source"
    db.close()


def test_create_note_with_source(tmp_path: Path):
    """create_note persists source fields."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    note = create_note(
        vault, db, "Source Note", "# Content",
        category="tech", tags=["test"],
        source_project="kb",
        source_context="architectural discussion",
    )

    assert note.source_project == "kb"
    assert note.source_context == "architectural discussion"

    row = db.get_note(note.file_id)
    assert row["source_project"] == "kb"
    db.close()


def test_update_note_can_set_source_fields(tmp_path: Path):
    """update_note can modify source tracking fields."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    created = create_note(vault, db, "Test", "content")
    updated = update_note(vault, db, created.file_id,
                          source_project="my-app",
                          source_context="debugging session")

    assert updated.source_project == "my-app"
    assert updated.source_context == "debugging session"
    db.close()


def test_save_note_file_updates_timestamp(tmp_path: Path):
    """save_note_file sets updated_at and re-parses."""
    import time
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    created = create_note(vault, db, "Test", "content")
    old_updated = created.updated_at

    time.sleep(1.1)  # ensure timestamp ticks to next second
    created.content = "new content"
    saved = save_note_file(vault, created)

    assert saved.updated_at != old_updated
    assert saved.content.rstrip("\n") == "new content"
    db.close()
