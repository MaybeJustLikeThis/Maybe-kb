"""Markdown file reading, writing, and frontmatter parsing."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from kb.core.models import Note

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
    if note.source_project:
        data["source_project"] = note.source_project
    if note.source_path:
        data["source_path"] = note.source_path
    if note.source_context:
        data["source_context"] = note.source_context
    if note.content_type != "markdown":
        data["content_type"] = note.content_type

    for k, v in note.extra_frontmatter.items():
        if k not in data:
            data[k] = v

    return yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()


def make_slug(title: str, category: str | None = None) -> tuple[str, str]:
    """Sanitize title and category into safe filename components."""
    slug = title.lower().replace(" ", "-").replace("/", "-").replace("\\", "-")[:50]
    cat = category.replace("/", "-").replace("\\", "-") if category else "未分类"
    return slug, cat


def write_markdown_file(file_path: Path, note: Note) -> None:
    """Write a Note to a Markdown file with frontmatter."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fm = _build_frontmatter_yaml(note)
    body = note.content if note.content.endswith("\n") else note.content + "\n"
    file_path.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


def validate_vault_path(vault_path: Path, file_id: str) -> Path:
    """Resolve a file_id against vault_path, blocking path traversal.

    Returns the resolved absolute Path, or raises ValueError if the path
    escapes the vault.
    """
    resolved = (vault_path / file_id).resolve()
    vault_resolved = vault_path.resolve()
    if not resolved.is_relative_to(vault_resolved):
        raise ValueError(f"Path traversal blocked: {file_id}")
    return resolved


def discover_notes(vault_path: Path) -> list[Path]:
    """Find all .md files under notes/ directory."""
    notes_dir = vault_path / "notes"
    if not notes_dir.exists():
        return []
    return sorted(notes_dir.rglob("*.md"))


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks at paragraph or sentence boundaries."""
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len <= max_chars:
            current.append(para)
            current_len += para_len
        else:
            if current:
                chunks.append("\n\n".join(current))
            if para_len > max_chars:
                sub_chunks = _split_long_paragraph(para, max_chars, overlap)
                chunks.extend(sub_chunks)
                current = []
                current_len = 0
            else:
                current = [para]
                current_len = para_len

    if current:
        chunks.append("\n\n".join(current))

    if overlap and len(chunks) > 1:
        chunks = _apply_overlap(chunks, overlap)

    return chunks


def _split_long_paragraph(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split a single paragraph at sentence boundaries."""
    sentences = re.split(r"(?<=[.。！？!?])\s*", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        s_len = len(sentence)
        if current_len + s_len <= max_chars:
            current.append(sentence)
            current_len += s_len
        else:
            if current:
                chunks.append("".join(current))
            if s_len > max_chars:
                for i in range(0, s_len, max_chars - overlap):
                    chunks.append(sentence[i:i + max_chars])
                current = []
                current_len = 0
            else:
                current = [sentence]
                current_len = s_len

    if current:
        chunks.append("".join(current))
    return chunks


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Add overlap text from previous chunk to next chunk."""
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        if len(prev) > overlap:
            result.append(prev[-overlap:] + chunks[i])
        else:
            result.append(chunks[i])
    return result
