"""NoteRepository contract tests (FakeRepository lives in tests/_fakes.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from kb.core.config import KBConfig, RepositoryConfig
from kb.data.local_repository import LocalMarkdownRepository
from kb.data.models import Note
from kb.data.repository import NoteRepository, create_repository

from tests._fakes import FakeRepository

CONTRACT_FACTORIES = [
    pytest.param(lambda tmp: FakeRepository(), id="fake"),
    pytest.param(lambda tmp: LocalMarkdownRepository(tmp, notes_dir="notes"), id="local"),
]


@pytest.mark.parametrize("make_repo", CONTRACT_FACTORIES)
def test_contract_read_missing_raises(tmp_path, make_repo):
    with pytest.raises(FileNotFoundError):
        make_repo(tmp_path).read("notes/missing.md")


@pytest.mark.parametrize("make_repo", CONTRACT_FACTORIES)
def test_contract_write_allocates_file_id_when_empty(tmp_path, make_repo):
    repo = make_repo(tmp_path)
    written = repo.write(Note(file_id="", title="Hello", content="body"))
    assert written.file_id
    assert written.file_hash
    assert repo.discover() == [written.file_id]


@pytest.mark.parametrize("make_repo", CONTRACT_FACTORIES)
def test_contract_delete_roundtrip(tmp_path, make_repo):
    repo = make_repo(tmp_path)
    fid = repo.write(Note(file_id="", title="X", content="x")).file_id
    repo.delete(fid)
    with pytest.raises(FileNotFoundError):
        repo.delete(fid)


@pytest.mark.parametrize("make_repo", CONTRACT_FACTORIES)
def test_contract_hash_detects_change(tmp_path, make_repo):
    repo = make_repo(tmp_path)
    fid = repo.write(Note(file_id="", title="T", content="v1")).file_id
    h1 = repo.hash(fid)
    repo.write(Note(file_id=fid, title="T", content="v2"))
    assert h1 != repo.hash(fid)


@pytest.mark.parametrize("make_repo", CONTRACT_FACTORIES)
def test_contract_supports_write_true(tmp_path, make_repo):
    assert make_repo(tmp_path).supports_write is True


@pytest.mark.parametrize("make_repo", CONTRACT_FACTORIES)
def test_contract_satisfies_protocol(tmp_path, make_repo):
    assert isinstance(make_repo(tmp_path), NoteRepository)


def test_fake_validate_returns_none():
    # Protocol allows non-local backends to return None; Fake pins this semantic.
    assert FakeRepository().validate("notes/anything.md") is None


def _local_repo(tmp_path: Path) -> LocalMarkdownRepository:
    (tmp_path / "notes").mkdir()
    return LocalMarkdownRepository(tmp_path, notes_dir="notes")


def test_local_write_increments_on_name_collision(tmp_path: Path):
    repo = _local_repo(tmp_path)
    a = repo.write(Note(file_id="", title="Dup", content="x"))
    b = repo.write(Note(file_id="", title="Dup", content="y"))
    assert a.file_id != b.file_id
    assert repo.discover() == sorted([a.file_id, b.file_id])


def test_local_validate_rejects_traversal(tmp_path: Path):
    repo = _local_repo(tmp_path)
    assert repo.validate("../outside.md") is None


def test_local_delete_removes_file(tmp_path: Path):
    repo = _local_repo(tmp_path)
    written = repo.write(Note(file_id="", title="Gone", content="x"))
    repo.delete(written.file_id)
    assert not (tmp_path / written.file_id).exists()
    with pytest.raises(FileNotFoundError):
        repo.delete(written.file_id)


# ---------------------------------------------------------------------------
# create_repository factory
# ---------------------------------------------------------------------------


def test_create_repository_local_returns_local_backend(tmp_path: Path):
    cfg = KBConfig(vault_path=tmp_path)
    repo = create_repository(cfg, tmp_path)
    assert isinstance(repo, LocalMarkdownRepository)
    assert isinstance(repo, NoteRepository)


def test_create_repository_unknown_provider_raises(tmp_path: Path):
    cfg = KBConfig(
        vault_path=tmp_path,
        repository=RepositoryConfig(provider="bogus"),
    )
    with pytest.raises(ValueError, match="Unknown repository provider"):
        create_repository(cfg, tmp_path)
