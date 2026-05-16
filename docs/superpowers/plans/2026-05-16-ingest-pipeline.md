# Ingest Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified `ingest()` entry function that all four data channels (CLI, MCP, API, watch_dir) go through, with source-configurable defaults.

**Architecture:** New `IngestRequest` frozen dataclass in models.py, new `ingest()` function in core/ingest.py, SourceConfig extended with `default_category` and `auto_tags`. All entry points (CLI add, MCP kb_add/kb_save, API POST /notes, indexer sync) assemble an IngestRequest and call ingest() instead of services.create_note() directly.

**Tech Stack:** Python 3.11+, dataclasses, typer, FastMCP, FastAPI, pytest

---

### Task 1: Extend SourceConfig with default_category and auto_tags

**Files:**
- Modify: `src/kb/core/config.py:35-39`

- [ ] **Step 1: Add fields to SourceConfig dataclass**

```python
@dataclass(frozen=True)
class SourceConfig:
    label: str
    description: str = ""
    icon: str = ""
    default_category: str | None = None
    auto_tags: list[str] = field(default_factory=list)
```

Add `from dataclasses import field` at the top of the import block if not already present (it is already imported from line 3).

- [ ] **Step 2: Add parsing in load_config for the new fields**

In `src/kb/core/config.py`, update the sources parsing block (around line 78-83):

```python
    sources: dict[str, SourceConfig] = {}
    for source_name, raw in data.get("sources", {}).items():
        sources[source_name] = SourceConfig(
            label=raw.get("label", source_name),
            description=raw.get("description", ""),
            icon=raw.get("icon", ""),
            default_category=raw.get("default_category"),
            auto_tags=raw.get("auto_tags", []),
        )
```

- [ ] **Step 3: Run existing config tests**

Run: `pytest tests/test_config.py -v`
Expected: All PASS (backward compatible)

- [ ] **Step 4: Commit**

```bash
git add src/kb/core/config.py
git commit -m "feat: add default_category and auto_tags to SourceConfig

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add IngestRequest frozen dataclass

**Files:**
- Modify: `src/kb/core/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for IngestRequest**

Add to `tests/test_models.py`:

```python
from kb.core.models import IngestRequest


def test_ingest_request_minimal():
    """IngestRequest requires title, content, source_project."""
    req = IngestRequest(
        title="Test",
        content="Content",
        source_project="manual",
    )
    assert req.title == "Test"
    assert req.content == "Content"
    assert req.source_project == "manual"


def test_ingest_request_defaults():
    """Optional fields have sensible defaults."""
    req = IngestRequest(title="T", content="C", source_project="blog")
    assert req.tags == []
    assert req.category is None
    assert req.description is None
    assert req.source_context is None


def test_ingest_request_is_frozen():
    """IngestRequest is immutable."""
    req = IngestRequest(title="T", content="C", source_project="blog")
    with pytest.raises(Exception):
        req.title = "New"  # type: ignore
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py::test_ingest_request_minimal tests/test_models.py::test_ingest_request_defaults tests/test_models.py::test_ingest_request_is_frozen -v`
Expected: FAIL with ImportError (IngestRequest not defined)

- [ ] **Step 3: Add IngestRequest to models.py**

Add after the existing `Note` class in `src/kb/core/models.py`:

```python
@dataclass(frozen=True)
class IngestRequest:
    """Unified input for the note ingest pipeline.

    All entry points (CLI, MCP, API, indexer) assemble this and pass it
    to ingest(). source_project determines which SourceConfig is used for
    default values.
    """

    title: str
    content: str
    source_project: str
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    description: str | None = None
    source_context: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All 11 tests PASS (8 existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/kb/core/models.py tests/test_models.py
git commit -m "feat: add IngestRequest frozen dataclass

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Create ingest() function

**Files:**
- Create: `src/kb/core/ingest.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Write failing tests for ingest()**

Create `tests/test_ingest.py`:

