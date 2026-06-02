"""Tests for data models."""
import pytest
from datetime import datetime
from kb.core.models import IngestRequest, Note, parse_tags, normalize_date


def test_note_from_dict_minimal():
    """Note can be created from minimal frontmatter data."""
    note = Note.from_frontmatter(
        title="Test Note",
        frontmatter={"title": "Test Note", "date": "2025-07-03 20:55:38"},
        file_path="tech/test.md",
    )
    assert note.title == "Test Note"
    assert note.file_id == "tech/test.md"
    assert note.status == "published"


def test_parse_tags_string():
    """Single string tag is converted to list."""
    assert parse_tags("杂谈") == ["杂谈"]


def test_parse_tags_list():
    """List of tags is returned as-is."""
    assert parse_tags(["vue", "pinia"]) == ["vue", "pinia"]


def test_parse_tags_empty():
    """Empty/None tags returns empty list."""
    assert parse_tags(None) == []
    assert parse_tags("") == []


def test_normalize_date_string():
    """Date string is parsed to ISO format."""
    result = normalize_date("2025-07-03 20:55:38")
    assert result == "2025-07-03T20:55:38"


def test_normalize_date_none():
    """None date returns None."""
    assert normalize_date(None) is None


def test_normalize_date_iso():
    """Already ISO date passes through."""
    result = normalize_date("2026-05-05T10:00:00+08:00")
    assert result == "2026-05-05T10:00:00+08:00"


def test_note_tags_text():
    """tags_text property joins tags with space."""
    note = Note.from_frontmatter(
        title="Test",
        frontmatter={"title": "Test", "tags": ["vue", "pinia"]},
        file_path="test.md",
    )
    assert note.tags_text == "vue pinia"


def test_note_new_source_fields():
    """Note supports source tracking fields."""
    source_context = "source context"
    note = Note(
        file_id="notes/test/example.md",
        title="测试笔记",
        content="内容",
        source_project="kb",
        source_path="/home/user/projects/kb",
        source_context=source_context,
        content_type="markdown",
    )
    assert note.source_project == "kb"
    assert note.source_path == "/home/user/projects/kb"
    assert note.source_context == source_context
    assert note.content_type == "markdown"


def test_note_new_fields_defaults():
    """New fields have sensible defaults."""
    note = Note(file_id="x", title="x")
    assert note.source_project is None
    assert note.source_path is None
    assert note.source_context is None
    assert note.content_type == "markdown"


def test_note_from_frontmatter_extracts_new_fields():
    """from_frontmatter parses source fields."""
    fm = {
        "title": "Test",
        "source_project": "my-app",
        "source_path": "/code/my-app",
        "source_context": "debugging login bug",
        "content_type": "markdown",
    }
    note = Note.from_frontmatter(title="Test", frontmatter=fm, file_path="notes/x.md")
    assert note.source_project == "my-app"
    assert note.source_path == "/code/my-app"
    assert note.source_context == "debugging login bug"
    assert note.content_type == "markdown"


def test_ingest_request_minimal():
    """IngestRequest requires title, content, source_project."""
    req = IngestRequest(
        title="Test",
        content="Content",
        source_project="manual",
    )
    assert req.title == "Test"
    assert req.content == "Content"
    assert req.source_project == "manual"


def test_ingest_request_defaults():
    """Optional fields have sensible defaults."""
    req = IngestRequest(title="T", content="C", source_project="blog")
    assert req.tags == []
    assert req.category is None
    assert req.description is None
    assert req.source_context is None


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


def test_ingest_request_is_frozen():
    """IngestRequest is immutable."""
    req = IngestRequest(title="T", content="C", source_project="blog")
    with pytest.raises(Exception):
        req.title = "New"  # type: ignore
