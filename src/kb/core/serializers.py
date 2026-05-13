"""Unified serializers for converting Note/DB rows to API response dicts."""
from __future__ import annotations

from kb.data.database import Database


def note_row_to_dict(db: Database, row, *, include_content: bool = False) -> dict:
    """Convert a DB row to a dict ready for API responses.

    Args:
        db: Database instance (for tag resolution).
        row: SQLite Row or dict with keys: id, title, description, category,
             created_at, updated_at, status.
        include_content: If True, include the full content field.

    Returns dict with keys: file_id, title, description, category, tags,
    created_at, updated_at, status, [content].
    """
    row_dict = dict(row) if not isinstance(row, dict) else row
    tags = db.get_tags(row_dict.get("id", ""))

    result = {
        "file_id": row_dict["id"],
        "title": row_dict["title"],
        "description": row_dict.get("description"),
        "category": row_dict.get("category"),
        "tags": tags,
        "created_at": row_dict.get("created_at"),
        "updated_at": row_dict.get("updated_at"),
        "status": row_dict.get("status", "published"),
        "entry_type": row_dict.get("entry_type"),
        "source_project": row_dict.get("source_project"),
        "source_path": row_dict.get("source_path"),
        "source_context": row_dict.get("source_context"),
        "content_type": row_dict.get("content_type", "markdown"),
    }

    if include_content:
        result["content"] = row_dict.get("content", "")

    return result


def note_to_response(note) -> dict:
    """Convert a Note object to an API-compatible dict."""
    return {
        "file_id": note.file_id,
        "title": note.title,
        "description": note.description,
        "content": note.content,
        "category": note.category,
        "tags": note.tags,
        "attachments": note.attachments,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "status": note.status,
        "entry_type": note.entry_type,
        "source_project": note.source_project,
        "source_path": note.source_path,
        "source_context": note.source_context,
        "content_type": note.content_type,
    }
