"""Tests for Markdown storage layer."""
import pytest
from pathlib import Path
from kb.data.storage import (
    chunk_text,
    chunk_text_plain,
    discover_notes,
    make_slug,
    parse_markdown_file,
    write_markdown_file,
)


SAMPLE_MARKDOWN = """\
---
title: 6月20日有感
tags: 杂谈
categories: 杂谈
description: 6月20日临时有感
top_img: transparent
abbrlink: 917b0383
date: 2025-07-03 20:55:38
updated:
---

# 正文标题

这里是正文内容。

## 第二节

更多内容。
"""

SAMPLE_ARRAY_TAGS = """\
---
title: Vue 状态管理
tags: [vue, pinia, vuex]
category: tech
date: 2026-01-15 10:00:00
---

正文。
"""


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 1314:
            pytest.skip(f"symlink creation is not permitted: {exc}")
        raise


def test_parse_hexo_frontmatter(tmp_path: Path):
    """Parse Hexo-style frontmatter with single-value tags."""
    f = tmp_path / "test.md"
    f.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    note = parse_markdown_file(f, tmp_path)

    assert note.title == "6月20日有感"
    assert note.tags == ["杂谈"]
    assert note.category == "杂谈"
    assert note.description == "6月20日临时有感"
    assert note.created_at == "2025-07-03T20:55:38"
    assert note.status == "published"
    # Extra fields preserved
    assert note.extra_frontmatter["top_img"] == "transparent"
    assert note.extra_frontmatter["abbrlink"] == "917b0383"


def test_parse_array_tags(tmp_path: Path):
    """Parse frontmatter with array tags."""
    f = tmp_path / "test.md"
    f.write_text(SAMPLE_ARRAY_TAGS, encoding="utf-8")

    note = parse_markdown_file(f, tmp_path)
    assert note.tags == ["vue", "pinia", "vuex"]
    assert note.category == "tech"


def test_parse_content(tmp_path: Path):
    """Content excludes frontmatter."""
    f = tmp_path / "test.md"
    f.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    note = parse_markdown_file(f, tmp_path)
    assert "title:" not in note.content
    assert "# 正文标题" in note.content
    assert "这里是正文内容。" in note.content


def test_write_and_roundtrip(tmp_path: Path):
    """Written file can be parsed back with same data."""
    f = tmp_path / "test.md"
    f.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    note = parse_markdown_file(f, tmp_path)
    write_markdown_file(f, note)

    note2 = parse_markdown_file(f, tmp_path)
    assert note2.title == note.title
    assert note2.tags == note.tags
    assert note2.description == note.description
    # Extra fields preserved
    assert note2.extra_frontmatter.get("top_img") == "transparent"


def test_write_new_note(tmp_path: Path):
    """write_markdown_file creates file with frontmatter + content."""
    from kb.data.models import Note

    note = Note(
        file_id="tech/new.md",
        title="New Note",
        tags=["python"],
        content="# Hello\n\nWorld.\n",
    )
    f = tmp_path / "tech" / "new.md"
    write_markdown_file(f, note)

    assert f.exists()
    parsed = parse_markdown_file(f, tmp_path)
    assert parsed.title == "New Note"
    assert parsed.tags == ["python"]
    assert "World." in parsed.content


def test_no_frontmatter(tmp_path: Path):
    """File without frontmatter is handled gracefully."""
    f = tmp_path / "plain.md"
    f.write_text("# Just a heading\n\nSome text.\n", encoding="utf-8")

    note = parse_markdown_file(f, tmp_path)
    assert note.title == "plain"  # fallback to filename
    assert note.tags == []
    assert "# Just a heading" in note.content


def test_chunk_short_text_not_split():
    """Text under max_chars returns single-element list."""
    assert chunk_text_plain("短文本", max_chars=1000) == ["短文本"]


def test_chunk_long_text_splits_at_paragraphs():
    """Long text with paragraph breaks splits at \\n\\n."""
    text = "段落一。" + "x" * 800 + "\n\n" + "段落二。" + "y" * 800
    result = chunk_text_plain(text, max_chars=1000)
    assert len(result) >= 2
    assert "段落一" in result[0]
    assert "段落二" in result[1]


def test_chunk_overlap_preserves_context():
    """Adjacent chunks share overlap region."""
    text = "篇章内容" * 500
    overlap = 100
    result = chunk_text_plain(text, max_chars=500, overlap=overlap)
    assert len(result) >= 2
    assert result[0][-overlap:] == result[1][:overlap]


def test_chunk_empty_text():
    """Empty string returns empty list."""
    assert chunk_text("") == []


def test_chunk_splits_at_sentence_boundary():
    """When no paragraph break, splits at Chinese period."""
    sentences = ["句子" + str(i) + "。" + "x" * 400 for i in range(5)]
    text = "".join(sentences)
    result = chunk_text_plain(text, max_chars=1000)
    assert len(result) >= 2


def test_make_slug_with_category():
    slug, cat = make_slug("Hello World", "tech")
    assert slug == "hello-world"
    assert cat == "tech"


def test_make_slug_without_category_defaults_to_weifenlei():
    slug, cat = make_slug("Hello World")
    assert slug == "hello-world"
    assert cat == "未分类"


def test_make_slug_sanitizes_category():
    slug, cat = make_slug("Title", "a/b\\c")
    assert cat == "a-b-c"
    assert "/" not in cat
    assert "\\" not in cat


def test_discover_notes_scans_only_configured_notes_dir(tmp_path: Path):
    vault = tmp_path / "vault"
    configured = vault / "knowledge"
    configured.mkdir(parents=True)
    included = configured / "included.md"
    included.write_text("# Included\n", encoding="utf-8")
    default_note = vault / "notes" / "ignored.md"
    default_note.parent.mkdir()
    default_note.write_text("# Ignored\n", encoding="utf-8")
    elsewhere = vault / "elsewhere.md"
    elsewhere.write_text("# Ignored\n", encoding="utf-8")

    assert discover_notes(vault, notes_dir="knowledge") == [included]


def test_discover_notes_rejects_configured_dir_outside_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()

    with pytest.raises(ValueError, match="escapes the vault"):
        discover_notes(vault, notes_dir="../outside")


def test_discover_notes_preserves_relative_vault_parse_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    vault = Path("vault")
    note_file = vault / "knowledge" / "note.md"
    note_file.parent.mkdir(parents=True)
    note_file.write_text("# Note\n", encoding="utf-8")

    files = discover_notes(vault, notes_dir="knowledge")
    note = parse_markdown_file(files[0], vault)

    assert files == [note_file]
    assert note.file_id == "knowledge/note.md"


def test_discover_notes_ignores_symlinked_markdown_outside_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    notes = vault / "knowledge"
    notes.mkdir(parents=True)
    inside = notes / "inside.md"
    inside.write_text("# Inside\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    unsafe_link = notes / "outside-link.md"
    _symlink_or_skip(unsafe_link, outside)

    assert discover_notes(vault, notes_dir="knowledge") == [inside]
