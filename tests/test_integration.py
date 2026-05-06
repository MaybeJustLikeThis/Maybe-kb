"""Integration tests with realistic Hexo-format notes."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from kb.cli import app
from kb.data.storage import parse_markdown_file
from kb.data.database import Database
from kb.server import create_app
from kb.core.config import load_config
from fastapi.testclient import TestClient

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


@pytest.fixture
def db(project: Path):
    """Yield an initialized Database, ensuring it is always closed."""
    database = Database(project / ".kb" / "kb.db")
    database.initialize()
    yield database
    database.close()


def test_full_workflow(project: Path, db: Database):
    """Full init -> index -> search -> list workflow."""
    result = runner.invoke(app, ["init", "--import-existing"])
    assert result.exit_code == 0

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


def test_incremental_index(project: Path, db: Database):
    """Second index run only processes changed files."""
    runner.invoke(app, ["init", "--import-existing"])

    vue_file = project / "notes" / "tech" / "vue-state.md"
    content = vue_file.read_text(encoding="utf-8")
    vue_file.write_text(content + "\n\n## 新增章节\n\n新增内容。\n", encoding="utf-8")

    from kb.cli import _index_files
    count, _ = _index_files(project, db, full=False)
    assert count == 1


def test_web_ui_full_workflow(project: Path):
    """Full Web UI workflow: create -> list -> search -> update -> delete."""
    runner.invoke(app, ["init"])
    config = load_config(project)
    web_app = create_app(config)
    client = TestClient(web_app)

    # Create notes
    r = client.post("/api/notes", json={
        "title": "Web Test",
        "content": "# Hello\n\nWorld",
        "category": "tech",
        "tags": ["test"],
    })
    assert r.status_code == 200
    file_id = r.json()["file_id"]

    # List
    r = client.get("/api/notes")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Search
    r = client.get("/api/search", params={"q": "Hello"})
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Get
    r = client.get(f"/api/notes/{file_id}")
    assert r.status_code == 200

    # Update
    r = client.put(f"/api/notes/{file_id}", json={"title": "Updated Title"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated Title"

    # Delete
    r = client.delete(f"/api/notes/{file_id}")
    assert r.status_code == 200

    r = client.get(f"/api/notes/{file_id}")
    assert r.status_code == 404
