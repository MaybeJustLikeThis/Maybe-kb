from pathlib import Path

import pytest

from kb.data.local_repository import LocalMarkdownRepository
from kb.data.models import Note
from kb.core.open_targets import (
    FileTarget,
    ObsidianTarget,
    create_open_target,
)
from kb.core.config import KBConfig


def _repo_with_note(tmp_path: Path, fid: str = "notes/x.md") -> LocalMarkdownRepository:
    (tmp_path / "notes").mkdir(parents=True, exist_ok=True)
    repo = LocalMarkdownRepository(tmp_path, notes_dir="notes")
    repo.write(Note(file_id=fid, title="X", content="body"))
    return repo


def test_obsidian_target_builds_uri(tmp_path: Path):
    repo = _repo_with_note(tmp_path)
    target = ObsidianTarget(vault_name="MyVault")
    result = target.build(repo, "notes/x.md")
    assert result["obsidian_uri"].startswith("obsidian://open?")
    assert "vault=MyVault" in result["obsidian_uri"]
    assert result["relative_path"] == "notes/x.md"


def test_file_target_omits_obsidian_uri(tmp_path: Path):
    repo = _repo_with_note(tmp_path)
    target = FileTarget()
    result = target.build(repo, "notes/x.md")
    assert "obsidian_uri" not in result
    assert result["relative_path"] == "notes/x.md"


def test_factory_picks_obsidian_when_enabled(tmp_path: Path):
    from dataclasses import replace
    base = KBConfig(vault_path=tmp_path)
    enabled = replace(base, obsidian=replace(base.obsidian, enabled=True, vault_name="V"))
    assert isinstance(create_open_target(enabled), ObsidianTarget)
    assert isinstance(create_open_target(base), FileTarget)


def test_target_raises_on_missing(tmp_path: Path):
    repo = _repo_with_note(tmp_path)
    with pytest.raises(FileNotFoundError):
        FileTarget().build(repo, "notes/missing.md")


def test_target_raises_value_error_on_traversal(tmp_path: Path):
    repo = _repo_with_note(tmp_path)
    with pytest.raises(ValueError):
        FileTarget().build(repo, "../outside.md")
    with pytest.raises(ValueError):
        ObsidianTarget(vault_name="V").build(repo, "../outside.md")