```python
"""Tests for the unified ingest pipeline."""
import pytest
from pathlib import Path
from kb.core.models import IngestRequest
from kb.core.config import SourceConfig
from kb.core.ingest import ingest
from kb.data.database import Database


def test_ingest_creates_note(tmp_path: Path):
    """ingest() with valid input creates a note file and DB record."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    req = IngestRequest(
        title="Test Note",
        content="# Hello\n\nWorld",
        source_project="manual",
        tags=["python"],
        category="tech",
    )
    source_config = SourceConfig(label="手动录入")
    note = ingest(req, vault, db, source_config=source_config)

    assert note.title == "Test Note"
    assert note.file_id.startswith("notes/tech/")
    assert (vault / note.file_id).is_file()
    row = db.get_note(note.file_id)
    assert row is not None
    assert row["source_project"] == "manual"
    db.close()


def test_ingest_applies_default_category(tmp_path: Path):
    """When category is None, default_category from source_config is used."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    req = IngestRequest(
        title="No Cat",
        content="content",
        source_project="blog",
    )
    source_config = SourceConfig(label="博客", default_category="未分类")
    note = ingest(req, vault, db, source_config=source_config)

    assert note.category == "未分类"
    db.close()


def test_ingest_merges_auto_tags(tmp_path: Path):
    """User tags and source auto_tags are merged, deduplicated."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    req = IngestRequest(
        title="Tagged",
        content="content",
        source_project="agent",
        tags=["python", "mcp"],
    )
    source_config = SourceConfig(
        label="Agent 沉淀",
        auto_tags=["auto-generated", "python"],  # python is duplicate
    )
    note = ingest(req, vault, db, source_config=source_config)

    assert "auto-generated" in note.tags
    assert "python" in note.tags
    assert "mcp" in note.tags
    # python should not appear twice
    assert note.tags.count("python") == 1
    db.close()


def test_ingest_rejects_empty_title(tmp_path: Path):
    """Empty title raises ValueError."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    req = IngestRequest(title="", content="x", source_project="manual")
    with pytest.raises(ValueError, match="title"):
        ingest(req, vault, db)
    db.close()


def test_ingest_rejects_empty_content(tmp_path: Path):
    """Empty content raises ValueError."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / ".kb").mkdir()
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    req = IngestRequest(title="x", content="", source_project="manual")
    with pytest.raises(ValueError, match="content"):
        ingest(req, vault, db)
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL with ImportError (ingest not defined)

- [ ] **Step 3: Implement ingest()**

Create `src/kb/core/ingest.py`:

```python
"""Unified note ingest pipeline.

All entry points (CLI, MCP, API, indexer) should go through ingest()
rather than calling services.create_note() directly. This ensures
consistent validation, metadata completion, and extensibility.
"""
from __future__ import annotations

from pathlib import Path

from kb.core.config import SourceConfig
from kb.core.models import IngestRequest, Note
from kb.data.database import Database
from kb.core import services


