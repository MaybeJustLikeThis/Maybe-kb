"""Attachment storage with content-hash deduplication."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

ATTACHMENTS_DIR = "attachments"


def _content_hash(data: bytes) -> str:
    """Short content hash for filename."""
    return hashlib.sha256(data).hexdigest()[:12]


def store_attachment(source: Path, vault_path: Path) -> str:
    """Store an attachment file, returning its relative path.

    Deduplicates by content hash: same content -> same stored file.
    """
    data = source.read_bytes()
    ext = source.suffix.lower()
    hash_name = _content_hash(data)
    rel_path = f"{ATTACHMENTS_DIR}/{hash_name}{ext}"

    dest = vault_path / rel_path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    return rel_path
