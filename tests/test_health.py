from pathlib import Path

from kb.core.config import KBConfig, ObsidianConfig
from kb.core.context import AppContext
from kb.core.health import get_system_health
from kb.core.models import Note
from kb.data.database import Database
from kb.data.vector import VectorStore


def make_context(tmp_path: Path, *, create_dirs: bool = True) -> AppContext:
    if create_dirs:
        (tmp_path / "notes").mkdir()
        (tmp_path / "attachments").mkdir()
        (tmp_path / ".kb").mkdir()
    config = KBConfig(
        vault_path=tmp_path.resolve(),
        obsidian=ObsidianConfig(
            enabled=True,
            vault_name="TestVault",
            vault_path=tmp_path.resolve(),
        ),
    )
    return AppContext.from_config(
        config,
        with_embedding=False,
        with_llm=False,
        allow_lazy_embedding=True,
        allow_lazy_llm=True,
    )


def status_by_id(health: dict) -> dict[str, str]:
    return {check["id"]: check["status"] for check in health["checks"]}


def test_health_ready_for_empty_initialized_vault(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    vector_path = tmp_path / ".kb" / "vectors.lance"
    assert not vector_path.exists()
    try:
        health = get_system_health(ctx)
    finally:
        ctx.close()

    assert not vector_path.exists()
    assert health["status"] == "ready"
    assert health["summary"] == {
        "notes_count": 0,
        "vectors_count": 0,
        "coverage": 1.0,
    }
    statuses = status_by_id(health)
    assert statuses["vault"] == "ready"
    assert statuses["notes_dir"] == "ready"
    assert statuses["attachments_dir"] == "ready"
    assert statuses["index_dir"] == "ready"
    assert statuses["obsidian"] == "ready"
    assert statuses["embedding_config"] == "ready"
    assert statuses["llm_config"] == "ready"


def test_health_errors_when_vault_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing-vault"
    config = KBConfig(vault_path=missing.resolve())
    ctx = AppContext(
        vault=missing.resolve(),
        db=Database(missing / ".kb" / "kb.db"),
        config=config,
        vector_store=VectorStore(missing / ".kb" / "vectors.lance"),
        allow_lazy_embedding=True,
        allow_lazy_llm=True,
    )
    try:
        health = get_system_health(ctx)
    finally:
        ctx.close()

    assert not missing.exists()
    assert health["status"] == "error"
    assert status_by_id(health)["vault"] == "error"


def test_health_warns_when_notes_have_no_vectors(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    try:
        ctx.db.upsert_note(Note(file_id="notes/example.md", title="Example", content="Body"))
        health = get_system_health(ctx)
    finally:
        ctx.close()

    assert health["status"] == "warning"
    assert health["summary"]["notes_count"] == 1
    assert health["summary"]["vectors_count"] == 0
    assert health["summary"]["coverage"] == 0.0
    assert status_by_id(health)["vector_index"] == "warning"
