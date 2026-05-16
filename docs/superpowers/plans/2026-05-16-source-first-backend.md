# Source-First Architecture — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the type-first model from the backend — replace `entry_type` with `source_project` as the primary dimension across config, models, services, queries, API, and MCP server.

**Architecture:** Config-driven source definitions (`[sources.*]` in config.toml), source-aware list queries, simplified dashboard/taxonomy responses, and MCP tools that accept `source_project` as a parameter instead of auto-deriving it from `entry_type`.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLite, dataclasses

---

## Task 1: Config — Replace kb_types with sources

**Files:**
- Modify: `src/kb/core/config.py:33-113`
- Modify: `config.toml:19-47`

- [ ] **Step 1: Add SourceConfig dataclass and update KBConfig**

Replace `KBTypeConfig` with `SourceConfig` in `src/kb/core/config.py`:

```python
# Remove lines 33-38 (KBTypeConfig class), replace with:
@dataclass
class SourceConfig:
    label: str
    description: str = ""
    icon: str = ""


@dataclass
class KBConfig:
    vault_path: Path
    search: SearchConfig = field(default_factory=SearchConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    sources: dict[str, SourceConfig] = field(default_factory=dict)
```

Remove line 59 (`kb_types: dict[str, KBTypeConfig]`). Remove line 112 (`kb_types=kb_types`).

- [ ] **Step 2: Update load_config() to parse [sources.*]**

Replace lines 79-81 and 112 in `load_config()`:

```python
    # Remove kb_types parsing (lines 79-81), replace with:
    sources: dict[str, SourceConfig] = {}
    for source_name, raw in data.get("sources", {}).items():
        sources[source_name] = SourceConfig(
            label=raw.get("label", source_name),
            description=raw.get("description", ""),
            icon=raw.get("icon", ""),
        )

    return KBConfig(
        vault_path=vault_path,
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
        ),
        server=ServerConfig(
            host=server_data.get("host", "127.0.0.1"),
            port=server_data.get("port", 8420),
            watch_dir=server_data.get("watch_dir"),
        ),
        sources=sources,
    )
```

- [ ] **Step 3: Update config.toml**

Replace `[kb_types.*]` sections (lines 19-47) with:

```toml
[sources.blog]
label = "博客"
description = "Hexo 博客文章"
icon = "BK"

[sources.agent]
label = "Agent 沉淀"
description = "Agent 自动沉淀的知识"
icon = "AG"

[sources.manual]
label = "手动录入"
description = "手动创建的知识笔记"
icon = "MN"
```

- [ ] **Step 4: Commit**

```bash
git add src/kb/core/config.py config.toml
git commit -m "refactor: replace kb_types with sources in config model"
```

---

## Task 2: Models — Remove entry_type from Note

**Files:**
- Modify: `src/kb/core/models.py:58,88,98,116`

- [ ] **Step 1: Remove entry_type from Note dataclass**

In `src/kb/core/models.py`:
- Line 58: remove `entry_type: str | None = None`
- Line 88: remove `entry_type = frontmatter.get("type")`
- Line 98: remove `"type"` from `managed_keys`
- Line 116: remove `entry_type=entry_type,`

```python
# Line 58 — remove the field, keep everything else
@dataclass
class Note:
    file_id: str
    title: str
    description: str | None = None
    content: str = ""
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    status: str = "published"
    file_hash: str | None = None
    source_project: str | None = None
    source_path: str | None = None
    source_context: str | None = None
    content_type: str = "markdown"
    extra_frontmatter: dict[str, Any] = field(default_factory=dict)
```

In `from_frontmatter`:
```python
        status = frontmatter.get("status", "published")
        source_project = frontmatter.get("source_project")
        source_path = frontmatter.get("source_path")
        source_context = frontmatter.get("source_context")
        content_type = frontmatter.get("content_type", "markdown")

        managed_keys = {
            "title", "tags", "categories", "category",
            "date", "created", "updated", "description",
            "attachments", "status",
            "source_project", "source_path",
            "source_context", "content_type",
        }
```

