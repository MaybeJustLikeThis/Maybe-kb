"""Tests for file converter (markitdown_converter module)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kb.parsers.markitdown_converter import (
    ConversionError,
    ConversionResult,
    MarkItDownNotInstalledError,
    _convert_markitdown,
    convert_file,
)


class TestConvertPdfPrimary:
    """PDF conversion uses PyMuPDF as primary strategy."""

    def test_pdf_uses_pymupdf(self, tmp_path: Path) -> None:
        """Real PDF is converted via PyMuPDF."""
        pdf = tmp_path / "test.pdf"
        # Create a minimal PDF with fitz
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World")
        doc.save(str(pdf))
        doc.close()

        result = convert_file(pdf)

        assert result.converter_used == "pymupdf"
        assert "Hello World" in result.text

    def test_pdf_falls_back_to_markitdown(self, tmp_path: Path) -> None:
        """When PyMuPDF fails, falls back to markitdown."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"not a real pdf")

        fake_result = MagicMock()
        fake_result.text_content = "# Fallback content"

        with patch("kb.parsers.markitdown_converter._convert_pdf_pymupdf",
                   side_effect=ConversionError("bad pdf")):
            with patch("kb.parsers.markitdown_converter._get_markitdown") as mock_get:
                mock_converter = MagicMock()
                mock_converter.convert.return_value = fake_result
                mock_get.return_value = mock_converter

                result = convert_file(pdf)

        assert result.converter_used == "markitdown"
        assert "Fallback" in result.text


class TestConvertNonPdf:
    """Non-PDF files use markitdown directly."""

    def test_docx_uses_markitdown(self, tmp_path: Path) -> None:
        """DOCX files go through markitdown."""
        docx = tmp_path / "test.docx"
        docx.write_bytes(b"fake docx")

        fake_result = MagicMock()
        fake_result.text_content = "# Document content"

        with patch("kb.parsers.markitdown_converter._get_markitdown") as mock_get:
            mock_converter = MagicMock()
            mock_converter.convert.return_value = fake_result
            mock_get.return_value = mock_converter

            result = convert_file(docx)

        assert result.converter_used == "markitdown"
        assert result.metadata["source_file"] == "test.docx"


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_content_raises(self, tmp_path: Path) -> None:
        """Empty conversion result raises ConversionError."""
        pdf = tmp_path / "blank.pdf"
        import fitz
        doc = fitz.open()
        doc.new_page()  # blank page
        doc.save(str(pdf))
        doc.close()

        # PyMuPDF produces empty text for blank page, markitdown also empty
        fake_result = MagicMock()
        fake_result.text_content = "   "

        with patch("kb.parsers.markitdown_converter._convert_pdf_pymupdf",
                   side_effect=ConversionError("empty")):
            with patch("kb.parsers.markitdown_converter._get_markitdown") as mock_get:
                mock_converter = MagicMock()
                mock_converter.convert.return_value = fake_result
                mock_get.return_value = mock_converter

                with pytest.raises(ConversionError, match="empty"):
                    convert_file(pdf)

    def test_markitdown_not_installed(self, tmp_path: Path) -> None:
        """Missing markitdown raises MarkItDownNotInstalledError."""
        docx = tmp_path / "test.docx"
        docx.write_bytes(b"fake")

        with patch("kb.parsers.markitdown_converter._get_markitdown",
                   side_effect=MarkItDownNotInstalledError()):
            with pytest.raises(MarkItDownNotInstalledError):
                _convert_markitdown(docx)

    def test_converter_cached(self) -> None:
        """MarkItDown instance is cached across calls."""
        import kb.parsers.markitdown_converter as mod
        # Reset cache
        mod._markitdown_instance = None

        fake_cls = MagicMock()
        with patch.dict("sys.modules", {"markitdown": MagicMock(MarkItDown=fake_cls)}):
            from kb.parsers.markitdown_converter import _get_markitdown
            _get_markitdown()
            _get_markitdown()

        assert fake_cls.call_count == 1  # only created once
