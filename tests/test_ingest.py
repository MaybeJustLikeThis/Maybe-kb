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


def test_ingest_uses_custom_notes_dir(tmp_path: Path, db: Database):
    """ingest forwards the configured notes root to note creation."""
    req = IngestRequest(
        title="Custom Ingest",
        content="content",
        source_project="manual",
        category="tech",
    )

    note = ingest(req, tmp_path, db, notes_dir="knowledge")

    assert note.file_id.startswith("knowledge/tech/")
    assert (tmp_path / note.file_id).is_file()


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