And in the return:
```python
        return cls(
            file_id=file_path,
            title=title,
            description=frontmatter.get("description"),
            content=content,
            category=category,
            tags=tags,
            attachments=attachments,
            created_at=created,
            updated_at=updated,
            status=status,
            file_hash=file_hash,
            extra_frontmatter=extra,
            source_project=source_project,
            source_path=source_path,
            source_context=source_context,
            content_type=content_type,
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/kb/core/models.py
git commit -m "refactor: remove entry_type from Note model"
```

---

## Task 3: Serializers — Remove entry_type from serialization

**Files:**
- Modify: `src/kb/core/serializers.py:31,57`

- [ ] **Step 1: Remove entry_type from note_row_to_dict and note_to_response**

In `note_row_to_dict` (line 31): remove `"entry_type": row_dict.get("entry_type"),`

In `note_to_response` (line 57): remove `"entry_type": note.entry_type,`

- [ ] **Step 2: Commit**

```bash
git add src/kb/core/serializers.py
git commit -m "refactor: remove entry_type from serializers"
```

---

## Task 4: Storage — Remove entry_type from frontmatter write

**Files:**
- Modify: `src/kb/data/storage.py:73-74`

- [ ] **Step 1: Remove entry_type from _build_frontmatter_yaml**

Remove lines 73-74:
```python
    if note.entry_type:
        data["type"] = note.entry_type
```

- [ ] **Step 2: Commit**

```bash
git add src/kb/data/storage.py
git commit -m "refactor: remove entry_type from markdown frontmatter serialization"
```

---

## Task 5: Services — Remove entry_type from create_note

**Files:**
- Modify: `src/kb/core/services.py:61,96`

- [ ] **Step 1: Remove entry_type parameter and field from create_note**

In `create_note` signature (line 61): remove `entry_type: str | None = None,`

In Note construction (line 96): remove `entry_type=entry_type,`

- [ ] **Step 2: Commit**

```bash
git add src/kb/core/services.py
git commit -m "refactor: remove entry_type from create_note service"
```

---

## Task 6: Queries — Remove type distribution, add source labels

**Files:**
- Modify: `src/kb/core/queries.py:45-57,60-65,107,126-127,151`

- [ ] **Step 1: Remove get_type_distribution function**

Delete the entire `get_type_distribution()` function (lines 45-57).

- [ ] **Step 2: Update get_source_projects to resolve labels from config.sources**

Replace lines 60-65:

```python
def get_source_projects(ctx: AppContext) -> list[dict]:
    """Return source project distribution with labels from config."""
    labels: dict[str, str] = {}
    if ctx.config and ctx.config.sources:
        labels = {name: s.label for name, s in ctx.config.sources.items()}
    return [
        count_item(row["source_project"], row["count"], labels.get(row["source_project"]))
        for row in ctx.db.list_source_projects()
    ]
```

- [ ] **Step 3: Update get_dashboard_stats — remove type_distribution**

In `get_dashboard_stats()` (line 107): remove `"type_distribution": get_type_distribution(ctx),`

- [ ] **Step 4: Update get_taxonomy — remove entry_types**

In `get_taxonomy()` (line 151): remove `"entry_types": get_type_distribution(ctx),`

- [ ] **Step 5: Remove entry_type from get_dashboard_activity**

Remove lines 126-127:
```python
        if note.get("entry_type"):
            description_parts.append(f"Type: {note['entry_type']}")
```

- [ ] **Step 6: Add source_project parameter to list_notes**

