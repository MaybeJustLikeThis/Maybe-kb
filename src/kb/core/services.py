"""Shared service functions for note CRUD orchestration.

CLI, API routes, and MCP server all go through these functions to ensure
consistent behavior across all interfaces.

Error convention: standard Python exceptions only.
- FileNotFoundError: note does not exist
- ValueError: path traversal blocked
Callers translate these into their own layer: HTTPException (API),
typer.Exit + console.print (CLI), error dict (MCP).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from kb.data.models import Note
from kb.data.storage import (
    make_slug,
    parse_markdown_file,
    validate_vault_path,
    write_markdown_file,
)
from kb.data.database import Database


def resolve_note(vault_path: Path, file_id: str) -> tuple[Path, Note]:
    """Resolve file_id against vault and parse the note file.

    Returns (absolute_path, parsed_note).
    Raises ValueError if path escapes vault.
    Raises FileNotFoundError if note file does not exist.
    """
    full_path = validate_vault_path(vault_path, file_id)
    if not full_path.is_file():
        raise FileNotFoundError(file_id)
    return full_path, parse_markdown_file(full_path, vault_path)


def save_note_file(vault_path: Path, note: Note) -> Note:
    """Write note to disk and re-parse to get fresh hash.

    Sets updated_at to now. Returns freshly-parsed Note.
    Raises ValueError if path escapes vault.
    """
    note = replace(note, updated_at=datetime.now().isoformat(timespec="seconds"))
    full_path = validate_vault_path(vault_path, note.file_id)
    write_markdown_file(full_path, note)
    return parse_markdown_file(full_path, vault_path)


def create_note(
    vault_path: Path,
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
    notes_dir: str = "notes",
) -> Note:
    """Create a new note — slug generation, collision avoidance, file write, DB insert.

    Returns the parsed Note (with correct file_id, hash, timestamps).
    Raises ValueError if slug produces a path that escapes vault.
    """
    now = datetime.now().isoformat(timespec="seconds")
    tag_list = list(tags) if tags else []
    cat = category if category else None

    slug, cat = make_slug(title, cat)
    vault_root = vault_path.resolve()
    notes_root = (vault_path / notes_dir).resolve()
    if not notes_root.is_relative_to(vault_root):
        raise ValueError(f"Configured notes directory escapes the vault: {notes_dir}")

    def resolve_create_path(suffix: str = "") -> tuple[str, Path]:
        full_path = (notes_root / cat / f"{slug}{suffix}.md").resolve()
        if (
            not full_path.is_relative_to(vault_root)
            or not full_path.is_relative_to(notes_root)
        ):
            raise ValueError("Note path escapes the configured notes directory")
        return full_path.relative_to(vault_root).as_posix(), full_path

    file_path, full_path = resolve_create_path()

    counter = 2
    while full_path.exists():
        suffix = f"-{counter}"
        file_path, full_path = resolve_create_path(suffix)
        counter += 1

    note = Note(
        file_id=file_path,
        title=title,
        content=content,
        category=cat,
        tags=tag_list,
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

    write_markdown_file(full_path, note)
    parsed = parse_markdown_file(full_path, vault_path)
    db.upsert_note(parsed)
    return parsed


def update_note(
    vault_path: Path,
    db: Database,
    file_id: str,
    **fields,
) -> Note:
    """Update note fields — re-read, modify, write, re-index.

    Only provided (non-None) fields are updated. Fields not in kwargs
    are left unchanged. Sets updated_at to now.

    Raises ValueError if path escapes vault.
    Raises FileNotFoundError if note does not exist.
    """
    full_path = validate_vault_path(vault_path, file_id)
    if not full_path.is_file():
        raise FileNotFoundError(file_id)

    note = parse_markdown_file(full_path, vault_path)

    update_kwargs: dict[str, object] = {
        k: v for k, v in fields.items()
        if v is not None and hasattr(note, k)
    }
    update_kwargs["updated_at"] = datetime.now().isoformat(timespec="seconds")
    note = replace(note, **update_kwargs)

    write_markdown_file(full_path, note)
    note = parse_markdown_file(full_path, vault_path)
    db.upsert_note(note)
    return note


def delete_note(vault_path: Path, db: Database, file_id: str) -> None:
    """Delete note file and DB record.

    Raises ValueError if path escapes vault.
    Raises FileNotFoundError if note does not exist.
    """
    full_path = validate_vault_path(vault_path, file_id)
    if not full_path.is_file():
        raise FileNotFoundError(file_id)
    full_path.unlink()
    db.delete_note(file_id)
