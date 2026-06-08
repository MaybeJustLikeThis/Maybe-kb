"""Markdown file reading, writing, and frontmatter parsing."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kb.data.models import Note

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


def discover_notes(vault_path: Path, notes_dir: str = "notes") -> list[Path]:
    """Find all .md files under the configured notes directory."""
    vault_root = vault_path.resolve()
    notes_path = vault_path / notes_dir
    notes_root = notes_path.resolve()
    if not notes_root.is_relative_to(vault_root):
        raise ValueError(f"Configured notes directory escapes the vault: {notes_dir}")
    if not notes_path.exists():
        return []

    discovered: list[Path] = []
    for path in notes_path.rglob("*.md"):
        resolved = path.resolve()
        if resolved.is_relative_to(vault_root) and resolved.is_relative_to(notes_root):
            discovered.append(path)
    return sorted(discovered)


@dataclass(frozen=True)
class Chunk:
    """A semantically coherent text chunk with structural metadata."""
    text: str
    section_path: list[str] = field(default_factory=list)
    content_type: str = "paragraph"
    file_id: str = ""


def _detect_content_type(text: str) -> str:
    """Detect the primary content type of a text block."""
    stripped = text.strip()
    if stripped.startswith("```"):
        return "code"
    lines = stripped.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if non_empty and all(l.strip().startswith(("- ", "* ", "+ ")) for l in non_empty):
        return "list"
    if non_empty and all(l.strip().startswith("|") for l in non_empty):
        return "table"
    return "paragraph"


def _split_at_headings(text: str) -> list[tuple[list[str], str]]:
    """Split markdown text at heading boundaries."""
    lines = text.split("\n")
    sections: list[tuple[list[str], str]] = []
    current_headings: list[str] = []
    current_body_lines: list[str] = []

    for line in lines:
        if re.match(r"^#{1,6}\s+", line.strip()):
            if current_body_lines:
                body = "\n".join(current_body_lines).strip()
                if body:
                    sections.append((list(current_headings), body))
            level = len(line.split()[0])
            while current_headings and len(current_headings[-1].split()[0]) >= level:
                current_headings.pop()
            current_headings.append(line.strip())
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_body_lines:
        body = "\n".join(current_body_lines).strip()
        if body:
            sections.append((list(current_headings), body))

    if not sections:
        stripped = text.strip()
        if stripped:
            sections.append(([], stripped))

    return sections


def chunk_text(
    text: str,
    max_chunk_chars: int = 1000,
    overlap: int = 100,
    file_id: str = "",
    *,
    max_chars: int | None = None,
) -> list[Chunk]:
    """Split markdown text into chunks using recursive strategy."""
    if max_chars is not None:
        max_chunk_chars = max_chars
    if not text or not text.strip():
        return []

    sections = _split_at_headings(text)
    all_chunks: list[Chunk] = []

    for section_path, body in sections:
        chunks = _chunk_section(body, section_path, max_chunk_chars, overlap, file_id)
        all_chunks.extend(chunks)

    if overlap and len(all_chunks) > 1:
        all_chunks = _apply_chunk_overlap(all_chunks, overlap)

    return all_chunks


def _chunk_section(text: str, section_path: list[str], max_chunk_chars: int, overlap: int, file_id: str) -> list[Chunk]:
    """Chunk a single section's body text using recursive strategy."""
    if len(text) <= max_chunk_chars:
        return [Chunk(text=text, section_path=list(section_path), content_type=_detect_content_type(text), file_id=file_id)]

    paragraphs = text.split("\n\n")
    if len(paragraphs) > 1:
        return _chunk_paragraphs(paragraphs, section_path, max_chunk_chars, file_id)

    sentences = re.split(r"(?<=[。！？!?])\s*", text)
    if len(sentences) > 1:
        return _chunk_sentences(sentences, section_path, max_chunk_chars, file_id)

    return _hard_split(text, section_path, max_chunk_chars, file_id)


def _chunk_paragraphs(paragraphs: list[str], section_path: list[str], max_chunk_chars: int, file_id: str) -> list[Chunk]:
    """Group paragraphs into chunks up to max_chunk_chars."""
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_len = len(para)
        if current_len + para_len <= max_chunk_chars:
            current_parts.append(para)
            current_len += para_len
        else:
            if current_parts:
                combined = "\n\n".join(current_parts)
                chunks.append(Chunk(text=combined, section_path=list(section_path), content_type=_detect_content_type(combined), file_id=file_id))
            if para_len > max_chunk_chars:
                sub_chunks = _chunk_section(para, section_path, max_chunk_chars, 0, file_id)
                chunks.extend(sub_chunks)
                current_parts = []
                current_len = 0
            else:
                current_parts = [para]
                current_len = para_len

    if current_parts:
        combined = "\n\n".join(current_parts)
        chunks.append(Chunk(text=combined, section_path=list(section_path), content_type=_detect_content_type(combined), file_id=file_id))

    return chunks


def _chunk_sentences(sentences: list[str], section_path: list[str], max_chunk_chars: int, file_id: str) -> list[Chunk]:
    """Group sentences into chunks up to max_chunk_chars."""
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        s_len = len(sentence)
        if current_len + s_len <= max_chunk_chars:
            current_parts.append(sentence)
            current_len += s_len
        else:
            if current_parts:
                combined = " ".join(current_parts)
                chunks.append(Chunk(text=combined, section_path=list(section_path), content_type=_detect_content_type(combined), file_id=file_id))
            if s_len > max_chunk_chars:
                sub_chunks = _hard_split(sentence, section_path, max_chunk_chars, file_id)
                chunks.extend(sub_chunks)
                current_parts = []
                current_len = 0
            else:
                current_parts = [sentence]
                current_len = s_len

    if current_parts:
        combined = " ".join(current_parts)
        chunks.append(Chunk(text=combined, section_path=list(section_path), content_type=_detect_content_type(combined), file_id=file_id))

    return chunks


def _hard_split(text: str, section_path: list[str], max_chunk_chars: int, file_id: str) -> list[Chunk]:
    """Hard split text at character boundaries as fallback."""
    chunks: list[Chunk] = []
    for i in range(0, len(text), max_chunk_chars):
        segment = text[i:i + max_chunk_chars]
        if segment.strip():
            chunks.append(Chunk(text=segment, section_path=list(section_path), content_type=_detect_content_type(segment), file_id=file_id))
    return chunks


def _apply_chunk_overlap(chunks: list[Chunk], overlap: int) -> list[Chunk]:
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_text = chunks[i - 1].text
        overlap_text = prev_text[-overlap:] if len(prev_text) > overlap else prev_text
        new_chunk = Chunk(text=overlap_text + chunks[i].text, section_path=chunks[i].section_path, content_type=chunks[i].content_type, file_id=chunks[i].file_id)
        result.append(new_chunk)
    return result


def chunk_text_plain(text: str, max_chars: int = 1000, overlap: int = 100) -> list[str]:
    """Plain text chunking (backward compatible). Returns list of strings."""
    return [c.text for c in chunk_text(text, max_chunk_chars=max_chars, overlap=overlap)]
