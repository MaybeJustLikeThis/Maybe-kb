"""Attachment storage with content-hash deduplication and date-based directories."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

ATTACHMENTS_DIR = "attachments"


def _content_hash(data: bytes) -> str:
    """Short content hash for filename."""
    return hashlib.sha256(data).hexdigest()[:12]


def store_attachment(source: Path, vault_path: Path) -> str:
    """Store an attachment file, returning its relative path.

    Deduplicates by content hash: same content -> same stored file.
    Uses date-based subdirectory: attachments/YYYY/MM/{hash}{ext}
    """
    data = source.read_bytes()
    ext = source.suffix.lower()
    hash_name = _content_hash(data)

    existing_path = _find_existing_attachment(vault_path, hash_name, ext, data)
    if existing_path is not None:
        return existing_path

    now = datetime.now()
    rel_path = f"{ATTACHMENTS_DIR}/{now.year}/{now.month:02d}/{hash_name}{ext}"

    dest = vault_path / rel_path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    return rel_path


def _find_existing_attachment(
    vault_path: Path,
    hash_name: str,
    ext: str,
    data: bytes,
) -> str | None:
    attachments_root = vault_path / ATTACHMENTS_DIR
    if not attachments_root.exists():
        return None

    matches = sorted(attachments_root.rglob(f"{hash_name}{ext}"))
    for path in matches:
        if path.is_file() and path.read_bytes() == data:
            return path.relative_to(vault_path).as_posix()

    return None
