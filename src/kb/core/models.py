"""Data models for notes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def parse_tags(raw: str | list[str] | None) -> list[str]:
    """Normalize tags to a list of strings."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    return [str(t).strip() for t in raw if str(t).strip()]


def normalize_date(raw: str | None) -> str | None:
    """Normalize date string to ISO format."""
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    if "T" in raw:
        return raw
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return raw


def _pick(d: dict, *keys: str, default: Any = None) -> Any:
    """Return the first non-None value from d[keys...]."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return default


@dataclass
class Note:
    """A knowledge base note."""

    file_id: str
    title: str
    description: str | None = None
    content: str = ""
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    status: str = "published"
    file_hash: str | None = None
    entry_type: str = ""
    source_project: str | None = None
    source_path: str | None = None
    source_context: str | None = None
    content_type: str = "markdown"
    extra_frontmatter: dict[str, Any] = field(default_factory=dict)
    entry_type: str | None = None
    source_project: str | None = None
    source_path: str | None = None
    source_context: str | None = None
    content_type: str = "markdown"

    @property
    def tags_text(self) -> str:
        """Tags joined by space for FTS5 indexing."""
        return " ".join(self.tags)

    @classmethod
    def from_frontmatter(
        cls,
        title: str,
        frontmatter: dict[str, Any],
        file_path: str,
        content: str = "",
        file_hash: str | None = None,
    ) -> Note:
        """Create Note from parsed frontmatter dict."""
        tags = parse_tags(frontmatter.get("tags"))
        created = normalize_date(_pick(frontmatter, "date", "created"))
        updated = normalize_date(frontmatter.get("updated"))
        category = _pick(frontmatter, "categories", "category")
        attachments = frontmatter.get("attachments") or []
        if isinstance(attachments, str):
            attachments = [attachments]
        status = frontmatter.get("status", "published")
        entry_type = frontmatter.get("type")
        source_project = frontmatter.get("source_project")
        source_path = frontmatter.get("source_path")
        source_context = frontmatter.get("source_context")
        content_type = frontmatter.get("content_type", "markdown")

        managed_keys = {
            "title", "tags", "categories", "category",
            "date", "created", "updated", "description",
            "attachments", "status",
            "type", "source_project", "source_path",
            "source_context", "content_type",
        }
        extra = {k: v for k, v in frontmatter.items() if k not in managed_keys}

        return cls(
            file_id=file_path,
            title=title,
            description=frontmatter.get("description"),
            content=content,
            category=category,
            tags=tags,
            attachments=attachments,
            created_at=created,
            updated_at=updated,
            status=status,
            file_hash=file_hash,
            extra_frontmatter=extra,
            entry_type=entry_type,
            source_project=source_project,
            source_path=source_path,
            source_context=source_context,
            content_type=content_type,
        )
