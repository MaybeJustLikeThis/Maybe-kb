"""Image parser with context_bound support."""
from __future__ import annotations

from pathlib import Path

from kb.core.parsers import ParsedContent, ParserRegistry


class ImageParser:
    """Parse image files. Multi-modal/OCR deferred to future iteration.

    context_bound=True: no independent description generated (inline images).
    context_bound=False: generates markdown image reference as placeholder.
    """

    def parse(self, path: Path, *, context_bound: bool = False) -> ParsedContent:
        if context_bound:
            return ParsedContent(
                text="",
                metadata={"context_bound": True},
                attachments=[path],
            )

        filename = path.name
        return ParsedContent(
            text=f"![{filename}]({filename})",
            metadata={},
            attachments=[path],
        )


for _ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]:
    ParserRegistry.register(_ext, ImageParser())
