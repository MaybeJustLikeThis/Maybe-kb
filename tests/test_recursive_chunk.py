"""Tests for recursive markdown-aware chunking."""
from kb.data.storage import chunk_text, Chunk


def test_empty_text_returns_empty():
    assert chunk_text("") == []


def test_short_text_returns_single_chunk():
    chunks = chunk_text("Hello world")
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world"


def test_splits_on_heading():
    md = "# Title\n\nIntro text.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
    chunks = chunk_text(md, max_chunk_chars=200)
    assert len(chunks) >= 2
    section_paths = [c.section_path for c in chunks]
    assert any("## Section A" in sp for sp in section_paths)
    assert any("## Section B" in sp for sp in section_paths)


def test_section_path_includes_parent_headings():
    md = "# Doc\n\n## Chapter 1\n\n### Detail\n\nSome content here."
    chunks = chunk_text(md, max_chunk_chars=200)
    detail_chunks = [c for c in chunks if "### Detail" in c.section_path]
    assert len(detail_chunks) >= 1
    assert "# Doc" in detail_chunks[0].section_path
    assert "## Chapter 1" in detail_chunks[0].section_path


def test_content_type_code_block():
    md = "## Code\n\n```python\nprint('hello')\nprint('world')\n```"
    chunks = chunk_text(md, max_chunk_chars=200)
    code_chunks = [c for c in chunks if c.content_type == "code"]
    assert len(code_chunks) >= 1


def test_content_type_list():
    md = "## Items\n\n- item one\n- item two\n- item three"
    chunks = chunk_text(md, max_chunk_chars=200)
    list_chunks = [c for c in chunks if c.content_type == "list"]
    assert len(list_chunks) >= 1


def test_content_type_paragraph():
    md = "## Section\n\nJust a normal paragraph of text."
    chunks = chunk_text(md, max_chunk_chars=200)
    para_chunks = [c for c in chunks if c.content_type == "paragraph"]
    assert len(para_chunks) >= 1


def test_long_paragraph_splits_on_sentences():
    sentences = ["这是一个测试句子。" * 5] * 10
    md = "## Long\n\n" + "".join(sentences)
    chunks = chunk_text(md, max_chunk_chars=300)
    assert len(chunks) >= 2


def test_overlap_between_chunks():
    md = "## S1\n\n" + "A" * 800 + "\n\n## S2\n\n" + "B" * 800
    chunks = chunk_text(md, max_chunk_chars=1000, overlap=100)
    if len(chunks) >= 2:
        assert len(chunks) > 1


def test_max_chunk_chars_respected():
    md = "## S\n\n" + "x" * 500 + "\n\n" + "y" * 500
    chunks = chunk_text(md, max_chunk_chars=600)
    for c in chunks:
        assert len(c.text) <= 700


def test_chunk_has_file_id():
    chunks = chunk_text("Hello", file_id="notes/test.md")
    assert chunks[0].file_id == "notes/test.md"


def test_backward_compatible_chunk_text_returns_list_of_str():
    """Old callers that expect list[str] can use chunk_text_plain."""
    from kb.data.storage import chunk_text_plain
    result = chunk_text_plain("Hello world")
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)
