"""Open-target builders for external editors."""
from __future__ import annotations

from urllib.parse import quote

from kb.core.config import KBConfig
from kb.data.storage import validate_vault_path


def build_obsidian_open_target(config: KBConfig, file_id: str) -> dict[str, str]:
    """Build a safe Obsidian URI target for a note file_id."""
    resolved = validate_vault_path(config.vault_path, file_id)
    if not resolved.is_file():
        raise FileNotFoundError(file_id)

    relative_path = resolved.relative_to(config.vault_path.resolve()).as_posix()
    vault_name = config.obsidian.vault_name or config.vault_path.name
    return {
        "obsidian_uri": (
            "obsidian://open?"
            f"vault={quote(vault_name, safe='')}"
            f"&file={quote(relative_path, safe='')}"
        ),
        "file_path": resolved.as_posix(),
        "relative_path": relative_path,
    }
