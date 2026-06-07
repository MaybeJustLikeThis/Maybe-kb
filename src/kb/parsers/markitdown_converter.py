"""MarkItDown-based file converter for kb import."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConversionResult:
    """Output from markitdown conversion."""
    text: str
    metadata: dict[str, str]


class MarkItDownNotInstalledError(Exception):
    """Raised when markitdown package is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "markitdown is not installed. "
            "Install it with: pip install 'kb[markitdown]'"
        )


class ConversionError(Exception):
    """Raised when file conversion fails."""


def _get_converter() -> object:
    """Lazily import and return a MarkItDown instance.

    Raises MarkItDownNotInstalledError if the package is missing.
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise MarkItDownNotInstalledError()
    return MarkItDown(enable_plugins=False)


def convert_file(path: Path) -> ConversionResult:
    """Convert a file to Markdown using markitdown.

    Args:
        path: Absolute path to the source file.

    Returns:
        ConversionResult with Markdown text and metadata.

    Raises:
        MarkItDownNotInstalledError: markitdown package not installed.
        ConversionError: conversion failed or produced empty output.
    """
    converter = _get_converter()

    try:
        result = converter.convert(str(path))
    except Exception as exc:
        raise ConversionError(f"Conversion failed: {exc}") from exc

    text = result.text_content or ""
    if not text.strip():
        raise ConversionError(
            f"Conversion produced empty content: {path.name}"
        )

    return ConversionResult(
        text=text,
        metadata={
            "converter": "markitdown",
            "source_file": path.name,
        },
    )
