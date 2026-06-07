"""Single-file import: convert via markitdown, store attachment, create note."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from kb.core.ingest import ingest
from kb.core.models import IngestRequest, Note
from kb.data.attachments import store_attachment
from kb.data.database import Database
from kb.parsers.markitdown_converter import (
    ConversionError,
    MarkItDownNotInstalledError,
    convert_file,
)


class ImportFileError(Exception):
    """Raised when file import fails."""


def import_file(
    source: Path,
    *,
    vault: Path,
    db: Database,
    notes_dir: str = "notes",
    attachments_dir: str = "attachments",
    title: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    source_config: Any = None,
) -> Note:
    """Import a file into the knowledge base.

    1. Store the original file as an attachment.
    2. Convert to Markdown via markitdown.
    3. Assemble IngestRequest and call ingest().

    Args:
        source: Absolute path to the file to import.
        vault: Vault root path.
        db: Database instance.
        notes_dir: Notes subdirectory name.
        attachments_dir: Attachments subdirectory name.
        title: Override title (default: filename without extension).
        category: Override category (default: "未分类").
        tags: Optional tags.
        source_config: Optional SourceConfig for ingest().

    Returns:
        The created Note.

    Raises:
        ImportFileError: import failed (conversion, empty content, etc.)
    """
    if not source.is_file():
        raise ImportFileError(f"File not found: {source}")

    # 1. Store original as attachment
    attachment_path = store_attachment(
        source, vault, attachments_dir=attachments_dir,
    )

    # 2. Convert to Markdown
    try:
        result = convert_file(source)
    except MarkItDownNotInstalledError as exc:
        raise ImportFileError(str(exc)) from exc
    except ConversionError as exc:
        raise ImportFileError(str(exc)) from exc

    # 3. Determine metadata
    stem = source.stem
    ext = source.suffix.lstrip(".")
    resolved_title = title or stem
    resolved_category = category or "未分类"

    # 4. Assemble IngestRequest
    request = IngestRequest(
        title=resolved_title,
        content=result.text,
        source_project="imported",
        category=resolved_category,
        tags=list(tags) if tags else [],
        content_type=ext,
        source_path=attachment_path,
        attachments=[attachment_path],
        extra_frontmatter={
            "source_file": result.metadata.get("source_file", source.name),
        },
    )

    # 5. Ingest
    return ingest(
        request,
        vault=vault,
        db=db,
        source_config=source_config,
        notes_dir=notes_dir,
    )
