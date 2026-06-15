"""Open-target strategies for external editors — decoupled from note sources.

Which editor opens a note is orthogonal to where the note is stored.
ObsidianTarget and FileTarget are two strategies behind one Protocol.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from urllib.parse import quote

from kb.core.config import KBConfig
from kb.data.repository import NoteRepository


@runtime_checkable
class OpenTargetStrategy(Protocol):
    def build(self, repo: NoteRepository, file_id: str) -> dict[str, str]: ...


class ObsidianTarget:
    """Open via obsidian:// URI."""

    def __init__(self, vault_name: str) -> None:
        self._vault_name = vault_name

    def build(self, repo: NoteRepository, file_id: str) -> dict[str, str]:
        resolved = repo.validate(file_id)
        if resolved is None or not resolved.is_file():
            raise FileNotFoundError(file_id)
        return {
            "obsidian_uri": (
                "obsidian://open?"
                f"vault={quote(self._vault_name, safe='')}"
                f"&file={quote(file_id, safe='')}"
            ),
            "file_path": resolved.as_posix(),
            "relative_path": file_id,
        }


class FileTarget:
    """Open via plain file path — non-Obsidian / macOS fallback."""

    def build(self, repo: NoteRepository, file_id: str) -> dict[str, str]:
        resolved = repo.validate(file_id)
        if resolved is None or not resolved.is_file():
            raise FileNotFoundError(file_id)
        return {
            "file_path": resolved.as_posix(),
            "relative_path": file_id,
        }


def create_open_target(config: KBConfig) -> OpenTargetStrategy:
    """Pick strategy by config.obsidian.enabled."""
    if config.obsidian.enabled:
        vault_name = config.obsidian.vault_name or config.vault_path.name
        return ObsidianTarget(vault_name)
    return FileTarget()


# --- backward-compat shim (removed in Task 10) ---

def build_obsidian_open_target(config: KBConfig, file_id: str) -> dict[str, str]:
    """Deprecated shim kept until api/v1.py switches to ctx.open_target."""
    from kb.data.local_repository import LocalMarkdownRepository

    repo = LocalMarkdownRepository(config.vault_path, config.general.notes_dir)
    vault_name = config.obsidian.vault_name or config.vault_path.name
    return ObsidianTarget(vault_name).build(repo, file_id)
