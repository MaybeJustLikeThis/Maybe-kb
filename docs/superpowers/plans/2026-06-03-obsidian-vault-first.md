# Obsidian Vault-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the personal knowledge vault to `D:\ObsidianVault`, make Obsidian the primary editor, and keep `kb` as an independent local knowledge engine.

**Architecture:** Introduce explicit configured vault subpaths (`notes_dir`, `attachments_dir`, `index_dir`) and an Obsidian integration config. Update storage, indexing, context initialization, API, CLI, and Web UI to operate on the configured vault instead of assuming the project directory is the vault. Add a migration command that copies existing notes and attachments, writes config, rebuilds the index, and leaves the old `notes/` untouched for rollback.

**Tech Stack:** Python 3.11+, Typer, FastAPI, SQLite FTS5, LanceDB, Vue 3, Vite, TypeScript.

---

## File Structure

- Modify: `src/kb/core/config.py`
  - Add `GeneralConfig` and `ObsidianConfig`.
  - Add `KBConfig.notes_path`, `KBConfig.attachments_path`, and `KBConfig.index_path` properties.
  - Load new config keys with backward-compatible defaults.
- Modify: `src/kb/core/context.py`
  - Use `config.index_path` for SQLite and LanceDB.
- Modify: `src/kb/data/storage.py`
  - Let `discover_notes()` scan a configurable notes directory.
  - Keep `file_id` relative to the vault root.
- Modify: `src/kb/data/attachments.py`
  - Let attachment storage use a configurable attachment directory.
- Modify: `src/kb/core/indexer.py`
  - Accept `notes_dir` and use configurable attachment storage.
  - Keep legacy external source support isolated.
- Modify: `src/kb/core/watcher.py`
  - No behavior change required; callers will pass the configured notes path.
- Modify: `src/kb/cli.py`
  - Stop overriding the vault to `Path.cwd()` in normal commands.
  - Add `kb obsidian init-vault`.
  - Make `serve` watch the configured notes path.
- Modify: `src/kb/api/schemas.py`
  - Add `OpenTarget`.
- Modify: `src/kb/api/v1.py`
  - Add `/api/v1/notes/{file_id}/open-target`.
- Create: `src/kb/core/open_targets.py`
  - Build Obsidian URI and resolved file target safely.
- Modify: `web/src/api.ts`
  - Add `OpenTarget` type and `getOpenTarget()`.
- Modify: `web/src/pages/NoteDetail.vue`
  - Make `Open in Obsidian` the primary note action.
- Modify: `web/src/pages/SearchPage.vue`
  - Add open action for search results.
- Modify: `web/src/pages/ChatPage.vue`
  - Add open action for RAG sources.
- Modify: tests under `tests/`
  - Add focused tests for config, storage discovery, attachments, open targets, API, CLI migration, and Web build.

---

### Task 1: Configuration Model

**Files:**
- Modify: `src/kb/core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add these tests to `tests/test_config.py`:

```python
from pathlib import Path

from kb.core.config import load_config


