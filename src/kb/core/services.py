"""Shared service functions for note CRUD orchestration.

CLI / API / MCP all go through these. Error convention: standard
Python exceptions only — FileNotFoundError (missing), ValueError
(traversal). Callers translate to their layer.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from kb.data.database import Database
from kb.data.models import Note
from kb.data.repository import NoteRepository


def resolve_note(repo: NoteRepository, file_id: str) -> tuple[Path | None, Note]:
    """Validate + read. Raises ValueError (traversal) / FileNotFoundError (missing)."""
    full = repo.validate(file_id)
    if full is None:
        raise ValueError(f"Path traversal blocked: {file_id}")
    return full, repo.read(file_id)


def save_note_file(repo: NoteRepository, note: Note) -> Note:
    """Write note and re-read for fresh hash. Sets updated_at."""
    note = replace(note, updated_at=datetime.now().isoformat(timespec="seconds"))
    return repo.write(note)


def create_note(
    repo: NoteRepository,
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
    extra_frontmatter: dict[str, Any] | None = None,
) -> Note:
    """Create a note — repo decides file_id, DB gets indexed.

    file_id allocation, slug and collision avoidance live in the repo.
    """
    now = datetime.now().isoformat(timespec="seconds")
    draft = Note(
        file_id="",
        title=title,
        content=content,
        category=category,
        tags=list(tags) if tags else [],
        description=description,
        created_at=now,
        updated_at=now,
        source_project=source_project,
        source_path=source_path,
        source_context=source_context,
        content_type=content_type,
        attachments=list(attachments) if attachments else [],
        extra_frontmatter=dict(extra_frontmatter) if extra_frontmatter else {},
    )
    written = repo.write(draft)
    db.upsert_note(written)
    return written


def update_note(repo: NoteRepository, db: Database, file_id: str, **fields) -> Note:
    """Update provided fields. Raises ValueError / FileNotFoundError."""
    note = repo.read(file_id)
    update_kwargs = {
        k: v for k, v in fields.items() if v is not None and hasattr(note, k)
    }
    update_kwargs["updated_at"] = datetime.now().isoformat(timespec="seconds")
    note = replace(note, **update_kwargs)
    note = repo.write(note)
    db.upsert_note(note)
    return note


def delete_note(repo: NoteRepository, db: Database, file_id: str) -> None:
    """Delete note file + DB record. Raises ValueError / FileNotFoundError."""
    repo.delete(file_id)
    db.delete_note(file_id)
