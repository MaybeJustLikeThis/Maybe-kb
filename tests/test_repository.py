"""NoteRepository contract tests + in-memory FakeRepository for core-layer tests."""
from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from kb.data.models import Note
from kb.data.repository import NoteRepository


class FakeRepository:
    """In-memory NoteRepository — lets core-layer tests run without a filesystem."""

    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}

    @property
    def supports_write(self) -> bool:
        return True

    def discover(self) -> list[str]:
        return sorted(self._notes)

    def read(self, file_id: str) -> Note:
        if file_id not in self._notes:
            raise FileNotFoundError(file_id)
        return self._notes[file_id]

    def write(self, note: Note) -> Note:
        file_id = note.file_id or f"notes/{note.title.strip() or 'untitled'}.md"
        digest = hashlib.sha256(note.content.encode("utf-8")).hexdigest()
        committed = replace(note, file_id=file_id, file_hash=digest)
        self._notes[file_id] = committed
        return committed

    def delete(self, file_id: str) -> None:
        if file_id not in self._notes:
            raise FileNotFoundError(file_id)
        del self._notes[file_id]

    def hash(self, file_id: str) -> str:
        return self.read(file_id).file_hash or ""

    def validate(self, file_id: str) -> None:
        return None


def _make_note(file_id: str = "", title: str = "T", content: str = "body") -> Note:
    return Note(file_id=file_id, title=title, content=content)


def test_fake_write_allocates_file_id_when_empty():
    repo: NoteRepository = FakeRepository()
    written = repo.write(_make_note(file_id="", title="Hello"))
    assert written.file_id == "notes/Hello.md"
    assert written.file_hash  # repo fills hash
    assert repo.discover() == ["notes/Hello.md"]


def test_fake_read_raises_when_missing():
    repo: NoteRepository = FakeRepository()
    with pytest.raises(FileNotFoundError):
        repo.read("notes/missing.md")


def test_fake_delete_roundtrip():
    repo: NoteRepository = FakeRepository()
    repo.write(_make_note(file_id="notes/x.md"))
    repo.delete("notes/x.md")
    assert repo.discover() == []
    with pytest.raises(FileNotFoundError):
        repo.delete("notes/x.md")


def test_fake_satisfies_protocol():
    # @runtime_checkable Protocol — lock the fake as a contract reference
    assert isinstance(FakeRepository(), NoteRepository)


def test_fake_hash_and_supports_write():
    repo: NoteRepository = FakeRepository()
    assert repo.supports_write is True
    repo.write(_make_note(file_id="notes/h.md", content="abc"))
    assert repo.hash("notes/h.md")


from pathlib import Path

from kb.data.local_repository import LocalMarkdownRepository  # 尚不存在


def _local_repo(tmp_path: Path) -> LocalMarkdownRepository:
    (tmp_path / "notes").mkdir()
    return LocalMarkdownRepository(tmp_path, notes_dir="notes")


def test_local_discover_empty_when_no_notes(tmp_path: Path):
    repo = _local_repo(tmp_path)
    assert repo.discover() == []


def test_local_write_then_read_roundtrip(tmp_path: Path):
    repo = _local_repo(tmp_path)
    written = repo.write(Note(file_id="", title="Hello", content="# Hi\n\nbody"))
    assert written.file_id.startswith("notes/") and written.file_id.endswith(".md")
    assert (tmp_path / written.file_id).is_file()
    note = repo.read(written.file_id)
    assert note.title == "Hello"
    assert repo.discover() == [written.file_id]


def test_local_write_increments_on_name_collision(tmp_path: Path):
    repo = _local_repo(tmp_path)
    a = repo.write(Note(file_id="", title="Dup", content="x"))
    b = repo.write(Note(file_id="", title="Dup", content="y"))
    assert a.file_id != b.file_id
    assert repo.discover() == sorted([a.file_id, b.file_id])


def test_local_hash_detects_change(tmp_path: Path):
    repo = _local_repo(tmp_path)
    written = repo.write(Note(file_id="", title="T", content="v1"))
    h1 = repo.hash(written.file_id)
    repo.write(Note(file_id=written.file_id, title="T", content="v2"))
    h2 = repo.hash(written.file_id)
    assert h1 != h2


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


def test_local_satisfies_protocol(tmp_path: Path):
    # runtime_checkable Protocol — structural check
    assert isinstance(_local_repo(tmp_path), NoteRepository)