def test_load_config_supports_obsidian_vault_paths(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[general]
vault_path = "D:/ObsidianVault"
notes_dir = "notes"
attachments_dir = "attachments"
index_dir = ".kb"

[obsidian]
enabled = true
vault_name = "ObsidianVault"
vault_path = "D:/ObsidianVault"
open_uri_strategy = "file"

[server]
watch_enabled = true
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.vault_path == Path("D:/ObsidianVault").resolve()
    assert config.general.notes_dir == "notes"
    assert config.general.attachments_dir == "attachments"
    assert config.general.index_dir == ".kb"
    assert config.notes_path == Path("D:/ObsidianVault").resolve() / "notes"
    assert config.attachments_path == Path("D:/ObsidianVault").resolve() / "attachments"
    assert config.index_path == Path("D:/ObsidianVault").resolve() / ".kb"
    assert config.obsidian.enabled is True
    assert config.obsidian.vault_name == "ObsidianVault"
    assert config.server.watch_enabled is True


def test_load_config_keeps_legacy_defaults(tmp_path: Path):
    (tmp_path / "config.toml").write_text(
        """
[general]
vault_path = "."
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.vault_path == tmp_path.resolve()
    assert config.general.notes_dir == "notes"
    assert config.general.attachments_dir == "attachments"
    assert config.general.index_dir == ".kb"
    assert config.obsidian.enabled is False
    assert config.server.watch_enabled is True
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_config.py -q
```

Expected: fails because `general`, `obsidian`, `notes_path`, `attachments_path`, `index_path`, and `watch_enabled` are not implemented.

- [ ] **Step 3: Implement config dataclasses and properties**

In `src/kb/core/config.py`, add:

```python
@dataclass(frozen=True)
class GeneralConfig:
    notes_dir: str = "notes"
    attachments_dir: str = "attachments"
    index_dir: str = ".kb"


@dataclass(frozen=True)
class ObsidianConfig:
    enabled: bool = False
    vault_name: str = ""
    vault_path: Path | None = None
    open_uri_strategy: str = "file"
```

Update `ServerConfig`:

```python
@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8420
    watch_dir: str | None = None
    watch_enabled: bool = True
```

Update `KBConfig`:

```python
@dataclass(frozen=True)
class KBConfig:
    vault_path: Path = field(default_factory=lambda: Path("."))
    general: GeneralConfig = field(default_factory=GeneralConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    obsidian: ObsidianConfig = field(default_factory=ObsidianConfig)
    sources: dict[str, SourceConfig] = field(default_factory=dict)

    @property
    def notes_path(self) -> Path:
        return self.vault_path / self.general.notes_dir

    @property
    def attachments_path(self) -> Path:
        return self.vault_path / self.general.attachments_dir

    @property
    def index_path(self) -> Path:
        return self.vault_path / self.general.index_dir
```

Inside `load_config()`, parse the new sections:

```python
general = data.get("general", {})
obsidian_data = data.get("obsidian", {})
server_data = data.get("server", {})

vault_rel = general.get("vault_path", ".")
vault_path_raw = Path(vault_rel).expanduser()
vault_path = (
    vault_path_raw.resolve()
    if vault_path_raw.is_absolute()
    else (base_path / vault_path_raw).resolve()
)

obsidian_vault_raw = obsidian_data.get("vault_path")
obsidian_vault_path = None
if obsidian_vault_raw:
    raw_path = Path(obsidian_vault_raw).expanduser()
    obsidian_vault_path = (
        raw_path.resolve()
        if raw_path.is_absolute()
        else (base_path / raw_path).resolve()
    )
```

Return these new values:

```python
return KBConfig(
    vault_path=vault_path,
    general=GeneralConfig(
        notes_dir=general.get("notes_dir", "notes"),
        attachments_dir=general.get("attachments_dir", "attachments"),
        index_dir=general.get("index_dir", ".kb"),
    ),
    search=SearchConfig(max_results=search_data.get("max_results", 20)),
    embedding=EmbeddingConfig(
        provider=embedding_data.get("provider", "local"),
        model=embedding_data.get("model", "BAAI/bge-small-zh-v1.5"),
        api_key_env=embedding_data.get("api_key_env"),
    ),
    llm=LLMConfig(
        provider=llm_data.get("provider", "ollama"),
        model=llm_data.get("model", "qwen2.5:7b"),
        api_key_env=llm_data.get("api_key_env"),
    ),
    rag=RAGConfig(
        top_k=rag_data.get("top_k", 5),
        truncate_chars=rag_data.get("truncate_chars", 800),
    ),
    server=ServerConfig(
        host=server_data.get("host", "127.0.0.1"),
        port=server_data.get("port", 8420),
        watch_dir=server_data.get("watch_dir"),
        watch_enabled=server_data.get("watch_enabled", True),
    ),
    obsidian=ObsidianConfig(
        enabled=obsidian_data.get("enabled", False),
        vault_name=obsidian_data.get("vault_name", ""),
        vault_path=obsidian_vault_path,
        open_uri_strategy=obsidian_data.get("open_uri_strategy", "file"),
    ),
    sources=sources,
)
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_config.py -q
```

Expected: all config tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/kb/core/config.py tests/test_config.py
git commit -m "feat: add vault path configuration"
```

---

### Task 2: Storage, Attachments, and Context Paths

**Files:**
- Modify: `src/kb/core/context.py`
- Modify: `src/kb/data/storage.py`
- Modify: `src/kb/data/attachments.py`
- Modify: `src/kb/core/indexer.py`
- Test: `tests/test_storage.py`
- Test: `tests/test_attachments.py`
- Test: `tests/test_indexer.py`

- [ ] **Step 1: Write failing storage discovery test**

Add to `tests/test_storage.py`:

```python
from pathlib import Path

from kb.data.storage import discover_notes


def test_discover_notes_only_scans_configured_notes_dir(tmp_path: Path):
    vault = tmp_path / "vault"
    notes = vault / "notes"
    notes.mkdir(parents=True)
    (notes / "keep.md").write_text("# keep", encoding="utf-8")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "ignore.md").write_text("# ignore", encoding="utf-8")
    (vault / "attachments").mkdir()
    (vault / "attachments" / "ignore.md").write_text("# ignore", encoding="utf-8")
    (vault / "templates").mkdir()
    (vault / "templates" / "ignore.md").write_text("# ignore", encoding="utf-8")

    result = discover_notes(vault, notes_dir="notes")

    assert result == [notes / "keep.md"]
```

- [ ] **Step 2: Write failing attachment directory test**

Add to `tests/test_attachments.py`:

```python
from pathlib import Path

from kb.data.attachments import store_attachment


def test_store_attachment_uses_configured_directory(tmp_path: Path):
    vault = tmp_path / "vault"
    source = tmp_path / "image.png"
    source.write_bytes(b"png")

    rel = store_attachment(source, vault, attachments_dir="files")

    assert rel.startswith("files/")
    assert (vault / rel).read_bytes() == b"png"
```

- [ ] **Step 3: Update storage and attachments implementation**

In `src/kb/data/storage.py`, replace `discover_notes()` with:

```python
def discover_notes(vault_path: Path, notes_dir: str = "notes") -> list[Path]:
    """Find all .md files under the configured notes directory."""
    root = (vault_path / notes_dir).resolve()
    vault_resolved = vault_path.resolve()
    if not root.is_relative_to(vault_resolved):
        raise ValueError(f"notes_dir escapes vault: {notes_dir}")
    if not root.exists():
        return []
    return sorted(root.rglob("*.md"))
```

In `src/kb/data/attachments.py`, update signatures and directory usage:

```python
def store_attachment(
    source: Path,
    vault_path: Path,
    *,
    attachments_dir: str = ATTACHMENTS_DIR,
) -> str:
    data = source.read_bytes()
    ext = source.suffix.lower()
    hash_name = _content_hash(data)

    existing_path = _find_existing_attachment(
        vault_path,
        hash_name,
        ext,
        data,
        attachments_dir=attachments_dir,
    )
    if existing_path is not None:
        return existing_path

    now = datetime.now()
    rel_path = f"{attachments_dir}/{now.year}/{now.month:02d}/{hash_name}{ext}"
    dest = vault_path / rel_path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return rel_path
```

Update `_find_existing_attachment()`:

```python
def _find_existing_attachment(
    vault_path: Path,
    hash_name: str,
    ext: str,
    data: bytes,
    *,
    attachments_dir: str = ATTACHMENTS_DIR,
) -> str | None:
    attachments_root = vault_path / attachments_dir
    if not attachments_root.exists():
        return None

    matches = sorted(attachments_root.rglob(f"{hash_name}{ext}"))
    for path in matches:
        if path.is_file() and path.read_bytes() == data:
            return path.relative_to(vault_path).as_posix()
    return None
```

- [ ] **Step 4: Update context and indexer paths**

In `src/kb/core/context.py`, replace hardcoded `.kb` paths:

```python
index_path = config.index_path
index_path.mkdir(parents=True, exist_ok=True)

db_path = index_path / "kb.db"
db = Database(db_path)
db.initialize()

vector_store = VectorStore(index_path / "vectors.lance")
```

In `src/kb/core/indexer.py`, add parameters:

```python
def index_files(
    vault: Path,
    db: Database,
    *,
    full: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    external_sources: list[Path] | None = None,
    source_project: str | None = None,
    notes_dir: str = "notes",
    attachments_dir: str = "attachments",
) -> tuple[int, int]:
```

Replace `notes_dir = vault / "notes"` in the external source block with:

```python
notes_root = vault / notes_dir
notes_root.mkdir(parents=True, exist_ok=True)
```

Replace `category_dir = notes_dir / cat` with:

```python
category_dir = notes_root / cat
```

Replace `for existing in notes_dir.rglob(f.name):` with:

```python
for existing in notes_root.rglob(f.name):
```

Call `collect_markdown_image_assets()` with the existing signature first. In the same task, update `collect_markdown_image_assets()` only if Task 2 tests reveal attachment directory mismatch. The minimal first pass keeps Markdown asset collection writing to `attachments`.

Replace:

```python
files = discover_notes(vault)
```

with:

```python
files = discover_notes(vault, notes_dir=notes_dir)
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_storage.py tests/test_attachments.py tests/test_indexer.py -q
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/kb/core/context.py src/kb/data/storage.py src/kb/data/attachments.py src/kb/core/indexer.py tests/test_storage.py tests/test_attachments.py tests/test_indexer.py
git commit -m "feat: use configured vault subpaths"
```

---

### Task 3: CLI Uses Configured Vault and Adds Migration Command

**Files:**
- Modify: `src/kb/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing helper tests for configured context**

Add to `tests/test_cli.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from kb.cli import app


def test_obsidian_init_vault_copies_notes_and_updates_config(tmp_path: Path):
    runner = CliRunner()
    project = tmp_path / "project"
    source_notes = project / "notes"
    source_attachments = project / "attachments"
    target = tmp_path / "ObsidianVault"
    source_notes.mkdir(parents=True)
    source_attachments.mkdir()
    (source_notes / "AI").mkdir()
    (source_notes / "AI" / "note.md").write_text("# Note", encoding="utf-8")
    (source_attachments / "file.png").write_bytes(b"png")
    (project / "config.toml").write_text(
        '[general]\nvault_path = "."\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "obsidian",
            "init-vault",
            "--target",
            str(target),
            "--from-notes",
            str(source_notes),
            "--from-attachments",
            str(source_attachments),
            "--skip-index",
        ],
        cwd=project,
    )

    assert result.exit_code == 0
    assert (target / "notes" / "AI" / "note.md").read_text(encoding="utf-8") == "# Note"
    assert (target / "attachments" / "file.png").read_bytes() == b"png"
    assert (target / ".obsidian").is_dir()
    updated = (project / "config.toml").read_text(encoding="utf-8")
    assert 'vault_path = "' in updated
    assert "D:/ObsidianVault" not in updated
    assert "notes_dir = \"notes\"" in updated
    assert "[obsidian]" in updated
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
python -m pytest tests/test_cli.py::test_obsidian_init_vault_copies_notes_and_updates_config -q
```

Expected: fails because the `obsidian init-vault` command does not exist.

- [ ] **Step 3: Add config-aware context helper**

In `src/kb/cli.py`, replace `_get_context()` with:

```python
def _get_context(
    *,
    with_embedding: bool = False,
    with_llm: bool = False,
    project_path: Path | None = None,
) -> AppContext:
    """Get AppContext from project config, operating on configured vault_path."""
    base = project_path or Path.cwd()
    config = load_config(base)
    return AppContext.from_config(
        config,
        with_embedding=with_embedding,
        with_llm=with_llm,
    )
```

When commands need the project directory for config writing, use `project = Path.cwd()`. When commands need the vault, use `ctx.vault` or `config.vault_path`.

- [ ] **Step 4: Add obsidian Typer group and migration command**

In `src/kb/cli.py`, after `app = typer.Typer(...)`, add:

```python
obsidian_app = typer.Typer(help="Obsidian vault integration commands")
app.add_typer(obsidian_app, name="obsidian")
```

Add helper functions:

```python
def _copy_tree_contents(source: Path, dest: Path) -> int:
    import shutil

    if not source.exists():
        return 0
    count = 0
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        count += 1
    return count


def _write_obsidian_config(project: Path, target: Path) -> None:
    config_path = project / "config.toml"
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    normalized = target.as_posix()
    content = (
        '[general]\n'
        f'vault_path = "{normalized}"\n'
        'notes_dir = "notes"\n'
        'attachments_dir = "attachments"\n'
        'index_dir = ".kb"\n\n'
        '[obsidian]\n'
        'enabled = true\n'
        'vault_name = "ObsidianVault"\n'
        f'vault_path = "{normalized}"\n'
        'open_uri_strategy = "file"\n\n'
    )
    for section in ("[search]", "[embedding]", "[llm]", "[rag]", "[server]", "[sources."):
        if section in existing:
            break
    config_path.write_text(content + _preserve_non_general_sections(existing), encoding="utf-8")


def _preserve_non_general_sections(existing: str) -> str:
    lines = existing.splitlines()
    kept: list[str] = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped in {"[general]", "[obsidian]"}:
            skip = True
            continue
        if stripped.startswith("[") and stripped not in {"[general]", "[obsidian]"}:
            skip = False
        if not skip and stripped:
            kept.append(line)
    return "\n".join(kept).strip() + ("\n" if kept else "")
```

Add the command:

```python
@obsidian_app.command("init-vault")
def obsidian_init_vault(
    target: Path = typer.Option(..., "--target", help="Target Obsidian vault path"),
    from_notes: Path = typer.Option(Path("notes"), "--from-notes", help="Existing notes directory"),
    from_attachments: Path = typer.Option(Path("attachments"), "--from-attachments", help="Existing attachments directory"),
    skip_index: bool = typer.Option(False, "--skip-index", help="Skip full index rebuild"),
):
    """Create an Obsidian vault and copy existing notes and attachments."""
    project = Path.cwd()
    target = target.expanduser().resolve()
    notes_target = target / "notes"
    attachments_target = target / "attachments"
    (target / ".obsidian").mkdir(parents=True, exist_ok=True)
    notes_count = _copy_tree_contents(from_notes.resolve(), notes_target)
    attachment_count = _copy_tree_contents(from_attachments.resolve(), attachments_target)
    _write_obsidian_config(project, target)

    indexed = 0
    vectors = 0
    if not skip_index:
        config = load_config(project)
        ctx = AppContext.from_config(config, with_embedding=True, with_llm=False)
        try:
            indexed, vectors = index_files(
                ctx.vault,
                ctx.db,
                full=True,
                embedding_provider=ctx.embedding,
                notes_dir=config.general.notes_dir,
                attachments_dir=config.general.attachments_dir,
            )
        finally:
            ctx.close()

    console.print(
        f"[green]Obsidian vault ready:[/green] {target} "
        f"({notes_count} notes, {attachment_count} attachments, "
        f"{indexed} indexed, {vectors} vectors)"
    )
```

- [ ] **Step 5: Update existing CLI commands to use configured vault**

For `init`, keep initializing the selected path as before.

For `add_note`, set:

```python
project = Path.cwd()
config = load_config(project)
ctx = _get_context()
vault = ctx.vault
```

Pass `source_config=config.sources.get(source_project)`.

For `index`, set:

```python
project = Path.cwd()
config = load_config(project)
ctx = _get_context(with_embedding=True)
fts5_count, vec_count = index_files(
    ctx.vault,
    ctx.db,
    full=full,
    embedding_provider=ctx.embedding,
    notes_dir=config.general.notes_dir,
    attachments_dir=config.general.attachments_dir,
)
```

For `serve`, watch `config.notes_path` when `config.server.watch_enabled` is true:

```python
watch_dir_path = watch.resolve() if watch else config.notes_path
if not config.server.watch_enabled:
    watch_dir_path = None
```

Inside `on_change()`, pass `notes_dir=config.general.notes_dir` and `attachments_dir=config.general.attachments_dir`.

- [ ] **Step 6: Run CLI tests**

Run:

```powershell
python -m pytest tests/test_cli.py -q
```

Expected: CLI tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/kb/cli.py tests/test_cli.py
git commit -m "feat: add obsidian vault migration command"
```

---

### Task 4: Obsidian Open Target API

**Files:**
- Create: `src/kb/core/open_targets.py`
- Modify: `src/kb/api/schemas.py`
- Modify: `src/kb/api/v1.py`
- Test: `tests/test_api_v1.py`
- Test: `tests/test_open_targets.py`

- [ ] **Step 1: Write open target unit tests**

Create `tests/test_open_targets.py`:

```python
from pathlib import Path

from kb.core.config import KBConfig, ObsidianConfig
from kb.core.open_targets import build_obsidian_open_target


def test_build_obsidian_open_target_encodes_relative_file(tmp_path: Path):
    vault = tmp_path / "ObsidianVault"
    note = vault / "notes" / "AI" / "测试 note(一).md"
    note.parent.mkdir(parents=True)
    note.write_text("# note", encoding="utf-8")
    config = KBConfig(
        vault_path=vault,
        obsidian=ObsidianConfig(enabled=True, vault_name="ObsidianVault"),
    )

    target = build_obsidian_open_target(config, "notes/AI/测试 note(一).md")

    assert target["relative_path"] == "notes/AI/测试 note(一).md"
    assert target["file_path"] == note.resolve().as_posix()
    assert target["obsidian_uri"] == (
        "obsidian://open?vault=ObsidianVault&file="
        "notes%2FAI%2F%E6%B5%8B%E8%AF%95%20note%28%E4%B8%80%29.md"
    )


def test_build_obsidian_open_target_blocks_path_traversal(tmp_path: Path):
    config = KBConfig(
        vault_path=tmp_path / "vault",
        obsidian=ObsidianConfig(enabled=True, vault_name="ObsidianVault"),
    )

    try:
        build_obsidian_open_target(config, "../secret.md")
    except ValueError as exc:
        assert "Path traversal blocked" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Add API test**

Add to `tests/test_api_v1.py`:

```python
def test_v1_note_open_target(client):
    create = client.post(
        "/api/v1/notes",
        json={
            "title": "测试 note",
            "content": "# 测试 note\n",
            "source_project": "manual",
        },
    )
    assert create.status_code == 200
    file_id = create.json()["data"]["file_id"]

    response = client.get(f"/api/v1/notes/{file_id}/open-target")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["relative_path"] == file_id
    assert data["obsidian_uri"].startswith("obsidian://open?")
```

If the existing API fixture does not enable Obsidian config, adjust only the fixture-local config in `tests/test_api_v1.py` to include `obsidian.enabled=True` and `vault_name="ObsidianVault"`.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_open_targets.py tests/test_api_v1.py::test_v1_note_open_target -q
```

Expected: fails because `open_targets.py`, schema, and route are not implemented.

- [ ] **Step 4: Implement open target helper**

Create `src/kb/core/open_targets.py`:

```python
"""Open-target builders for external editors."""
from __future__ import annotations

from urllib.parse import quote

from kb.core.config import KBConfig
from kb.data.storage import validate_vault_path


def build_obsidian_open_target(config: KBConfig, file_id: str) -> dict:
    """Build a safe Obsidian URI target for a note file_id."""
    resolved = validate_vault_path(config.vault_path, file_id)
    if not resolved.is_file():
        raise FileNotFoundError(file_id)

    relative_path = resolved.relative_to(config.vault_path.resolve()).as_posix()
    vault_name = config.obsidian.vault_name or config.vault_path.name
    return {
        "obsidian_uri": (
            "obsidian://open?"
            f"vault={quote(vault_name, safe='')}"
            f"&file={quote(relative_path, safe='')}"
        ),
        "file_path": resolved.as_posix(),
        "relative_path": relative_path,
    }
```

- [ ] **Step 5: Add schema and route**

In `src/kb/api/schemas.py`, add:

```python
class OpenTarget(BaseModel):
    obsidian_uri: str
    file_path: str
    relative_path: str
```

In `src/kb/api/v1.py`, import:

```python
from kb.core.open_targets import build_obsidian_open_target
```

Add route before `@router.get("/notes/{file_id:path}")`:

```python
@router.get("/notes/{file_id:path}/open-target")
def get_note_open_target(file_id: str):
    if ctx.config is None or not ctx.config.obsidian.enabled:
        return responses.provider_not_configured("Obsidian integration is disabled")
    try:
        return responses.ok(build_obsidian_open_target(ctx.config, file_id))
    except (FileNotFoundError, ValueError) as exc:
        return _not_found_or_path_error(exc)
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_open_targets.py tests/test_api_v1.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/kb/core/open_targets.py src/kb/api/schemas.py src/kb/api/v1.py tests/test_open_targets.py tests/test_api_v1.py
git commit -m "feat: add obsidian open target api"
```

---

### Task 5: Web UI Open in Obsidian

**Files:**
- Modify: `web/src/api.ts`
- Modify: `web/src/pages/NoteDetail.vue`
- Modify: `web/src/pages/SearchPage.vue`
- Modify: `web/src/pages/ChatPage.vue`

- [ ] **Step 1: Add API client type and method**

In `web/src/api.ts`, add:

```ts
export interface OpenTarget {
  obsidian_uri: string
  file_path: string
  relative_path: string
}
```

Inside `api`, add:

```ts
getOpenTarget(fileId: string) {
  return request<OpenTarget>(`/notes/${encodeURIComponent(fileId)}/open-target`)
},
```

- [ ] **Step 2: Update NoteDetail primary action**

In `web/src/pages/NoteDetail.vue`, add imports as needed:

```ts
import { api, type NoteDetail, type OpenTarget } from '../api'
```

Add state:

```ts
const openTarget = ref<OpenTarget | null>(null)
const openError = ref<string | null>(null)
```

After the note loads, fetch target:

```ts
try {
  openTarget.value = await api.getOpenTarget(fileId.value)
} catch (e) {
  openError.value = e instanceof Error ? e.message : 'Unable to open in Obsidian'
}
```

Add method:

```ts
function openInObsidian() {
  if (openTarget.value?.obsidian_uri) {
    window.location.href = openTarget.value.obsidian_uri
  }
}
```

Replace the primary edit-style action with:

```vue
<button
  class="btn btn-primary"
  :disabled="!openTarget"
  @click="openInObsidian"
>
  Open in Obsidian
</button>
```

Keep existing edit behavior only as a secondary action if it already exists:

```vue
<button class="btn btn-secondary" @click="isEditing = true">
  Edit in Web
</button>
```

- [ ] **Step 3: Add search result open action**

In `web/src/pages/SearchPage.vue`, add a method:

```ts
async function openResultInObsidian(fileId: string) {
  const target = await api.getOpenTarget(fileId)
  window.location.href = target.obsidian_uri
}
```

For each search result action area, add:

```vue
<button class="btn btn-secondary" @click.prevent="openResultInObsidian(result.note.file_id)">
  Open
</button>
```

- [ ] **Step 4: Add chat source open action**

In `web/src/pages/ChatPage.vue`, add:

```ts
async function openSourceInObsidian(fileId: string) {
  const target = await api.getOpenTarget(fileId)
  window.location.href = target.obsidian_uri
}
```

Near each source item, add:

```vue
<button class="btn btn-secondary" @click="openSourceInObsidian(source.file_id)">
  Open
</button>
```

- [ ] **Step 5: Build frontend**

Run:

```powershell
npm run build
```

from `web/`.

Expected: build succeeds. The existing large chunk warning may remain.

- [ ] **Step 6: Commit**

Run:

```powershell
git add web/src/api.ts web/src/pages/NoteDetail.vue web/src/pages/SearchPage.vue web/src/pages/ChatPage.vue
git commit -m "feat: open notes from web in obsidian"
```

---

### Task 6: Configure and Validate `D:\ObsidianVault`

**Files:**
- Modify: `config.toml`
- External filesystem: `D:\ObsidianVault`

- [ ] **Step 1: Ensure editable install points at current project**

Run:

```powershell
pip install -e .
pip show kb
```

Expected: `Editable project location` is `C:\Users\cherry\Desktop\kb`.

- [ ] **Step 2: Run migration command**

Run:

```powershell
kb obsidian init-vault --target D:\ObsidianVault --from-notes C:\Users\cherry\Desktop\kb\notes --from-attachments C:\Users\cherry\Desktop\kb\attachments
```

Expected: command reports copied notes, copied attachments, indexed notes, and vectors.

- [ ] **Step 3: Verify filesystem result**

Run:

```powershell
Test-Path D:\ObsidianVault
Test-Path D:\ObsidianVault\notes
Test-Path D:\ObsidianVault\attachments
Test-Path D:\ObsidianVault\.obsidian
Test-Path D:\ObsidianVault\.kb\kb.db
```

Expected: all commands print `True`.

- [ ] **Step 4: Verify config**

Run:

```powershell
Get-Content config.toml
```

Expected: contains:

```toml
[general]
vault_path = "D:/ObsidianVault"
notes_dir = "notes"
attachments_dir = "attachments"
index_dir = ".kb"

[obsidian]
enabled = true
vault_name = "ObsidianVault"
vault_path = "D:/ObsidianVault"
open_uri_strategy = "file"
```

- [ ] **Step 5: Verify index and search**

Run:

```powershell
kb index --full
kb search "AI"
```

Expected: index succeeds and search returns notes from `D:\ObsidianVault\notes`.

- [ ] **Step 6: Commit config change**

Run:

```powershell
git add config.toml
git commit -m "chore: point kb at obsidian vault"
```

---

### Task 7: Full Verification and Legacy Notes Backup

**Files:**
- External filesystem: `C:\Users\cherry\Desktop\kb\notes`
- External filesystem: `C:\Users\cherry\Desktop\kb\notes.legacy-backup`

- [ ] **Step 1: Run backend tests through current project install**

Run:

```powershell
pip install -e .
python -m pytest -q
```

Expected: tests pass. If tests fail because optional embedding dependencies are unavailable, run the focused suite:

```powershell
python -m pytest tests/test_config.py tests/test_storage.py tests/test_attachments.py tests/test_indexer.py tests/test_cli.py tests/test_api_v1.py tests/test_open_targets.py -q
```

Expected: focused suite passes.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd web
npm run build
cd ..
```

Expected: build succeeds. The known Vite chunk-size warning is acceptable.

- [ ] **Step 3: Start server manually**

Run:

```powershell
.\scripts\start.ps1 -OpenBrowser -SkipWatch
```

Expected: backend and frontend start. Search page can find migrated notes. Note detail shows `Open in Obsidian`.

- [ ] **Step 4: Verify Obsidian URI manually**

In the Web UI, open a migrated note detail and click `Open in Obsidian`.

Expected: Obsidian opens `D:\ObsidianVault` and focuses the selected note.

- [ ] **Step 5: Stop server**

Stop the PowerShell process that was started by `scripts\start.ps1`.

Expected: no backend or Vite process remains running for this task.

- [ ] **Step 6: Rename legacy notes after manual confirmation**

Run only after the user confirms the migrated vault works:

```powershell
Rename-Item -LiteralPath C:\Users\cherry\Desktop\kb\notes -NewName notes.legacy-backup
```

Expected: `C:\Users\cherry\Desktop\kb\notes.legacy-backup` exists and `C:\Users\cherry\Desktop\kb\notes` no longer exists.

- [ ] **Step 7: Commit legacy notes state only if repository tracks it**

Run:

```powershell
git status --short
```

If Git reports tracked deletions or renames under `notes/`, commit them:

```powershell
git add -A notes notes.legacy-backup
git commit -m "chore: archive local notes after obsidian migration"
```

If Git reports no tracked changes for notes, do not commit.

---

## Execution Notes

- Do not delete `C:\Users\cherry\Desktop\kb\notes` during migration.
- Do not migrate old `.kb`; regenerate indexes in `D:\ObsidianVault\.kb`.
- Do not implement an Obsidian plugin in this plan.
- Do not convert `kb` into an Obsidian-dependent service; CLI, API, Web, and MCP must work when Obsidian is closed.
- Keep `source_project` as metadata/frontmatter and Dashboard grouping. Do not rework full source registry in this plan.

## Final Verification

Run:

```powershell
pip install -e .
python -m pytest -q
cd web
npm run build
cd ..
kb index --full
kb search "AI"
```

Expected:

- Python tests pass, or the focused suite from Task 7 passes if optional dependencies block the full suite.
- Frontend build succeeds.
- `kb index --full` indexes `D:\ObsidianVault\notes`.
- `kb search "AI"` returns migrated notes.
- Web UI can open notes in Obsidian through `obsidian://open`.
