"""DOCX parser using python-docx."""
from __future__ import annotations

from pathlib import Path

from kb.core.parsers import ParsedContent, ParserRegistry


class DocxParser:
    """Parse .docx files: extract paragraph text with python-docx."""

    def parse(self, path: Path, *, context_bound: bool = False) -> ParsedContent:
        from docx import Document

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        return ParsedContent(
            text=text,
            metadata={"paragraphs": len(paragraphs)},
            attachments=[path],
        )


ParserRegistry.register(".docx", DocxParser())
