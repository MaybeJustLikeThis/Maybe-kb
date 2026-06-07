"""Tests for markitdown converter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kb.parsers.markitdown_converter import (
    ConversionError,
    MarkItDownNotInstalledError,
    convert_file,
)


def test_convert_file_returns_text(tmp_path: Path) -> None:
    """convert_file returns Markdown text from a file."""
    fake_result = MagicMock()
    fake_result.text_content = "# Converted\n\nHello from PDF."

    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake_result
        mock_get.return_value = mock_converter

        result = convert_file(tmp_path / "test.pdf")

    assert result.text == "# Converted\n\nHello from PDF."
    assert result.metadata["converter"] == "markitdown"
    assert result.metadata["source_file"] == "test.pdf"


def test_convert_file_extracts_source_filename(tmp_path: Path) -> None:
    """Metadata contains the original filename."""
    fake_result = MagicMock()
    fake_result.text_content = "content"

    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake_result
        mock_get.return_value = mock_converter

        result = convert_file(tmp_path / "my-report.docx")

    assert result.metadata["source_file"] == "my-report.docx"


def test_convert_file_raises_on_empty_content(tmp_path: Path) -> None:
    """Empty conversion result raises ConversionError."""
    fake_result = MagicMock()
    fake_result.text_content = "   "

    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.return_value = fake_result
        mock_get.return_value = mock_converter

        with pytest.raises(ConversionError, match="empty"):
            convert_file(tmp_path / "blank.pdf")


def test_convert_file_raises_on_converter_exception(tmp_path: Path) -> None:
    """markitdown exceptions are wrapped in ConversionError."""
    with patch("kb.parsers.markitdown_converter._get_converter") as mock_get:
        mock_converter = MagicMock()
        mock_converter.convert.side_effect = RuntimeError("boom")
        mock_get.return_value = mock_converter

        with pytest.raises(ConversionError, match="boom"):
            convert_file(tmp_path / "broken.pdf")


def test_convert_file_raises_not_installed(tmp_path: Path) -> None:
    """Missing markitdown package raises MarkItDownNotInstalledError."""
    with patch(
        "kb.parsers.markitdown_converter._get_converter",
        side_effect=MarkItDownNotInstalledError(),
    ):
        with pytest.raises(MarkItDownNotInstalledError):
            convert_file(tmp_path / "test.pdf")
