"""PDF parser using PyMuPDF (fitz)."""
from __future__ import annotations

from pathlib import Path

from kb.core.parsers import ParsedContent, ParserRegistry


class PDFParser:
    """Parse .pdf files: extract text with PyMuPDF."""

    def parse(self, path: Path, *, context_bound: bool = False) -> ParsedContent:
        import fitz

        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()

        text = "\n\n".join(pages)
        return ParsedContent(
            text=text,
            metadata={"pages": len(pages)},
            attachments=[path],
        )


ParserRegistry.register(".pdf", PDFParser())
