"""Tests for CLI commands."""
from __future__ import annotations

import tomllib
import shutil
import pytest
from pathlib import Path
from typer.testing import CliRunner
from kb.cli import app

runner = CliRunner()


@pytest.fixture
def kb_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a kb project directory and cd into it."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_external_config(
    project: Path,
    vault: Path,
    *,
    watch_dir: Path | None = None,
    watch_enabled: bool = True,
) -> None:
    watch_line = f'watch_dir = "{watch_dir.as_posix()}"\n' if watch_dir else ""
    project.joinpath("config.toml").write_text(
        "[general]\n"
        f'vault_path = "{vault.as_posix()}"\n'
        'notes_dir = "knowledge"\n'
        'attachments_dir = "media"\n'
        'index_dir = ".index"\n'
        "\n"
        "[server]\n"
        f"watch_enabled = {str(watch_enabled).lower()}\n"
        f"{watch_line}",
        encoding="utf-8",
    )


def test_kb_init(kb_dir: Path):
    """kb init creates directory structure."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (kb_dir / "notes").is_dir()
    assert (kb_dir / "attachments").is_dir()
    assert (kb_dir / "config.toml").exists()
    assert (kb_dir / ".gitignore").exists()


def test_kb_init_import_existing(kb_dir: Path):
    """kb init --import-existing indexes existing .md files."""
    notes_dir = kb_dir / "notes"
    notes_dir.mkdir()
    (notes_dir / "test.md").write_text(
        "---\ntitle: Test\ntags: demo\n---\n\nHello.\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["init", "--import-existing"])
    assert result.exit_code == 0
    assert (kb_dir / ".kb" / "kb.db").exists()


def test_kb_add(kb_dir: Path):
    """kb add creates a new note."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["add", "My Note", "--tags", "test,demo", "--category", "tech"])
    assert result.exit_code == 0

    notes = list((kb_dir / "notes").rglob("*.md"))
    assert len(notes) == 1
    content = notes[0].read_text(encoding="utf-8")
    assert "My Note" in content
    assert "test" in content


def test_kb_list(kb_dir: Path):
    """kb list shows notes."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "Note A", "--tags", "python"])
    runner.invoke(app, ["add", "Note B", "--tags", "go"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Note A" in result.output


def test_kb_search(kb_dir: Path):
    """kb search finds notes by content."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "Vue 状态管理"])
    runner.invoke(app, ["add", "Docker 部署"])

    result = runner.invoke(app, ["search", "状态管理"])
    assert result.exit_code == 0
    assert "Vue" in result.output or "状态管理" in result.output


def test_kb_delete(kb_dir: Path):
    """kb delete removes a note."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "To Delete"])

    notes = list((kb_dir / "notes").rglob("*.md"))
    assert len(notes) == 1
    rel_path = notes[0].relative_to(kb_dir).as_posix()

    result = runner.invoke(app, ["delete", rel_path, "--force"])
    assert result.exit_code == 0

    notes = list((kb_dir / "notes").rglob("*.md"))
    assert len(notes) == 0


def test_kb_tag_add(kb_dir: Path):
    """kb tag adds tags to an existing note."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "Tagged Note", "--tags", "python"])

    notes = list((kb_dir / "notes").rglob("*.md"))
    rel_path = notes[0].relative_to(kb_dir).as_posix()

    result = runner.invoke(app, ["tag", rel_path, "add", "--tags", "fastapi,web"])
    assert result.exit_code == 0

    content = notes[0].read_text(encoding="utf-8")
    assert "fastapi" in content


def test_kb_edit_file_not_found(kb_dir: Path):
    """kb edit exits with error if file doesn't exist."""
    result = runner.invoke(app, ["edit", "nonexistent.md"])
    assert result.exit_code == 1


