from pathlib import Path

import pytest

from kb.core.config import KBConfig, ObsidianConfig
from kb.core.open_targets import build_obsidian_open_target


def test_build_obsidian_open_target_encodes_relative_file(tmp_path: Path):
    vault = tmp_path / "ObsidianVault"
    note = vault / "notes" / "AI" / "测试 note(一).md"
    note.parent.mkdir(parents=True)
    note.write_text("# note", encoding="utf-8")
    config = KBConfig(
        vault_path=vault.resolve(),
        obsidian=ObsidianConfig(enabled=True, vault_name="ObsidianVault"),
    )

    target = build_obsidian_open_target(config, "notes/AI/测试 note(一).md")

    assert target["relative_path"] == "notes/AI/测试 note(一).md"
    assert target["file_path"] == note.resolve().as_posix()
    assert target["obsidian_uri"] == (
        "obsidian://open?vault=ObsidianVault&file="
        "notes%2FAI%2F%E6%B5%8B%E8%AF%95%20note%28%E4%B8%80%29.md"
    )


def test_build_obsidian_open_target_blocks_path_traversal(tmp_path: Path):
    config = KBConfig(
        vault_path=(tmp_path / "vault").resolve(),
        obsidian=ObsidianConfig(enabled=True, vault_name="ObsidianVault"),
    )

    with pytest.raises(ValueError, match="Path traversal blocked"):
        build_obsidian_open_target(config, "../secret.md")


def test_build_obsidian_open_target_requires_existing_file(tmp_path: Path):
    config = KBConfig(
        vault_path=(tmp_path / "vault").resolve(),
        obsidian=ObsidianConfig(enabled=True, vault_name="ObsidianVault"),
    )

    with pytest.raises(FileNotFoundError):
        build_obsidian_open_target(config, "notes/missing.md")
