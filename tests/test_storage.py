"""Tests for Markdown storage layer."""
import pytest
from pathlib import Path
from kb.storage import parse_markdown_file, write_markdown_file


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
    from kb.models import Note

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
