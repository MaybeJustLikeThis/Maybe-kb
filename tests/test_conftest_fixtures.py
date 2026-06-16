"""Smoke tests proving the shared conftest fixtures are usable."""
from pathlib import Path

from kb.data.database import Database
from kb.data.local_repository import LocalMarkdownRepository
from kb.data.models import Note


def test_vault_fixture_creates_dirs(vault: Path):
    assert (vault / "notes").is_dir()
    assert (vault / ".kb").is_dir()


def test_db_fixture_is_initialized(db: Database, vault: Path):
    # initialize() created tables -> a trivial roundtrip works
    assert db is not None
    db.upsert_note(Note(file_id="a.md", title="A", content="x"))
    assert db.get_note("a.md") is not None


def test_local_repo_fixture_over_vault(local_repo: LocalMarkdownRepository, vault: Path):
    written = local_repo.write(Note(file_id="", title="Hello", content="body"))
    assert (vault / written.file_id).is_file()
