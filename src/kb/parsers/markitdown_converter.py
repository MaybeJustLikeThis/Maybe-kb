"""File-to-Markdown converter with multi-strategy support.

Conversion strategy by file type:
- PDF:  PyMuPDF HTML+unescape (primary) → markitdown (fallback)
- Other: markitdown (DOCX, CSV, XLSX, etc.)

PyMuPDF handles CJK fonts with custom encodings correctly because it
returns Unicode HTML entities; markitdown sometimes produces garbled
output for such PDFs.
"""
from __future__ import annotations

import html as _html
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversionResult:
    """Output from file conversion."""
    text: str
    metadata: dict[str, str]
    converter_used: str  # "pymupdf" | "markitdown"


class MarkItDownNotInstalledError(Exception):
    """Raised when markitdown package is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "markitdown is not installed. "
            "Install it with: pip install 'kb[markitdown]'"
        )


class ConversionError(Exception):
    """Raised when file conversion fails."""


# ---------------------------------------------------------------------------
# PyMuPDF strategy (PDF only)
# ---------------------------------------------------------------------------

def _convert_pdf_pymupdf(path: Path) -> ConversionResult:
    """Extract text from PDF using PyMuPDF HTML mode.

    Uses page.get_text("html") which preserves Unicode for CJK fonts
    that encode characters as HTML entities (&#xNNNNN;), then decodes
    them with html.unescape().
    """
    import fitz

    doc = fitz.open(str(path))
    pages: list[str] = []
    for page in doc:
        raw = page.get_text("html")
        spans = re.findall(r"<span[^>]*>([^<]+)</span>", raw)
        decoded = [_html.unescape(s) for s in spans if s.strip()]
        if decoded:
            pages.append(" ".join(decoded))
    doc.close()

    text = "\n\n".join(pages)
    text = re.sub(r" {2,}", " ", text)

    if not text.strip():
        raise ConversionError(f"PyMuPDF produced empty content: {path.name}")

    return ConversionResult(
        text=text,
        metadata={"source_file": path.name, "pages": str(len(pages))},
        converter_used="pymupdf",
    )


# ---------------------------------------------------------------------------
# markitdown strategy (any format)
# ---------------------------------------------------------------------------

_markitdown_instance: object | None = None


def _get_markitdown() -> object:
    """Return a cached MarkItDown instance."""
    global _markitdown_instance
    if _markitdown_instance is not None:
        return _markitdown_instance
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise MarkItDownNotInstalledError()
    _markitdown_instance = MarkItDown(enable_plugins=False)
    return _markitdown_instance


def _convert_markitdown(path: Path) -> ConversionResult:
    """Convert any file via markitdown."""
    converter = _get_markitdown()
    try:
        result = converter.convert(str(path))
    except Exception as exc:
        raise ConversionError(f"Conversion failed: {exc}") from exc

    text = result.text_content or ""
    if not text.strip():
        raise ConversionError(f"Conversion produced empty content: {path.name}")

    return ConversionResult(
        text=text,
        metadata={"source_file": path.name},
        converter_used="markitdown",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_file(path: Path) -> ConversionResult:
    """Convert a file to Markdown.

    Strategy selection:
    - PDF  → PyMuPDF (primary), markitdown (fallback)
    - Other → markitdown

    Returns ConversionResult with text, metadata, and converter_used.

    Raises:
        ConversionError: all strategies failed or produced empty output.
        MarkItDownNotInstalledError: markitdown needed but not installed.
    """
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        # Primary: PyMuPDF
        try:
            return _convert_pdf_pymupdf(path)
        except ImportError:
            logger.warning("PyMuPDF not available for PDF, falling back to markitdown")
        except ConversionError:
            logger.warning("PyMuPDF produced empty output for %s, trying markitdown", path.name)
        except Exception as exc:
            logger.warning("PyMuPDF failed for %s: %s, trying markitdown", path.name, exc)

        # Fallback: markitdown
        return _convert_markitdown(path)

    # Non-PDF: markitdown only
    return _convert_markitdown(path)
