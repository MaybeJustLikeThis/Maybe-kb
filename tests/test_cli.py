"""Tests for CLI commands."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from kb.cli import app

runner = CliRunner()


@pytest.fixture
def kb_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a kb project directory and cd into it."""
    import os
    os.chdir(tmp_path)
    return tmp_path


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