def test_kb_add_no_collision(kb_dir: Path):
    """kb add with duplicate title gets unique filename."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "Same Title"])
    runner.invoke(app, ["add", "Same Title"])

    notes = sorted((kb_dir / "notes").rglob("*.md"))
    assert len(notes) == 2
    names = {n.name for n in notes}
    assert "same-title.md" in names
    assert "same-title-2.md" in names


def test_kb_serve_help(kb_dir: Path):
    """kb serve has --help."""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output


def test_kb_migrate_dry_run(kb_dir: Path):
    """kb migrate --dry-run shows preview without moving files."""
    import os

    note = kb_dir / "notes" / "test-note.md"
    note.parent.mkdir(exist_ok=True)
    note.write_text(
        "---\ntitle: Test Note\ncategories: tech\n---\n\n# Test\nContent.\n",
        encoding="utf-8",
    )

    os.chdir(kb_dir)
    result = runner.invoke(app, ["migrate", "--dry-run"])

    assert "Would move" in result.stdout
    assert note.exists()


def test_kb_migrate_moves_files(kb_dir: Path):
    """kb migrate moves root-level .md files into category dirs."""
    import os

    note = kb_dir / "notes" / "tech-note.md"
    note.parent.mkdir(exist_ok=True)
    note.write_text(
        "---\ntitle: Tech Note\ncategories: tech\n---\n\n# Tech\nContent.\n",
        encoding="utf-8",
    )

    os.chdir(kb_dir)
    result = runner.invoke(app, ["migrate"])

    assert "Migrated" in result.stdout
    assert not note.exists()
    assert (kb_dir / "notes" / "tech" / "tech-note.md").exists()


def test_kb_migrate_no_category_goes_to_weifenlei(kb_dir: Path):
    """kb migrate puts uncategorized notes under 未分类/."""
    import os

    note = kb_dir / "notes" / "random.md"
    note.parent.mkdir(exist_ok=True)
    note.write_text(
        "---\ntitle: Random\n---\n\n# Random\nContent.\n",
        encoding="utf-8",
    )

    os.chdir(kb_dir)
    result = runner.invoke(app, ["migrate"])

    assert not note.exists()
    assert (kb_dir / "notes" / "未分类" / "random.md").exists()


def test_kb_migrate_idempotent(kb_dir: Path):
    """kb migrate is idempotent."""
    import os

    note = kb_dir / "notes" / "tech" / "existing.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "---\ntitle: Existing\ncategories: tech\n---\n\n# Existing\nContent.\n",
        encoding="utf-8",
    )

    os.chdir(kb_dir)
    result = runner.invoke(app, ["migrate"])

    assert note.exists()
    assert "No root-level notes to migrate" in result.stdout or "Migrated 0" in result.stdout


# ---------------------------------------------------------------------------
# Edge case tests (Task 3.4)
# ---------------------------------------------------------------------------


def test_kb_serve_params(kb_dir: Path):
    """kb serve --help shows host, port, and watch options."""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--watch" in result.stdout


def test_kb_ask_params(kb_dir: Path):
    """kb ask --help shows --top-k and --stream options."""
    result = runner.invoke(app, ["ask", "--help"])
    assert result.exit_code == 0
    assert "--top-k" in result.stdout
    assert "--stream" in result.stdout


def test_kb_ask_no_llm_config(kb_dir: Path):
    """kb ask exits non-zero when no LLM config is set up."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["ask", "test question"])
    assert result.exit_code != 0


