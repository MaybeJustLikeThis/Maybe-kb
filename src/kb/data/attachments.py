"""Attachment storage with content-hash deduplication and date-based directories."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

ATTACHMENTS_DIR = "attachments"
_ARTICLE_NAME_RE = re.compile(r"^[^./\\][^/\\]*$")


def _validate_article_name(name: str) -> None:
    """Reject article names that could escape the directory."""
    if not _ARTICLE_NAME_RE.match(name) or ".." in name:
        raise ValueError(f"Unsafe article name: {name}")


def _content_hash(data: bytes) -> str:
    """Short content hash for filename."""
    return hashlib.sha256(data).hexdigest()[:12]


def store_attachment(
    source: Path,
    vault_path: Path,
    *,
    attachments_dir: str = ATTACHMENTS_DIR,
    article_name: str | None = None,
) -> str:
    """Store an attachment file, returning its relative path.

    Deduplicates by content hash: same content -> same stored file.
    Uses date-based subdirectory: {attachments_dir}/YYYY/MM/{hash}{ext}
    When *article_name* is given the path becomes:
        {attachments_dir}/YYYY/MM/{article_name}/{hash}{ext}
    """
    data = source.read_bytes()
    ext = source.suffix.lower()
    hash_name = _content_hash(data)

    if article_name is not None:
        _validate_article_name(article_name)

    attachments_root = _resolve_attachments_root(vault_path, attachments_dir)
    existing_path = _find_existing_attachment(
        vault_path,
        hash_name,
        ext,
        data,
        attachments_dir=attachments_dir,
    )
    if existing_path is not None:
        return existing_path

    now = datetime.now()
    month_dir = attachments_root / str(now.year) / f"{now.month:02d}"
    if article_name is not None:
        dest = month_dir / article_name / f"{hash_name}{ext}"
    else:
        dest = month_dir / f"{hash_name}{ext}"
    resolved_dest = _resolve_attachment_path(
        dest,
        vault_root=vault_path.resolve(),
        attachments_root=attachments_root,
    )
    if not resolved_dest.exists():
        resolved_dest.parent.mkdir(parents=True, exist_ok=True)
        resolved_dest.write_bytes(data)

    return resolved_dest.relative_to(vault_path.resolve()).as_posix()


def _find_existing_attachment(
    vault_path: Path,
    hash_name: str,
    ext: str,
    data: bytes,
    *,
    attachments_dir: str = ATTACHMENTS_DIR,
) -> str | None:
    vault_root = vault_path.resolve()
    attachments_root = _resolve_attachments_root(vault_path, attachments_dir)
    if not attachments_root.exists():
        return None

    matches = sorted(attachments_root.rglob(f"{hash_name}{ext}"))
    for path in matches:
        try:
            resolved_path = _resolve_attachment_path(
                path,
                vault_root=vault_root,
                attachments_root=attachments_root,
            )
        except ValueError:
            continue
        if resolved_path.is_file() and resolved_path.read_bytes() == data:
            return resolved_path.relative_to(vault_root).as_posix()

    return None


def _resolve_attachments_root(vault_path: Path, attachments_dir: str) -> Path:
    vault_root = vault_path.resolve()
    attachments_root = (vault_path / attachments_dir).resolve()
    if not attachments_root.is_relative_to(vault_root):
        raise ValueError(
            f"Configured attachments directory escapes the vault: {attachments_dir}"
        )
    return attachments_root


def _resolve_attachment_path(
    path: Path,
    *,
    vault_root: Path,
    attachments_root: Path,
) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(vault_root):
        raise ValueError(f"Attachment path escapes the vault: {path}")
    if not resolved.is_relative_to(attachments_root):
        raise ValueError(f"Attachment path escapes the configured directory: {path}")
    return resolved
