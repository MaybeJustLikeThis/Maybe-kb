"""Parser protocol, registry, and built-in MarkdownParser."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class ParsedContent:
    """Unified output from any parser."""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[Path] = field(default_factory=list)


class Parser(Protocol):
    """Protocol for file parsers."""

    def parse(self, path: Path, *, context_bound: bool = False) -> ParsedContent:
        """Parse a file into ParsedContent."""
        ...


class MarkdownParser:
    """Parse .md files: split frontmatter, return body as text."""

    def parse(self, path: Path, *, context_bound: bool = False) -> ParsedContent:
        from kb.data.storage import _split_frontmatter
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        return ParsedContent(text=body, metadata=frontmatter)


class ParserRegistry:
    """Registry of file-extension -> Parser mappings."""

    _parsers: dict[str, Parser] = {}

    @classmethod
    def register(cls, extension: str, parser: Parser) -> None:
        cls._parsers[extension.lower()] = parser

    @classmethod
    def get(cls, extension: str) -> Parser:
        ext = extension.lower()
        if ext in cls._parsers:
            return cls._parsers[ext]
        raise KeyError(f"No parser registered for '{extension}'")

    @classmethod
    def get_by_filename(cls, filename: str | Path) -> Parser:
        return cls.get(Path(filename).suffix)

    @classmethod
    def _reset(cls) -> None:
        """Clear registry (for testing)."""
        cls._parsers.clear()


# Register built-in parser
ParserRegistry.register(".md", MarkdownParser())
