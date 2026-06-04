"""Tests for attachment management."""
import hashlib
from datetime import datetime
import pytest
from pathlib import Path
from kb.data.attachments import store_attachment


def _symlink_or_skip(link: Path, target: Path, *, is_directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=is_directory)
    except OSError as exc:
        if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 1314:
            pytest.skip(f"symlink creation is not permitted: {exc}")
        raise


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


def test_store_attachment_uses_date_dirs(tmp_path: Path):
    """store_attachment saves to attachments/YYYY/MM/ subdirectory."""
    source = tmp_path / "test.png"
    source.write_bytes(b"fake-png-data-123")

    vault = tmp_path / "vault"
    vault.mkdir()
    rel = store_attachment(source, vault)

    assert rel.startswith("attachments/")
    parts = rel.split("/")
    assert len(parts) == 4  # attachments / YYYY / MM / filename
    assert parts[1].isdigit() and len(parts[1]) == 4
    assert parts[2].isdigit() and len(parts[2]) == 2
    assert (vault / rel).is_file()


def test_store_attachment_deduplication(tmp_path: Path):
    """Same content → same stored file, not duplicated."""
    source = tmp_path / "img.png"
    source.write_bytes(b"unique-data")

    vault = tmp_path / "vault"
    vault.mkdir()

    rel1 = store_attachment(source, vault)
    rel2 = store_attachment(source, vault)
    assert rel1 == rel2
    files = list((vault / "attachments").rglob("*"))
    file_count = sum(1 for f in files if f.is_file())
    assert file_count == 1


def test_store_preserves_extension(tmp_path: Path):
    """Extension is preserved in stored filename."""
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"%PDF fake")

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    result = store_attachment(source, vault_path)
    assert result.endswith(".pdf")


def test_store_attachment_uses_configured_attachments_dir(tmp_path: Path):
    source = tmp_path / "photo.png"
    source.write_bytes(b"custom attachment path")
    vault = tmp_path / "vault"
    vault.mkdir()

    first = store_attachment(source, vault, attachments_dir="files")
    second = store_attachment(source, vault, attachments_dir="files")

    assert first == second
    assert first.startswith("files/")
    assert (vault / first).read_bytes() == b"custom attachment path"
    assert not (vault / "attachments").exists()


def test_store_attachment_rejects_final_destination_outside_vault_via_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls) -> datetime:
            return cls(2026, 6, 4)

    monkeypatch.setattr("kb.data.attachments.datetime", FrozenDateTime)
    source = tmp_path / "photo.png"
    data = b"outside destination"
    source.write_bytes(data)
    vault = tmp_path / "vault"
    month_parent = vault / "attachments" / "2026"
    month_parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    _symlink_or_skip(month_parent / "06", outside, is_directory=True)
    hash_name = hashlib.sha256(data).hexdigest()[:12]

    with pytest.raises(ValueError, match="escapes the vault"):
        store_attachment(source, vault)

    assert not (outside / f"{hash_name}.png").exists()


def test_store_attachment_does_not_dedupe_to_symlink_outside_vault(tmp_path: Path):
    data = b"outside dedupe"
    source = tmp_path / "photo.png"
    source.write_bytes(data)
    vault = tmp_path / "vault"
    old_dir = vault / "attachments" / "old"
    old_dir.mkdir(parents=True)
    outside = tmp_path / "outside.png"
    outside.write_bytes(data)
    hash_name = hashlib.sha256(data).hexdigest()[:12]
    unsafe_link = old_dir / f"{hash_name}.png"
    _symlink_or_skip(unsafe_link, outside, is_directory=False)

    result = store_attachment(source, vault)

    assert (vault / result).resolve().is_relative_to(vault.resolve())
    assert result != unsafe_link.relative_to(vault).as_posix()
