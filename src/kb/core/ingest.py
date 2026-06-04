"""Unified note ingest pipeline."""
from __future__ import annotations

from pathlib import Path

from kb.core import services
from kb.core.config import SourceConfig
from kb.core.models import IngestRequest, Note
from kb.data.database import Database


def ingest(
    request: IngestRequest,
    vault: Path,
    db: Database,
    *,
    source_config: SourceConfig | None = None,
    notes_dir: str = "notes",
) -> Note:
    """Validate, enrich, and persist an ingest request."""
    if not request.title.strip():
        raise ValueError("title must not be empty")
    if not request.content.strip():
        raise ValueError("content must not be empty")

    category = request.category
    if (category is None or not category.strip()) and source_config is not None:
        category = source_config.default_category

    tags = list(request.tags)
    if source_config is not None:
        for tag in source_config.auto_tags:
            if tag not in tags:
                tags.append(tag)

    return services.create_note(
        vault_path=vault,
        db=db,
        title=request.title,
        content=request.content,
        category=category,
        tags=tags,
        description=request.description,
        source_project=request.source_project,
        source_path=request.source_path,
        source_context=request.source_context,
        content_type=request.content_type,
        attachments=request.attachments,
        extra_frontmatter=request.extra_frontmatter,
        notes_dir=notes_dir,
    )
