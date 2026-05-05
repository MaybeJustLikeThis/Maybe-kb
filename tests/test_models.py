"""Tests for data models."""
import pytest
from datetime import datetime
from kb.models import Note, parse_tags, normalize_date


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
