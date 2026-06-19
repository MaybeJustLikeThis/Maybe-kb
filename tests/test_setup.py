from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from kb.core.setup import (
    SetupError,
    SetupRequest,
    apply_setup_plan,
    build_setup_plan,
)


def test_obsidian_plan_connects_existing_vault_without_note_mutation(tmp_path: Path):
    project = tmp_path / "project"
    vault = tmp_path / "Obsidian Vault"
    project.mkdir()
    vault.mkdir()
    vault.joinpath(".obsidian").mkdir()
    note = vault / "daily.md"
    note.write_text("# Daily\n", encoding="utf-8")

    plan = build_setup_plan(
        SetupRequest(project_path=project, mode="obsidian", source_path=vault)
    )

    assert plan.vault_path == vault.resolve()
    assert plan.notes_dir == "."
    assert plan.attachments_dir == "attachments"
    assert plan.index_dir == ".kb"
    assert plan.config_updates["general"]["vault_path"] == vault.resolve().as_posix()
    assert plan.config_updates["general"]["notes_dir"] == "."
    assert plan.config_updates["obsidian"]["enabled"] is True
    assert plan.config_updates["obsidian"]["vault_name"] == "Obsidian Vault"
    assert plan.config_updates["obsidian"]["vault_path"] == vault.resolve().as_posix()
    assert note.read_text(encoding="utf-8") == "# Daily\n"


def test_markdown_plan_connects_existing_folder_without_obsidian(tmp_path: Path):
    project = tmp_path / "project"
    notes = tmp_path / "notes-folder"
    project.mkdir()
    notes.mkdir()
    notes.joinpath("note.md").write_text("# Note\n", encoding="utf-8")

    plan = build_setup_plan(
        SetupRequest(project_path=project, mode="markdown", source_path=notes)
    )

    assert plan.vault_path == notes.resolve()
    assert plan.notes_dir == "."
    assert plan.config_updates["general"]["vault_path"] == notes.resolve().as_posix()
    assert plan.config_updates["general"]["notes_dir"] == "."
    assert plan.config_updates["obsidian"]["enabled"] is False
    assert plan.config_updates["obsidian"]["vault_name"] == ""
    assert plan.config_updates["obsidian"]["vault_path"] == ""


def test_new_plan_creates_tidy_empty_vault_defaults(tmp_path: Path):
    project = tmp_path / "project"
    target = tmp_path / "new-vault"
    project.mkdir()

    plan = build_setup_plan(
        SetupRequest(project_path=project, mode="new", source_path=target)
    )

    assert plan.vault_path == target.resolve()
    assert plan.notes_dir == "notes"
    assert plan.attachments_dir == "attachments"
    assert plan.index_dir == ".kb"
    assert target.resolve() in plan.directories_to_create
    assert (target / "notes").resolve() in plan.directories_to_create
    assert (target / "attachments").resolve() in plan.directories_to_create
    assert (target / ".kb").resolve() in plan.directories_to_create


def test_setup_rejects_missing_existing_source_before_writing_config(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    config = project / "config.toml"
    missing = tmp_path / "missing"

    with pytest.raises(SetupError, match="Source directory not found"):
        build_setup_plan(
            SetupRequest(project_path=project, mode="markdown", source_path=missing)
        )

    assert not config.exists()


def test_apply_plan_preserves_config_and_does_not_rewrite_notes(tmp_path: Path):
    project = tmp_path / "project"
    vault = tmp_path / "vault"
    project.mkdir()
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("# Original\n", encoding="utf-8")
    project.joinpath("config.toml").write_text(
        "# keep comment\n"
        "[general]\n"
        'vault_path = "."\n'
        'custom = "keep"\n'
        "\n"
        "[search]\n"
        "max_results = 7\n",
        encoding="utf-8",
    )

    plan = build_setup_plan(
        SetupRequest(project_path=project, mode="markdown", source_path=vault)
    )
    result = apply_setup_plan(plan, build_index=False)

    text = project.joinpath("config.toml").read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert result.indexed_notes is None
    assert result.indexed_vectors is None
    assert "# keep comment" in text
    assert parsed["search"]["max_results"] == 7
    assert parsed["general"]["custom"] == "keep"
    assert parsed["general"]["vault_path"] == vault.resolve().as_posix()
    assert parsed["general"]["notes_dir"] == "."
    assert note.read_text(encoding="utf-8") == "# Original\n"
    assert vault.joinpath("attachments").is_dir()
    assert vault.joinpath(".kb").is_dir()