def test_kb_migrate_dry_run_init(kb_dir: Path):
    """kb migrate --dry-run after init shows preview for root-level notes."""
    runner.invoke(app, ["init"])
    notes = kb_dir / "notes"
    (notes / "root_note.md").write_text(
        "---\ntitle: Root Note\ncategory: tech\n---\n\nContent.\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["migrate", "--dry-run"])
    assert result.exit_code == 0
    assert "Would move" in result.stdout or "No root-level notes" in result.stdout


def test_kb_migrate_no_notes_dir(kb_dir: Path):
    """kb migrate fails with helpful message when notes/ does not exist."""
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code != 0
    assert "not found" in result.stdout


def test_kb_tag_invalid_action(kb_dir: Path):
    """kb tag with an invalid action name exits non-zero."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "Test Note", "--tags", "demo"])

    notes = list((kb_dir / "notes").rglob("*.md"))
    assert len(notes) == 1
    rel_path = notes[0].relative_to(kb_dir).as_posix()

    result = runner.invoke(
        app, ["tag", rel_path, "invalid", "--tags", "demo"]
    )
    assert result.exit_code != 0
    assert "Unknown action" in result.stdout


def test_kb_search_empty_query(kb_dir: Path):
    """kb search without a query argument exits non-zero."""
    result = runner.invoke(app, ["search"])
    assert result.exit_code != 0


def test_kb_init_in_existing(kb_dir: Path):
    """kb init is idempotent — second init succeeds and config.toml still exists."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (kb_dir / "config.toml").exists()


def test_kb_add_with_source_project(kb_dir: Path):
    """kb add --source-project creates note with correct source."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    result = runner.invoke(app, [
        "add", "CLI Test",
        "--source-project", "manual",
        "--category", "test",
        "--tags", "cli,test",
        "--description", "CLI test note",
        "--source-context", "testing ingest",
    ])
    assert result.exit_code == 0
    assert "Created note:" in result.stdout
    note = next((kb_dir / "notes").rglob("*.md"))
    content = note.read_text(encoding="utf-8")
    assert "source_project: manual" in content
    assert "source_context: testing ingest" in content


def test_kb_add_rejects_empty_title(kb_dir: Path):
    """kb add rejects empty title via ingest validation."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["add", ""])
    assert result.exit_code != 0
    assert "title" in result.stdout.lower()
    assert not list((kb_dir / "notes").rglob("*.md"))


def test_kb_init_import_existing_uses_selected_project_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project = tmp_path / "project"
    vault = tmp_path / "vault"
    project.mkdir()
    vault.joinpath("knowledge").mkdir(parents=True)
    vault.joinpath("knowledge", "existing.md").write_text("# Existing\n", encoding="utf-8")
    write_external_config(project, vault)
    monkeypatch.setattr("kb.core.context.create_embedding_provider", lambda config: None)

    result = runner.invoke(app, ["init", "--path", str(project), "--import-existing"])

    assert result.exit_code == 0, result.output
    assert vault.joinpath(".index", "kb.db").is_file()
    assert vault.joinpath("media").is_dir()
    assert not project.joinpath(".kb").exists()


def test_kb_add_delete_and_tag_use_external_vault(kb_dir: Path):
    vault = kb_dir / "external-vault"
    write_external_config(kb_dir, vault)

    added = runner.invoke(app, ["add", "External Note", "--tags", "one"])
    note = next(vault.joinpath("knowledge").rglob("*.md"))
    file_id = note.relative_to(vault).as_posix()
    assert added.exit_code == 0, added.output
    assert not kb_dir.joinpath("notes").exists()

    tagged = runner.invoke(app, ["tag", file_id, "add", "--tags", "two"])
    assert tagged.exit_code == 0, tagged.output
    assert "two" in note.read_text(encoding="utf-8")

    deleted = runner.invoke(app, ["delete", file_id, "--force"])
    assert deleted.exit_code == 0, deleted.output
    assert not note.exists()


def test_kb_migrate_uses_external_vault_and_configured_notes_dir(
    kb_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = kb_dir / "external-vault"
    note = vault / "knowledge" / "root.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntitle: Root\ncategories: tech\n---\n\nBody.\n",
        encoding="utf-8",
    )
    write_external_config(kb_dir, vault)
    calls = []
    monkeypatch.setattr("kb.core.context.create_embedding_provider", lambda config: None)
    monkeypatch.setattr("kb.cli.index_files", lambda *args, **kwargs: calls.append((args, kwargs)) or (1, 0))

    result = runner.invoke(app, ["migrate"])

    assert result.exit_code == 0, result.output
    assert not note.exists()
    assert vault.joinpath("knowledge", "tech", "root.md").is_file()
    assert calls[0][0][0] == vault.resolve()
    assert calls[0][1]["notes_dir"] == "knowledge"
    assert calls[0][1]["attachments_dir"] == "media"
    assert calls[0][1]["index_dir"] == ".index"


def test_kb_index_uses_external_vault_without_importing_watch_dir(
    kb_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = kb_dir / "external-vault"
    watch_dir = kb_dir / "blog"
    vault.mkdir()
    watch_dir.mkdir()
    write_external_config(kb_dir, vault, watch_dir=watch_dir)
    calls = []
    monkeypatch.setattr("kb.core.context.create_embedding_provider", lambda config: None)
    monkeypatch.setattr("kb.cli.index_files", lambda *args, **kwargs: calls.append((args, kwargs)) or (0, 0))

    result = runner.invoke(app, ["index"])

    assert result.exit_code == 0, result.output
    args, kwargs = calls[0]
    assert args[0] == vault.resolve()
    assert kwargs["notes_dir"] == "knowledge"
    assert kwargs["attachments_dir"] == "media"
    assert kwargs["index_dir"] == ".index"
    assert "external_sources" not in kwargs


def test_kb_serve_watches_notes_and_indexes_configured_vault(
    kb_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = kb_dir / "external-vault"
    notes = vault / "knowledge"
    notes.mkdir(parents=True)
    write_external_config(kb_dir, vault)
    index_calls = []
    watcher_calls = []

    class Observer:
        def stop(self):
            pass

        def join(self):
            pass

    def fake_start_watcher(path, callback, debounce_ms):
        watcher_calls.append((path, callback, debounce_ms))
        return Observer()

    monkeypatch.setattr("kb.core.context.create_embedding_provider", lambda config: None)
    monkeypatch.setattr("kb.server.create_app", lambda config: object())
    monkeypatch.setattr("kb.core.watcher.start_watcher", fake_start_watcher)
    monkeypatch.setattr("kb.cli.index_files", lambda *args, **kwargs: index_calls.append((args, kwargs)) or (0, 0))
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)

    result = runner.invoke(app, ["serve"])
    watcher_calls[0][1]()

    assert result.exit_code == 0, result.output
    assert watcher_calls[0][0] == notes.resolve()
    assert len(index_calls) == 2
    for args, kwargs in index_calls:
        assert args[0] == vault.resolve()
        assert kwargs["notes_dir"] == "knowledge"
        assert kwargs["attachments_dir"] == "media"
        assert kwargs["index_dir"] == ".index"
        assert "external_sources" not in kwargs


def test_kb_serve_does_not_default_watch_when_disabled(
    kb_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = kb_dir / "external-vault"
    vault.joinpath("knowledge").mkdir(parents=True)
    write_external_config(kb_dir, vault, watch_enabled=False)
    monkeypatch.setattr("kb.server.create_app", lambda config: object())
    monkeypatch.setattr(
        "kb.core.watcher.start_watcher",
        lambda *args, **kwargs: pytest.fail("watcher should not start"),
    )
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)

    result = runner.invoke(app, ["serve"])

    assert result.exit_code == 0, result.output


def test_kb_obsidian_init_vault_copies_and_updates_config(
    kb_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_notes = kb_dir / "old-notes"
    source_attachments = kb_dir / "old-attachments"
    target = kb_dir / "Obsidian Vault"
    source_notes.joinpath("topic").mkdir(parents=True)
    source_attachments.mkdir()
    source_notes.joinpath("topic", "note.md").write_text("# Note\n", encoding="utf-8")
    source_attachments.joinpath("image.png").write_bytes(b"image")
    kb_dir.joinpath("config.toml").write_text(
        "# keep this comment\n"
        "[general]\n"
        'vault_path = "."\n'
        'unknown = "keep"\n\n'
        "[search]\nmax_results = 77\n\n"
        "[server]\n"
        'watch_dir = "D:/blog/source"\n\n'
        "[sources.blog]\nlabel = \"Blog\"\n",
        encoding="utf-8",
    )
    index_calls = []
    monkeypatch.setattr("kb.core.context.create_embedding_provider", lambda config: None)
    monkeypatch.setattr("kb.cli.index_files", lambda *args, **kwargs: index_calls.append((args, kwargs)) or (1, 0))

    result = runner.invoke(
        app,
        [
            "obsidian",
            "init-vault",
            "--target",
            str(target),
            "--from-notes",
            str(source_notes),
            "--from-attachments",
            str(source_attachments),
        ],
    )

    assert result.exit_code == 0, result.output
    assert source_notes.joinpath("topic", "note.md").is_file()
    assert source_attachments.joinpath("image.png").is_file()
    assert target.joinpath("notes", "topic", "note.md").is_file()
    assert target.joinpath("attachments", "image.png").read_bytes() == b"image"
    assert target.joinpath(".obsidian").is_dir()
    assert index_calls[0][0][0] == target.resolve()
    text = kb_dir.joinpath("config.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert "# keep this comment" in text
    assert data["search"]["max_results"] == 77
    assert data["server"]["watch_dir"] == "D:/blog/source"
    assert data["sources"]["blog"]["label"] == "Blog"
    assert data["general"]["unknown"] == "keep"
    assert data["general"]["vault_path"] == target.resolve().as_posix()
    assert data["general"]["notes_dir"] == "notes"
    assert data["general"]["attachments_dir"] == "attachments"
    assert data["general"]["index_dir"] == ".kb"
    assert data["obsidian"] == {
        "enabled": True,
        "vault_name": target.name,
        "vault_path": target.resolve().as_posix(),
        "open_uri_strategy": "file",
    }


def test_kb_obsidian_init_vault_skip_index_and_idempotent(kb_dir: Path):
    source_notes = kb_dir / "old-notes"
    source_attachments = kb_dir / "old-attachments"
    target = kb_dir / "vault"
    source_notes.mkdir()
    source_attachments.mkdir()
    source_notes.joinpath("note.md").write_text("# Same\n", encoding="utf-8")

    args = [
        "obsidian",
        "init-vault",
        "--target",
        str(target),
        "--from-notes",
        str(source_notes),
        "--from-attachments",
        str(source_attachments),
        "--skip-index",
    ]
    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert not target.joinpath(".kb").exists()
    assert target.joinpath("notes", "note.md").read_text(encoding="utf-8") == "# Same\n"


def test_kb_obsidian_init_vault_refuses_conflict_without_changing_config(kb_dir: Path):
    source_notes = kb_dir / "old-notes"
    source_attachments = kb_dir / "old-attachments"
    target = kb_dir / "vault"
    source_notes.mkdir()
    source_attachments.mkdir()
    target.joinpath("notes").mkdir(parents=True)
    source_notes.joinpath("note.md").write_text("# Source\n", encoding="utf-8")
    target.joinpath("notes", "note.md").write_text("# Conflict\n", encoding="utf-8")
    config_path = kb_dir / "config.toml"
    original_config = "[general]\nvault_path = \".\"\n"
    config_path.write_text(original_config, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "obsidian",
            "init-vault",
            "--target",
            str(target),
            "--from-notes",
            str(source_notes),
            "--from-attachments",
            str(source_attachments),
            "--skip-index",
        ],
    )

    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
    assert config_path.read_text(encoding="utf-8") == original_config
    assert target.joinpath("notes", "note.md").read_text(encoding="utf-8") == "# Conflict\n"


def test_kb_obsidian_init_vault_preflights_parent_path_conflicts(kb_dir: Path):
    source_notes = kb_dir / "old-notes"
    source_attachments = kb_dir / "old-attachments"
    target = kb_dir / "vault"
    source_notes.joinpath("z").mkdir(parents=True)
    source_attachments.mkdir()
    source_notes.joinpath("a.md").write_text("# A\n", encoding="utf-8")
    source_notes.joinpath("z", "note.md").write_text("# Nested\n", encoding="utf-8")
    target.joinpath("notes").mkdir(parents=True)
    target.joinpath("notes", "z").write_text("not a directory", encoding="utf-8")
    config_path = kb_dir / "config.toml"
    original_config = "[general]\nvault_path = \".\"\n"
    config_path.write_text(original_config, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "obsidian",
            "init-vault",
            "--target",
            str(target),
            "--from-notes",
            str(source_notes),
            "--from-attachments",
            str(source_attachments),
            "--skip-index",
        ],
    )

    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
    assert not target.joinpath("notes", "a.md").exists()
    assert config_path.read_text(encoding="utf-8") == original_config


def test_kb_obsidian_init_vault_refuses_target_inside_sources(kb_dir: Path):
    source_notes = kb_dir / "old-notes"
    source_attachments = kb_dir / "old-attachments"
    target = source_notes / "vault"
    source_notes.mkdir()
    source_attachments.mkdir()
    source_notes.joinpath("note.md").write_text("# Note\n", encoding="utf-8")
    config_path = kb_dir / "config.toml"
    original_config = "[general]\nvault_path = \".\"\n"
    config_path.write_text(original_config, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "obsidian",
            "init-vault",
            "--target",
            str(target),
            "--from-notes",
            str(source_notes),
            "--from-attachments",
            str(source_attachments),
            "--skip-index",
        ],
    )

    assert result.exit_code != 0
    assert "inside" in result.output.lower()
    assert not target.exists()
    assert config_path.read_text(encoding="utf-8") == original_config


def test_kb_obsidian_init_vault_cleans_partial_copies_on_failure(
    kb_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_notes = kb_dir / "old-notes"
    source_attachments = kb_dir / "old-attachments"
    target = kb_dir / "vault"
    source_notes.mkdir()
    source_attachments.mkdir()
    first = source_notes / "a.md"
    second = source_notes / "b.md"
    first.write_text("# A\n", encoding="utf-8")
    second.write_text("# B\n", encoding="utf-8")
    config_path = kb_dir / "config.toml"
    original_config = "[general]\nvault_path = \".\"\n"
    config_path.write_text(original_config, encoding="utf-8")
    real_copy2 = shutil.copy2
    calls = 0

    def flaky_copy2(source: Path, destination: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("partial", encoding="utf-8")
            raise OSError("simulated copy failure")
        return real_copy2(source, destination)

    monkeypatch.setattr("kb.cli.shutil.copy2", flaky_copy2)

    result = runner.invoke(
        app,
        [
            "obsidian",
            "init-vault",
            "--target",
            str(target),
            "--from-notes",
            str(source_notes),
            "--from-attachments",
            str(source_attachments),
            "--skip-index",
        ],
    )

    assert result.exit_code != 0
    assert "copy failure" in result.output
    assert not target.joinpath("notes", "a.md").exists()
    assert not target.joinpath("notes", "b.md").exists()
    assert config_path.read_text(encoding="utf-8") == original_config


def test_kb_mcp_path_loads_project_config(kb_dir: Path, monkeypatch: pytest.MonkeyPatch):
    vault = kb_dir / "external-vault"
    write_external_config(kb_dir, vault)
    configs = []

    class Server:
        def run(self):
            pass

    monkeypatch.setattr(
        "kb.mcp_server.create_mcp_server",
        lambda config: configs.append(config) or Server(),
    )

    result = runner.invoke(app, ["mcp", "--path", str(kb_dir)])

    assert result.exit_code == 0, result.output
    assert configs[0].vault_path == vault.resolve()