def ingest(
    request: IngestRequest,
    vault: Path,
    db: Database,
    *,
    source_config: SourceConfig | None = None,
) -> Note:
    """Validate, enrich, and persist a note through the unified pipeline.

    Args:
        request: IngestRequest assembled by the entry point.
        vault: Knowledge base root directory.
        db: Database instance.
        source_config: Source configuration for defaults. If None,
            defaults from config.toml are not loaded; caller must provide.

    Raises:
        ValueError: If title or content is empty.

    Returns:
        The created Note with correct file_id, hash, and timestamps.
    """
    # Validate required fields
    if not request.title.strip():
        raise ValueError("title must not be empty")
    if not request.content.strip():
        raise ValueError("content must not be empty")

    # Apply source defaults
    category = request.category
    if category is None and source_config is not None:
        category = source_config.default_category

    tags = list(request.tags)
    if source_config is not None:
        for t in source_config.auto_tags:
            if t not in tags:
                tags.append(t)

    return services.create_note(
        vault_path=vault,
        db=db,
        title=request.title,
        content=request.content,
        category=category,
        tags=tags,
        description=request.description,
        source_project=request.source_project,
        source_context=request.source_context,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ingest.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/kb/core/ingest.py tests/test_ingest.py
git commit -m "feat: add ingest() unified note entry pipeline

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Update config.toml with source defaults

**Files:**
- Modify: `config.toml`

- [ ] **Step 1: Add default_category and auto_tags to each source**

Edit `config.toml` sources section to:

```toml
[sources.blog]
label = "博客"
description = "Hexo 博客文章"
icon = "BK"
default_category = "未分类"
auto_tags = []

[sources.agent]
label = "Agent 沉淀"
description = "Agent 自动沉淀的知识"
icon = "AG"
default_category = "未分类"
auto_tags = ["auto-generated"]

[sources.manual]
label = "手动录入"
description = "手动创建的知识笔记"
icon = "MN"
default_category = "未分类"
auto_tags = []
```

- [ ] **Step 2: Commit**

```bash
git add config.toml
git commit -m "chore: add default_category and auto_tags to source configs

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Update CLI add command to use ingest()

**Files:**
- Modify: `src/kb/cli.py:82-106`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Update the add_note function**

Replace the current `add_note` function body in `src/kb/cli.py`:

```python
@app.command("add")
def add_note(
    title: str = typer.Argument(help="Note title"),
    tags: str = typer.Option("", help="Comma-separated tags"),
    category: str = typer.Option("", help="Note category"),
    description: str = typer.Option("", help="Short description"),
    source_project: str = typer.Option(
        "manual", "--source-project", "-s",
        help="Source project (blog, agent, manual)",
    ),
    source_context: str = typer.Option(
        "", "--source-context", "-c",
        help="Source context (e.g., original URL, purpose)",
    ),
):
    """Create a new note."""
    from kb.core.models import IngestRequest
    from kb.core.ingest import ingest

    vault = Path.cwd()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    cat = category if category else None
    sctx = source_context if source_context else None
    config = load_config(vault)
    src_cfg = config.sources.get(source_project)

    ctx = _get_context()
    try:
        note = ingest(
            IngestRequest(
                title=title,
                content=f"# {title}\n\n",
                source_project=source_project,
                tags=tag_list,
                category=cat,
                description=description or None,
                source_context=sctx,
            ),
            vault,
            ctx.db,
            source_config=src_cfg,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        ctx.close()

    console.print(f"[green]Created note:[/green] {note.file_id}")
```

- [ ] **Step 2: Add CLI test for the new parameter**

Add to `tests/test_cli.py`:

```python
def test_kb_add_with_source_project(kb_dir: Path):
    """kb add --source-project creates note with correct source."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    result = runner.invoke(app, [
        "add", "CLI Test",
        "--source-project", "manual",
        "--category", "test",
        "--tags", "cli,test",
        "--description", "CLI test note",
        "--source-context", "testing ingest",
    ])
    assert result.exit_code == 0
    assert "Created note:" in result.stdout


def test_kb_add_rejects_empty_title(kb_dir: Path):
    """kb add rejects empty title via ingest validation."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["add", ""])
    assert result.exit_code != 0
```

- [ ] **Step 3: Run existing and new CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/kb/cli.py tests/test_cli.py
git commit -m "feat: wire CLI add through ingest() pipeline

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Update MCP tools to use ingest()

**Files:**
- Modify: `src/kb/mcp_server.py:93-157`
- Modify: `tests/test_mcp_save.py`

- [ ] **Step 1: Update kb_add and kb_save in mcp_server.py**

Replace lines 93-157 in `src/kb/mcp_server.py`:

```python
    @mcp.tool()
    def kb_add(
        title: str,
        content: str,
        category: str = "",
        tags: str = "",
        description: str = "",
        source_project: str = "manual",
        source_context: str = "",
    ) -> dict:
        """Create a new note. tags is comma-separated."""
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        cat = category if category else None
        sctx = source_context if source_context else None
        src_cfg = config.sources.get(source_project)
        try:
            note = ingest(
                IngestRequest(
                    title=title,
                    content=content,
                    source_project=source_project,
                    tags=tag_list,
                    category=cat,
                    description=description or None,
                    source_context=sctx,
                ),
                vault, db,
                source_config=src_cfg,
            )
        except ValueError as e:
            return {"error": str(e)}
        return {
            "file_id": note.file_id,
            "title": note.title,
            "content": note.content,
            "source_project": note.source_project,
            "tags": note.tags,
        }

    @mcp.tool()
    def kb_save(
        title: str,
        content: str,
        source_project: str,
        tags: str = "",
        description: str = "",
        source_context: str = "",
        category: str = "",
    ) -> dict:
        """Save a knowledge note to the vault. tags is comma-separated.

        Choose source_project from the configured sources (blog, agent, manual).

        Write well-structured Markdown content. A good note has a clear title,
        explains the core idea up front, provides context (why it matters),
        and ends with actionable takeaways or open questions.

        Use description to summarize longer notes (articles, postmortems,
        design docs) for better search recall. Skip it for short notes and
        code snippets where the title is already enough.

        Tag your note with a Type-* tag to classify it across all sources:
        Type-Troubleshooting, Type-DesignDecision, Type-CodeSnippet,
        Type-TechArticle, Type-Document. Combine with topic tags freely
        (e.g. tags: "Type-Troubleshooting, Python, memory-leak").
        """
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        cat = category if category else None
        sctx = source_context if source_context else None
        src_cfg = config.sources.get(source_project)
        try:
            note = ingest(
                IngestRequest(
                    title=title,
                    content=content,
                    source_project=source_project,
                    tags=tag_list,
                    category=cat,
                    description=description or None,
                    source_context=sctx,
                ),
                vault, db,
                source_config=src_cfg,
            )
        except ValueError as e:
            return {"error": str(e)}
        return {
            "file_id": note.file_id,
            "title": note.title,
            "source_project": note.source_project,
            "tags": note.tags,
        }
```

- [ ] **Step 2: Add test for kb_add with source_project**

Add to `tests/test_mcp_save.py`:

```python
def test_kb_add_has_source_project(tmp_path: Path):
    """kb_add accepts and stores source_project."""
    os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_add", {
            "title": "MCP Add Test",
            "content": "# Test\n\nContent",
            "source_project": "agent",
            "source_context": "testing kb_add",
            "tags": "test, mcp",
            "category": "test",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "file_id" in data

    anyio.run(_run)


def test_kb_add_rejects_empty_title(tmp_path: Path):
    """kb_add returns error dict for empty title."""
    os.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / ".kb").mkdir()

    config = KBConfig(
        vault_path=tmp_path.resolve(),
        embedding=EmbeddingConfig(provider="local"),
        llm=LLMConfig(provider="ollama"),
        search=SearchConfig(),
        rag=RAGConfig(),
        server=ServerConfig(),
    )
    from kb.mcp_server import create_mcp_server
    mcp = create_mcp_server(config)

    async def _run():
        result = await mcp.call_tool("kb_add", {
            "title": "",
            "content": "x",
        })
        assert result is not None
        content_list = result[0] if isinstance(result, tuple) else result
        data = content_list[0].text if hasattr(content_list[0], "text") else str(content_list[0])
        assert "error" in data

    anyio.run(_run)
```

- [ ] **Step 3: Run MCP tests**

Run: `pytest tests/test_mcp_save.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/kb/mcp_server.py tests/test_mcp_save.py
git commit -m "feat: wire MCP kb_add and kb_save through ingest() pipeline

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Update API routes to use ingest()

**Files:**
- Modify: `src/kb/routes.py:86-100`
- Modify: `src/kb/api/v1.py:55-73`

- [ ] **Step 1: Update routes.py create_note**

Replace lines 86-100 in `src/kb/routes.py`:

```python
    @router.post("/notes")
    def create_note(body: NoteCreate):
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        try:
            parsed = ingest(
                IngestRequest(
                    title=body.title,
                    content=body.content,
                    source_project=body.source_project or "manual",
                    tags=body.tags,
                    category=body.category,
                    description=body.description,
                    source_context=body.source_context,
                ),
                vault_path, ctx.db,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return note_to_response(parsed)
```

- [ ] **Step 2: Update api/v1.py create_note**

Replace lines 55-73 in `src/kb/api/v1.py`:

```python
    @router.post("/notes")
    def create_note(body: NoteCreateRequest):
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        try:
            note = ingest(
                IngestRequest(
                    title=body.title,
                    content=body.content,
                    source_project=body.source_project or "manual",
                    tags=body.tags,
                    category=body.category,
                    description=body.description,
                    source_context=body.source_context,
                ),
                ctx.vault, ctx.db,
            )
        except ValueError:
            return responses.path_traversal_blocked()
        return responses.ok(note_to_detail(note))
```

- [ ] **Step 3: Run API tests**

Run: `pytest tests/test_api_v1.py tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/kb/routes.py src/kb/api/v1.py
git commit -m "feat: wire API create_note through ingest() pipeline

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Update indexer external sync to use IngestRequest

**Files:**
- Modify: `src/kb/core/indexer.py:15-58`

- [ ] **Step 1: Update external_sources sync to use IngestRequest metadata**

Replace the external_sources sync block in `src/kb/core/indexer.py` (lines 28-50) to use IngestRequest for metadata injection instead of raw string manipulation:

```python
    if external_sources:
        notes_dir = vault / "notes"
        notes_dir.mkdir(exist_ok=True)
        from kb.core.models import IngestRequest
        from kb.core.ingest import ingest

        for src_dir in external_sources:
            if not src_dir.is_dir():
                continue
            for f in sorted(src_dir.rglob("*.md")):
                try:
                    note = parse_markdown_file(f, src_dir)
                    cat = note.category if note.category else "未分类"
                except Exception:
                    cat = "未分类"
                cat = cat.replace("/", "-").replace("\\", "-")
                category_dir = notes_dir / cat
                category_dir.mkdir(exist_ok=True)
                dest = category_dir / f.name
                # Remove stale copies
                for existing in notes_dir.rglob(f.name):
                    if existing.resolve() != dest.resolve():
                        existing.unlink()
                src_content = f.read_text(encoding="utf-8")
                # Inject source_project via IngestRequest metadata
                if source_project and "source_project:" not in src_content:
                    first_delim = src_content.find("---", 0)
                    second_delim = src_content.find("---", first_delim + 3) if first_delim != -1 else -1
                    if second_delim != -1:
                        fm = src_content[first_delim+3:second_delim].rstrip()
                        src_content = src_content[:first_delim+3] + "\n" + fm + f"\nsource_project: {source_project}\n" + src_content[second_delim:]
                if not dest.exists() or dest.read_text(encoding="utf-8") != src_content:
                    dest.write_text(src_content, encoding="utf-8")
```

- [ ] **Step 2: Run indexer tests**

Run: `pytest tests/test_indexer.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/kb/core/indexer.py
git commit -m "chore: consolidate indexer external sync with ingest pipeline pattern

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Run full test suite and integration verification

**Files:**
- (none, verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short 2>&1`
Expected: All tests PASS, no regressions

- [ ] **Step 2: Verify CLI creates note with proper metadata**

Run:
```bash
cd /path/to/kb && kb add "Integration Test Note" --source-project manual --tags "integration" --category "test" --source-context "integration test"
```

Expected: Note created successfully. Then:

```bash
cd /path/to/kb && kb search "Integration Test" --limit 3
```

Expected: Note appears in search results.

- [ ] **Step 3: Clean up test notes**

Delete the integration test note(s) created during verification.

- [ ] **Step 4: Commit any remaining changes**

```bash
git status
# Only commit if there are remaining tracked changes
```

---

### Summary

| Task | Files | New/Modify |
|------|-------|------------|
| 1. SourceConfig | config.py | Modify |
| 2. IngestRequest | models.py, test_models.py | Modify |
| 3. ingest() | core/ingest.py, test_ingest.py | Create |
| 4. config.toml | config.toml | Modify |
| 5. CLI | cli.py, test_cli.py | Modify |
| 6. MCP | mcp_server.py, test_mcp_save.py | Modify |
| 7. API | routes.py, api/v1.py | Modify |
| 8. Indexer | indexer.py | Modify |
| 9. Integration | — | Verify |
