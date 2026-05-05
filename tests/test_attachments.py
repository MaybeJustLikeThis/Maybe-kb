"""Tests for attachment management."""
import pytest
from pathlib import Path
from kb.attachments import store_attachment


def test_store_attachment(tmp_path: Path):
    """Attachment is copied with content-hash filename."""
    source = tmp_path / "photo.png"
    source.write_bytes(b"\x89PNG fake image data")

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = store_attachment(source, vault_path)
    assert result.startswith("attachments/")
    assert result.endswith(".png")

    stored = vault_path / result
    assert stored.exists()
    assert stored.read_bytes() == b"\x89PNG fake image data"


def test_store_deduplicates(tmp_path: Path):
    """Same content is stored only once."""
    source1 = tmp_path / "a.png"
    source1.write_bytes(b"same content")
    source2 = tmp_path / "b.png"
    source2.write_bytes(b"same content")

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    r1 = store_attachment(source1, vault_path)
    r2 = store_attachment(source2, vault_path)
    assert r1 == r2


def test_store_preserves_extension(tmp_path: Path):
    """Extension is preserved in stored filename."""
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"%PDF fake")

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = store_attachment(source, vault_path)
    assert result.endswith(".pdf")
