"""Integration tests with realistic Hexo-format notes."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from kb.cli import app
from kb.storage import parse_markdown_file
from kb.indexer import Database

runner = CliRunner()

HEXO_NOTE = """\
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

## 正文

这里是正文内容。
"""

VUE_NOTE = """\
---
title: Vue 状态管理方案对比
tags: [vue, pinia, vuex]
category: tech
date: 2026-01-15 10:00:00
updated: 2026-01-20 08:00:00
---

Pinia 是 Vue 3 推荐的状态管理方案。
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a full kb project with Hexo notes."""
    import os
    os.chdir(tmp_path)

    notes_dir = tmp_path / "notes" / "杂谈"
    notes_dir.mkdir(parents=True)
    (notes_dir / "6月20日有感.md").write_text(HEXO_NOTE, encoding="utf-8")

    tech_dir = tmp_path / "notes" / "tech"
    tech_dir.mkdir(parents=True)
    (tech_dir / "vue-state.md").write_text(VUE_NOTE, encoding="utf-8")

    return tmp_path


def test_full_workflow(project: Path):
    """Full init -> index -> search -> list workflow."""
    result = runner.invoke(app, ["init", "--import-existing"])
    assert result.exit_code == 0

    db = Database(project / ".kb" / "kb.db")
    db.initialize()

    all_hashes = db.get_all_hashes()
    assert len(all_hashes) == 2

    results = db.search_fulltext("Pinia")
    assert len(results) >= 1

    tech_notes = db.list_notes(category="tech")
    assert len(tech_notes) == 1
    assert tech_notes[0]["title"] == "Vue 状态管理方案对比"

    # Verify Hexo fields preserved
    note = parse_markdown_file(project / "notes" / "杂谈" / "6月20日有感.md", project)
    assert note.extra_frontmatter["top_img"] == "transparent"
    assert note.extra_frontmatter["abbrlink"] == "917b0383"
    assert note.tags == ["杂谈"]

    db.close()


def test_incremental_index(project: Path):
    """Second index run only processes changed files."""
    runner.invoke(app, ["init", "--import-existing"])

    db = Database(project / ".kb" / "kb.db")
    db.initialize()

    vue_file = project / "notes" / "tech" / "vue-state.md"
    content = vue_file.read_text(encoding="utf-8")
    vue_file.write_text(content + "\n\n## 新增章节\n\n新增内容。\n", encoding="utf-8")

    from kb.cli import _index_files
    count = _index_files(project, db, full=False)
    assert count == 1

    db.close()
