"""Tests for import_file function."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kb.core.import_file import (
    ImportFileError,
    import_file,
)
from kb.parsers.markitdown_converter import ConversionError


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Create a mock AppContext with all needed attributes."""
    ctx = MagicMock()
    ctx.vault = Path("/vault")
    ctx.db = MagicMock()
    ctx.notes_dir = "notes"
    ctx.attachments_dir = "attachments"
    ctx.config = MagicMock()
    ctx.config.sources = {}
    return ctx


def _write_pdf(path: Path) -> Path:
    """Create a minimal PDF file for testing."""
    pdf_path = path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF")
    return pdf_path


def test_import_file_success(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Successful import stores attachment and creates a note."""
    pdf_path = _write_pdf(tmp_path)

    mock_note = MagicMock()
    mock_note.file_id = "notes/未分类/test.md"

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
        patch("kb.core.import_file.ingest") as mock_ingest,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="# Converted\n\nContent",
            metadata={"converter": "markitdown", "source_file": "test.pdf"},
        )
        mock_ingest.return_value = mock_note

        result = import_file(
            pdf_path,
            vault=mock_ctx.vault,
            db=mock_ctx.db,
            notes_dir=mock_ctx.notes_dir,
            attachments_dir=mock_ctx.attachments_dir,
        )

    assert result.file_id == "notes/未分类/test.md"

    # Verify IngestRequest was assembled correctly
    call_args = mock_ingest.call_args
    req = call_args[0][0]
    assert req.title == "test"
    assert req.source_project == "imported"
    assert req.content_type == "pdf"
    assert req.source_path == "attachments/2026/06/abc123.pdf"
    assert req.attachments == ["attachments/2026/06/abc123.pdf"]
    assert req.extra_frontmatter["source_file"] == "test.pdf"


def test_import_file_custom_title_and_category(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Title and category can be overridden."""
    pdf_path = _write_pdf(tmp_path)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
        patch("kb.core.import_file.ingest") as mock_ingest,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.return_value = MagicMock(
            text="content", metadata={"converter": "markitdown", "source_file": "test.pdf"},
        )
        mock_ingest.return_value = MagicMock(file_id="notes/AI/paper.md")

        import_file(
            pdf_path,
            vault=mock_ctx.vault,
            db=mock_ctx.db,
            notes_dir=mock_ctx.notes_dir,
            attachments_dir=mock_ctx.attachments_dir,
            title="My Paper",
            category="AI",
        )

    req = mock_ingest.call_args[0][0]
    assert req.title == "My Paper"
    assert req.category == "AI"


def test_import_file_stores_attachment_before_convert(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Attachment is stored even if conversion fails."""
    pdf_path = _write_pdf(tmp_path)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        mock_convert.side_effect = ConversionError("conversion crashed")

        with pytest.raises(ImportFileError, match="conversion crashed"):
            import_file(
                pdf_path,
                vault=mock_ctx.vault,
                db=mock_ctx.db,
                notes_dir=mock_ctx.notes_dir,
                attachments_dir=mock_ctx.attachments_dir,
            )

    # Attachment was stored
    mock_store.assert_called_once()


def test_import_file_not_installed(tmp_path: Path, mock_ctx: MagicMock) -> None:
    """Clear error when markitdown is not installed."""
    pdf_path = _write_pdf(tmp_path)

    with (
        patch("kb.core.import_file.store_attachment") as mock_store,
        patch("kb.core.import_file.convert_file") as mock_convert,
    ):
        mock_store.return_value = "attachments/2026/06/abc123.pdf"
        from kb.parsers.markitdown_converter import MarkItDownNotInstalledError
        mock_convert.side_effect = MarkItDownNotInstalledError()

        with pytest.raises(ImportFileError, match="markitdown"):
            import_file(
                pdf_path,
                vault=mock_ctx.vault,
                db=mock_ctx.db,
                notes_dir=mock_ctx.notes_dir,
                attachments_dir=mock_ctx.attachments_dir,
            )
