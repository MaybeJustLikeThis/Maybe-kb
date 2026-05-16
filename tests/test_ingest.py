"""Tests for the unified ingest pipeline."""
from pathlib import Path

import pytest

from kb.core.config import SourceConfig
from kb.core.ingest import ingest
from kb.core.models import IngestRequest
from kb.data.database import Database


def make_db(vault: Path) -> Database:
    """Create an initialized test database for a vault."""
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()
    return db


@pytest.fixture
def db(tmp_path: Path):
    """Create and close an initialized test database."""
    database = make_db(tmp_path)
    try:
        yield database
    finally:
        database.close()


def test_ingest_creates_note(tmp_path: Path, db: Database):
    """ingest() with valid input creates a note file and DB record."""
    req = IngestRequest(
        title="Test Note",
        content="# Hello\n\nWorld",
        source_project="manual",
        tags=["python"],
        category="tech",
    )
    source_config = SourceConfig(label="Manual")
    note = ingest(req, tmp_path, db, source_config=source_config)

    assert note.title == "Test Note"
    assert note.file_id.startswith("notes/tech/")
    assert (tmp_path / note.file_id).is_file()
    row = db.get_note(note.file_id)
    assert row is not None
    assert row["source_project"] == "manual"


def test_ingest_applies_default_category(tmp_path: Path, db: Database):
    """When category is None, default_category from source_config is used."""
    req = IngestRequest(
        title="No Cat",
        content="content",
        source_project="blog",
    )
    source_config = SourceConfig(label="Blog", default_category="articles")
    note = ingest(req, tmp_path, db, source_config=source_config)

    assert note.category == "articles"


def test_ingest_applies_default_category_for_blank_category(
    tmp_path: Path, db: Database
):
    """When category is blank, default_category from source_config is used."""
    req = IngestRequest(
        title="Blank Cat",
        content="content",
        source_project="blog",
        category=" \t",
    )
    source_config = SourceConfig(label="Blog", default_category="articles")
    note = ingest(req, tmp_path, db, source_config=source_config)

    assert note.category == "articles"


def test_ingest_merges_auto_tags(tmp_path: Path, db: Database):
    """User tags and source auto_tags are merged, deduplicated."""
    req = IngestRequest(
        title="Tagged",
        content="content",
        source_project="agent",
        tags=["python", "mcp"],
    )
    source_config = SourceConfig(
        label="Agent",
        auto_tags=["auto-generated", "python"],
    )
    note = ingest(req, tmp_path, db, source_config=source_config)

    assert "auto-generated" in note.tags
    assert "python" in note.tags
    assert "mcp" in note.tags
    assert note.tags.count("python") == 1


def test_ingest_rejects_empty_title(tmp_path: Path, db: Database):
    """Empty title raises ValueError."""
    req = IngestRequest(title="  ", content="x", source_project="manual")
    with pytest.raises(ValueError, match="title"):
        ingest(req, tmp_path, db)


def test_ingest_rejects_empty_content(tmp_path: Path, db: Database):
    """Empty content raises ValueError."""
    req = IngestRequest(title="x", content="\n\t", source_project="manual")
    with pytest.raises(ValueError, match="content"):
        ingest(req, tmp_path, db)
