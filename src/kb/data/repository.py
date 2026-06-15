"""NoteRepository — the sole boundary between core logic and note storage.

Core layers (indexer / services / search / RAG / MCP) depend on this
Protocol, never on a concrete backend. Adding a new note source means
adding a new implementation class; core layers are untouched.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from kb.data.models import Note


@runtime_checkable
class NoteRepository(Protocol):
    """Every note storage backend implements this interface."""

    def discover(self) -> list[str]:
        """file_ids of all notes (deduplicated)."""
        ...

    def read(self, file_id: str) -> Note:
        """Read one note. Raises FileNotFoundError / ValueError."""
        ...

    def write(self, note: Note) -> Note:
        """Create or update. If note.file_id is empty, the repo decides it.
        Returns a Note with committed file_id and fresh file_hash."""
        ...

    def delete(self, file_id: str) -> None:
        """Delete a note. Raises FileNotFoundError / ValueError."""
        ...

    def hash(self, file_id: str) -> str:
        """Content hash for change detection. Raises FileNotFoundError."""
        ...

    def validate(self, file_id: str) -> Path | None:
        """Check file_id stays in bounds. Local impls return resolved Path;
        other backends may return None. Returns None if out of bounds."""
        ...

    @property
    def supports_write(self) -> bool:
        """Whether write/delete work (read-only backends -> False)."""
        ...
