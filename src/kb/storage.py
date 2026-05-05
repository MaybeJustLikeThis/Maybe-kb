"""Markdown file reading, writing, and frontmatter parsing."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from kb.models import Note

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _compute_hash(path: Path) -> str:
    """SHA256 of file content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split Markdown into frontmatter dict and body text."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw_yaml = match.group(1)
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        data = {}

    body = text[match.end():]
    return data, body


def parse_markdown_file(file_path: Path, vault_path: Path) -> Note:
    """Parse a Markdown file into a Note object."""
    text = file_path.read_text(encoding="utf-8")
    frontmatter, content = _split_frontmatter(text)
    file_hash = _compute_hash(file_path)

    rel = file_path.relative_to(vault_path).as_posix()
    title = frontmatter.get("title") or file_path.stem

    return Note.from_frontmatter(
        title=title,
        frontmatter=frontmatter,
        file_path=rel,
        content=content,
        file_hash=file_hash,
    )


def _build_frontmatter_yaml(note: Note) -> str:
    """Build YAML frontmatter string from a Note."""
    data: dict[str, Any] = {"title": note.title}

    if note.tags:
        data["tags"] = note.tags
    if note.category:
        data["categories"] = note.category
    if note.description:
        data["description"] = note.description
    if note.created_at:
        data["date"] = note.created_at
    if note.updated_at:
        data["updated"] = note.updated_at
    if note.attachments:
        data["attachments"] = note.attachments
    if note.status != "published":
        data["status"] = note.status

    for k, v in note.extra_frontmatter.items():
        if k not in data:
            data[k] = v

    return yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()


def write_markdown_file(file_path: Path, note: Note) -> None:
    """Write a Note to a Markdown file with frontmatter."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fm = _build_frontmatter_yaml(note)
    body = note.content if note.content.endswith("\n") else note.content + "\n"
    file_path.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


def discover_notes(vault_path: Path) -> list[Path]:
    """Find all .md files under notes/ directory."""
    notes_dir = vault_path / "notes"
    if not notes_dir.exists():
        return []
    return sorted(notes_dir.rglob("*.md"))
