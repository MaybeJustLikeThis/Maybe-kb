"""Tests for parser registry and MarkdownParser."""
import pytest
from pathlib import Path
from kb.core.parsers import Parser, ParsedContent, ParserRegistry, MarkdownParser


def test_parsed_content_is_frozen():
    """ParsedContent is immutable."""
    pc = ParsedContent(text="hello", metadata={"pages": 1}, attachments=[])
    assert pc.text == "hello"
    assert pc.metadata == {"pages": 1}


def test_markdown_parser_parses_file(tmp_path: Path):
    """MarkdownParser extracts frontmatter and body."""
    md = tmp_path / "test.md"
    md.write_text("---\ntitle: Hello\ntags: [a, b]\n---\n\n# Content\n\nBody text.", encoding="utf-8")

    parser = MarkdownParser()
    result = parser.parse(md)

    assert "# Content" in result.text
    assert "Body text" in result.text
    assert result.metadata["title"] == "Hello"
    assert result.metadata["tags"] == ["a", "b"]


def test_markdown_parser_no_frontmatter(tmp_path: Path):
    """MarkdownParser handles files without frontmatter."""
    md = tmp_path / "plain.md"
    md.write_text("# Just a heading\n\nSome content.", encoding="utf-8")

    parser = MarkdownParser()
    result = parser.parse(md)

    assert "Just a heading" in result.text
    assert "Some content" in result.text


def test_parser_registry_returns_correct_parser():
    """ParserRegistry returns parser by extension."""
    assert isinstance(ParserRegistry.get(".md"), MarkdownParser)
    assert isinstance(ParserRegistry.get(".MD"), MarkdownParser)


def test_parser_registry_raises_for_unknown_extension():
    """ParserRegistry raises KeyError for unregistered extensions."""
    with pytest.raises(KeyError):
        ParserRegistry.get(".xyz")


def test_parser_registry_register_custom_parser():
    """Custom parsers can be registered."""
    class FakeParser:
        def parse(self, path, *, context_bound=False):
            return ParsedContent(text="fake", metadata={}, attachments=[])

    ParserRegistry.register(".fake", FakeParser())
    assert isinstance(ParserRegistry.get(".fake"), FakeParser)
