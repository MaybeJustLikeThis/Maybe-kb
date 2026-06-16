"""Shared in-memory test doubles for the NoteRepository contract.

Imported by any core-layer test that wants to exercise logic against the
NoteRepository Protocol without touching the filesystem.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

from kb.data.models import Note


class FakeRepository:
    """In-memory NoteRepository — lets core-layer tests run without a filesystem."""

    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}

    @property
    def supports_write(self) -> bool:
        return True

    def discover(self) -> list[str]:
        return sorted(self._notes)

    def read(self, file_id: str) -> Note:
        if file_id not in self._notes:
            raise FileNotFoundError(file_id)
        return self._notes[file_id]

    def write(self, note: Note) -> Note:
        file_id = note.file_id or f"notes/{note.title.strip() or 'untitled'}.md"
        digest = hashlib.sha256(note.content.encode("utf-8")).hexdigest()
        committed = replace(note, file_id=file_id, file_hash=digest)
        self._notes[file_id] = committed
        return committed

    def delete(self, file_id: str) -> None:
        if file_id not in self._notes:
            raise FileNotFoundError(file_id)
        del self._notes[file_id]

    def hash(self, file_id: str) -> str:
        return self.read(file_id).file_hash or ""

    def validate(self, file_id: str) -> None:
        return None
