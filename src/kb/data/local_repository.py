"""Local filesystem NoteRepository — Markdown + PDF files under a vault.

Encapsulates the existing storage.py file functions behind the
NoteRepository Protocol. File-specific side effects (dedup, external
source sync) live here as methods, NOT on the Protocol — only the
local backend has these semantics.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from kb.data.models import Note
from kb.data.storage import (
    _compute_hash,
    discover_notes,
    make_slug,
    parse_markdown_file,
    parse_pdf_file,
    validate_vault_path,
    write_markdown_file,
)

_log = logging.getLogger(__name__)


class LocalMarkdownRepository:
    """NoteRepository backed by a local vault directory."""

    def __init__(
        self,
        vault_path: Path,
        notes_dir: str = "notes",
        attachments_dir: str = "attachments",
    ) -> None:
        self._vault = vault_path
        self._notes_dir = notes_dir
        self._attachments_dir = attachments_dir

    @property
    def supports_write(self) -> bool:
        return True

    def discover(self) -> list[str]:
        self._dedupe()
        paths = discover_notes(self._vault, notes_dir=self._notes_dir)
        return [p.relative_to(self._vault).as_posix() for p in paths]

    def read(self, file_id: str) -> Note:
        full = self.validate(file_id)
        if full is None or not full.is_file():
            raise FileNotFoundError(file_id)
        if full.suffix.lower() == ".pdf":
            return parse_pdf_file(full, self._vault)
        return parse_markdown_file(full, self._vault)

    def write(self, note: Note) -> Note:
        if not note.file_id:
            note = replace(note, file_id=self._allocate_file_id(note))
        full = self.validate(note.file_id)
        if full is None:
            raise ValueError(note.file_id)
        write_markdown_file(full, note)
        return parse_markdown_file(full, self._vault)

    def delete(self, file_id: str) -> None:
        full = self.validate(file_id)
        if full is None or not full.is_file():
            raise FileNotFoundError(file_id)
        full.unlink()

    def hash(self, file_id: str) -> str:
        full = self.validate(file_id)
        if full is None or not full.is_file():
            raise FileNotFoundError(file_id)
        return _compute_hash(full)

    def validate(self, file_id: str) -> Path | None:
        try:
            return validate_vault_path(self._vault, file_id)
        except ValueError:
            return None

    # -- file-specific helpers (not on the Protocol) --

    def _allocate_file_id(self, note: Note) -> str:
        """Pick a notes_dir-relative path for a new note (slug + collision check)."""
        slug, cat = make_slug(note.title, note.category)
        vault_root = self._vault.resolve()
        notes_root = (self._vault / self._notes_dir).resolve()
        if not notes_root.is_relative_to(vault_root):
            raise ValueError(f"notes_dir escapes vault: {self._notes_dir}")

        def resolve_path(suffix: str) -> tuple[str, Path]:
            full = (notes_root / cat / f"{slug}{suffix}.md").resolve()
            if not (full.is_relative_to(vault_root) and full.is_relative_to(notes_root)):
                raise ValueError("allocated path escapes notes dir")
            return full.relative_to(vault_root).as_posix(), full

        file_id, full = resolve_path("")
        counter = 2
        while full.exists():
            file_id, full = resolve_path(f"-{counter}")
            counter += 1
        return file_id

    def _dedupe(self) -> None:
        """Remove files with identical content but different paths."""
        seen: dict[str, Path] = {}
        for p in discover_notes(self._vault, notes_dir=self._notes_dir):
            try:
                h = _compute_hash(p)
            except Exception:
                continue
            if h in seen:
                p.unlink()
                _log.info("Removed duplicate %s (same content as %s)", p, seen[h])
            else:
                seen[h] = p
