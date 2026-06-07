"""Tests for kb import CLI command."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kb.cli import app

runner = CliRunner()


@pytest.fixture
def kb_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a kb project directory and cd into it."""
    monkeypatch.chdir(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "notes").mkdir()
    (vault / "attachments").mkdir()
    (vault / ".kb").mkdir()

    tmp_path.joinpath("config.toml").write_text(
        f'[general]\nvault_path = "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    return tmp_path


def _write_pdf(path: Path) -> Path:
    """Create a minimal PDF file."""
    pdf_path = path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF")
    return pdf_path


def test_kb_import_success(kb_dir: Path) -> None:
    """kb import creates a note from a PDF file."""
    pdf_path = _write_pdf(kb_dir)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="# Paper Title\n\nContent here.",
            metadata={"converter": "markitdown", "source_file": "paper.pdf"},
        )

        result = runner.invoke(app, ["import", str(pdf_path)])

    assert result.exit_code == 0, result.output
    assert "Created note" in result.output
    assert "paper.md" in result.output


def test_kb_import_with_options(kb_dir: Path) -> None:
    """kb import respects --title, --category, --tags."""
    pdf_path = _write_pdf(kb_dir)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="content",
            metadata={"converter": "markitdown", "source_file": "paper.pdf"},
        )

        result = runner.invoke(app, [
            "import", str(pdf_path),
            "--title", "My Paper",
            "--category", "AI",
            "--tags", "ml,research",
        ])

    assert result.exit_code == 0, result.output


def test_kb_import_file_not_found(kb_dir: Path) -> None:
    """kb import reports error for missing file."""
    result = runner.invoke(app, ["import", str(kb_dir / "nonexistent.pdf")])
    assert result.exit_code != 0
