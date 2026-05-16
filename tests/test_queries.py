"""Tests for read-model query orchestration."""
from pathlib import Path

import pytest

from kb.core import queries
from kb.core.config import KBConfig, ServerConfig
from kb.core.context import AppContext
from kb.core.models import Note


@pytest.fixture
def ctx(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "attachments").mkdir()
    (tmp_path / "attachments" / "sample.txt").write_text("x", encoding="utf-8")
    (tmp_path / ".kb").mkdir()
    config = KBConfig(
        vault_path=tmp_path.resolve(),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )
    app_ctx = AppContext.from_config(
        config,
        vault=tmp_path,
        with_embedding=False,
        with_llm=False,
    )
    yield app_ctx
    app_ctx.close()


def add_note(ctx: AppContext, note: Note):
    ctx.db.upsert_note(note)


def test_list_notes_returns_summaries_and_total(ctx):
    add_note(ctx, Note(
        file_id="notes/a.md",
        title="A",
        content="Alpha",
        category="tech",
        tags=["python"],
        status="published",
        file_hash="a",
    ))
    add_note(ctx, Note(
        file_id="notes/b.md",
        title="B",
        content="Beta",
        category="tech",
        tags=["fastapi"],
        status="published",
        file_hash="b",
    ))

    result = queries.list_notes(ctx, category="tech", tag=None, limit=1, offset=0)

    assert result.total == 2
    assert len(result.items) == 1
    assert result.items[0]["file_id"] in {"notes/a.md", "notes/b.md"}
    assert "content" not in result.items[0]


def test_get_dashboard_stats_unifies_sources(ctx):
    add_note(ctx, Note(
        file_id="notes/a.md",
        title="A",
        content="Alpha",
        category="tech",
        tags=["python"],
        status="published",
        file_hash="a",
        source_project="kb",
        content_type="markdown",
    ))

    stats = queries.get_dashboard_stats(ctx)

    assert stats["notes_count"] == 1
    assert stats["attachments_count"] == 1
    assert stats["index_health"]["notes_count"] == 1
    assert stats["source_projects"][0]["name"] == "kb"
    assert stats["content_types"][0]["name"] == "markdown"