```python
def list_notes(
    ctx: AppContext,
    *,
    category: str | None,
    tag: str | None,
    source_project: str | None = None,
    limit: int,
    offset: int,
) -> PageResult:
    """List note summaries with pagination metadata."""
    rows = ctx.db.list_notes(
        category=category, tag=tag, source_project=source_project,
        limit=limit, offset=offset,
    )
    total = ctx.db.count_notes(category=category, tag=tag, source_project=source_project)
    return PageResult(
        items=[note_row_to_summary(ctx.db, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 7: Commit**

```bash
git add src/kb/core/queries.py
git commit -m "refactor: remove type distribution, add source labels and source_project filter"
```

---

## Task 7: Database — Add source_project filter to list_notes

**Files:**
- Modify: `src/kb/data/database.py:205-233`

- [ ] **Step 1: Add source_project parameter to list_notes and count_notes**

In `list_notes` signature, add `source_project: str | None = None` parameter.
Add filter condition after category check:

```python
    def list_notes(
        self,
        category: str | None = None,
        tag: str | None = None,
        source_project: str | None = None,
        status: str = "published",
        limit: int = 100,
        sort: str | None = None,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """List notes with optional filters."""
        conn = self._connect()
        query = "SELECT n.* FROM notes n"
        conditions = ["n.status = ?"]
        params: list[Any] = [status]

        if tag:
            query += " JOIN note_tags t ON n.id = t.note_id"
            conditions.append("t.tag = ?")
            params.append(tag)

        if category:
            conditions.append("n.category = ?")
            params.append(category)

        if source_project:
            conditions.append("n.source_project = ?")
            params.append(source_project)

        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY n.updated_at DESC, n.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        return conn.execute(query, params).fetchall()
```

Also update `count_notes` if it doesn't support `source_project`:
Add `source_project: str | None = None` parameter and matching condition.

- [ ] **Step 2: Commit**

```bash
git add src/kb/data/database.py
git commit -m "feat: add source_project filter to list_notes and count_notes"
```

---

## Task 8: API Routes — Remove type-distribution, add /sources

**Files:**
- Modify: `src/kb/routes.py:244-256` (remove type-distribution route)
- Modify: `src/kb/routes.py:95` (remove entry_type from create_note call)
- Modify: `src/kb/api/v1.py:33-46,62-65` (update list_notes, create_note, add /sources)

- [ ] **Step 1: Remove type-distribution route from routes.py**

Delete lines 244-256 (the `get_type_distribution` route).

Also remove `entry_type` from the `create_note` call in the create route:
- Remove line referencing `entry_type=body.entry_type` in the `services.create_note()` arguments.

- [ ] **Step 2: Add source_project filter to v1 list_notes**

In `src/kb/api/v1.py`, update `list_notes`:

```python
    @router.get("/notes")
    def list_notes(
        category: str | None = Query(None),
        tag: str | None = Query(None),
        source_project: str | None = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        result = queries.list_notes(
            ctx,
            category=category,
            tag=tag,
            source_project=source_project,
            limit=limit,
            offset=offset,
        )
        return responses.page(
            result.items,
            limit=result.limit,
            offset=result.offset,
            total=result.total,
        )
```

- [ ] **Step 3: Add /api/v1/sources endpoint**

Add after the dashboard routes:

```python
    @router.get("/sources")
    def get_sources():
        sources = []
        if ctx.config and ctx.config.sources:
            for name, s in ctx.config.sources.items():
                sources.append({
                    "name": name,
                    "label": s.label,
                    "description": s.description,
                    "icon": s.icon,
                })
        return responses.ok({"sources": sources})
```

- [ ] **Step 4: Commit**

```bash
git add src/kb/routes.py src/kb/api/v1.py
git commit -m "refactor: remove type-distribution route, add /sources endpoint"
```

---

## Task 9: API Schemas — Remove entry_type from Pydantic models

**Files:**
- Modify: `src/kb/api/schemas.py:39,61,75,101,115`

- [ ] **Step 1: Remove entry_type from NoteBase, NoteCreateRequest, NoteUpdateRequest**

Remove `entry_type: str | None = None` from:
- `NoteBase` (line 39)
- `NoteCreateRequest` (line 61)
- `NoteUpdateRequest` (line 75)

- [ ] **Step 2: Remove entry_types and type_distribution from response schemas**

In `TaxonomyResponse` (line 101): remove `entry_types: list[CountItem] = Field(default_factory=list)`

In `DashboardStats` (line 115): remove `type_distribution: list[CountItem] = Field(default_factory=list)`

- [ ] **Step 3: Commit**

```bash
git add src/kb/api/schemas.py
git commit -m "refactor: remove entry_type and type_distribution from API schemas"
```

---

## Task 10: MCP Server — Remove kb_types lookup, update save tools

**Files:**
- Modify: `src/kb/mcp_server.py:77,113-143,145-208`

- [ ] **Step 1: Remove entry_type from kb_read response**

Line 77: remove `"entry_type": note.entry_type,`

- [ ] **Step 2: Refactor _save_note — remove entry_type, accept source_project**

Replace `_save_note` (lines 113-143):

```python
    def _save_note(
        source_project: str,
        title: str,
        content: str,
        source_context: str = "",
        tags: str = "",
    ) -> dict:
        """Shared helper for kb_save_* tools."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        try:
            note = services.create_note(
                vault, db, title, content,
                source_project=source_project or None,
                source_context=source_context or None,
                tags=tag_list,
            )
        except ValueError:
            return {"error": "Path traversal blocked"}
        return {
            "file_id": note.file_id,
            "title": note.title,
            "source_project": note.source_project,
            "tags": note.tags,
        }
```

- [ ] **Step 3: Update each kb_save_* tool**

Remove `entry_type` first argument, pass `source_project` as the first param. Example:

```python
    @mcp.tool()
    def kb_save_tech_article(
        title: str,
        content: str,
        source_project: str = "",
        source_context: str = "",
        tags: str = "",
    ) -> dict:
        """Save a 技术文章 (tech article). 适合：技术分析、教程、原理解析。
        写清楚：核心技术点、适用场景、局限性。"""
        return _save_note(source_project, title, content,
                          source_context, tags)
```

Do the same for `kb_save_troubleshooting`, `kb_save_design_decision`, `kb_save_code_snippet`, `kb_save_document`.

- [ ] **Step 4: Commit**

```bash
git add src/kb/mcp_server.py
git commit -m "refactor: remove kb_types MCP lookup, pass source_project directly"
```

---

## Task 11: Tests — Update all test files

**Files:**
- Modify: `tests/test_models.py:63-106`
- Modify: `tests/test_services.py:171-254`
- Modify: `tests/test_queries.py:64-85`
- Modify: `tests/test_dashboard.py:23-36,133-147`
- Modify: `tests/test_api_v1.py:87,98,163,173,194`
- Modify: `tests/test_integration.py:156`
- Modify: `tests/test_mcp_save.py`
- Delete: `tests/test_types_config.py`

- [ ] **Step 1: Update test_models.py**

Remove `test_note_new_source_fields` entry_type assertions (lines 68,74), `test_note_new_fields_defaults` entry_type assertion (line 84), and `test_note_from_frontmatter_extracts_new_fields` entry_type and `"type"` assertions (lines 93,96,102):

```python
def test_note_new_source_fields():
    """Note supports source tracking fields."""
    note = Note(
        file_id="notes/test/example.md",
        title="测试笔记",
        content="内容",
        source_project="kb",
        source_path="/home/user/projects/kb",
        source_context="在实现搜索功能时的笔记",
        content_type="markdown",
    )
    assert note.source_project == "kb"
    assert note.source_path == "/home/user/projects/kb"
    assert note.source_context == "在实现搜索功能时的笔记"
    assert note.content_type == "markdown"


def test_note_new_fields_defaults():
    """New fields have sensible defaults."""
    note = Note(file_id="x", title="x")
    assert note.source_project is None
    assert note.source_path is None
    assert note.source_context is None
    assert note.content_type == "markdown"


def test_note_from_frontmatter_extracts_new_fields():
    """from_frontmatter parses source fields."""
    fm = {
        "title": "Test",
        "source_project": "my-app",
        "source_path": "/code/my-app",
        "source_context": "debugging login bug",
        "content_type": "markdown",
    }
    note = Note.from_frontmatter(title="Test", frontmatter=fm, file_path="notes/x.md")
    assert note.source_project == "my-app"
    assert note.source_path == "/code/my-app"
    assert note.source_context == "debugging login bug"
    assert note.content_type == "markdown"
```

- [ ] **Step 2: Update test_services.py**

Remove `entry_type` from test fixtures:
- `test_note_response_includes_new_fields`: remove `entry_type="tech-article"` from Note, remove assertion for `resp["entry_type"]`
- `test_note_row_to_dict_includes_new_fields`: remove `entry_type` from UPDATE, remove assertion
- `test_create_note_with_entry_type_and_source`: rename to `test_create_note_with_source`, remove `entry_type="design-decision"`, remove entry_type assertions
- `test_update_note_can_set_source_fields`: remove `entry_type="troubleshooting"`, remove assertion

- [ ] **Step 3: Update test_queries.py**

Remove `entry_type="tech-article"` from Note in `test_get_dashboard_stats_unifies_sources` (line 73).
Remove assertion for `stats["type_distribution"]` (line 83).

- [ ] **Step 4: Update test_dashboard.py**

Remove `entry_type="tech-article"` from note1 (line 27), `entry_type="document"` from note2 (line 34).
Delete `test_get_type_distribution` test function (lines 133-147).
Update `test_get_source_projects` — the source_project value is now `"kb"` (from fixtures), make sure assertions match.

- [ ] **Step 5: Update test_api_v1.py**

Remove `entry_type` from create/update payloads and assertions about entry_types/type_distribution in taxonomy/dashboard responses.

- [ ] **Step 6: Update test_integration.py**

Remove assertion about `entry_type` column (line 156).

- [ ] **Step 7: Update test_mcp_save.py**

Update all test assertions — remove `entry_type` from expected responses, check for `source_project` instead.

- [ ] **Step 8: Remove test_types_config.py**

```bash
rm tests/test_types_config.py
```

- [ ] **Step 9: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass. Fix any failures.

- [ ] **Step 10: Commit**

```bash
git add tests/
git commit -m "test: update tests for source-first, remove type-related test cases"
```

---

## Task 12: Data Migration

**Files:**
- Modify: `.kb/kb.db` (SQL UPDATE)

- [ ] **Step 1: Run the backfill SQL**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('.kb/kb.db')
conn.execute(\"UPDATE notes SET source_project = 'blog' WHERE source_project IS NULL AND status = 'published'\")
conn.commit()
print(f'Rows updated: {conn.total_changes}')
conn.close()
"
```

Expected: "Rows updated: 24"

- [ ] **Step 2: Verify**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('.kb/kb.db')
rows = conn.execute('SELECT source_project, COUNT(*) FROM notes GROUP BY source_project').fetchall()
for r in rows:
    print(f'source_project={r[0]}, count={r[1]}')
"
```

Expected: `source_project=blog, count=24`

- [ ] **Step 3: Commit**

No file changes to commit — the migration is run once against the local database.

---

## Verification Checklist

- [ ] `config.toml` has `[sources.*]` sections (no `[kb_types.*]`)
- [ ] `KBTypeConfig` and `kb_types` removed from `config.py`
- [ ] `entry_type` removed from `Note` model
- [ ] `entry_type` removed from all serializers
- [ ] `entry_type` removed from frontmatter write
- [ ] `entry_type` removed from `create_note()` service
- [ ] `get_type_distribution()` function deleted
- [ ] `/api/type-distribution` route deleted (returns 404)
- [ ] `/api/v1/sources` returns sources config with correct shape
- [ ] `/api/v1/notes?source_project=blog` returns only blog notes
- [ ] `/api/v1/dashboard` response has no `type_distribution` field
- [ ] `/api/v1/taxonomy` response has no `entry_types` field
- [ ] `source_projects` in dashboard response includes `label` from config
- [ ] MCP `kb_read` response has no `entry_type`
- [ ] MCP `_save_note` no longer references `config.kb_types`
- [ ] All 24 notes have `source_project = 'blog'`
- [ ] `pytest tests/ -v` passes with all tests updated
