"""NoteRepository — the sole boundary between core logic and note storage.

Core layers (indexer / services / search / RAG / MCP) depend on this
Protocol, never on a concrete backend. Adding a new note source means
adding a new implementation class; core layers are untouched.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from kb.data.models import Note

if TYPE_CHECKING:
    from kb.core.config import KBConfig


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


def create_repository(config: "KBConfig", vault: Path) -> NoteRepository:
    """Factory: build a NoteRepository from config.repository.provider.

    Single backend today; dispatching here means adding a second backend
    only touches this function, not context.py.
    """
    from kb.data.local_repository import LocalMarkdownRepository

    provider = config.repository.provider
    if provider == "local":
        return LocalMarkdownRepository(
            vault,
            notes_dir=config.general.notes_dir,
            attachments_dir=config.general.attachments_dir,
        )
    raise ValueError(f"Unknown repository provider: {provider!r}")
