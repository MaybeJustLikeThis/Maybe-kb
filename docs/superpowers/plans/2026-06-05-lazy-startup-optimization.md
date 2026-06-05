# Lazy Startup Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the FastAPI app and ordinary API tests start without loading embedding or LLM providers, while repairing corrupted uncategorized fallback strings.

**Architecture:** Keep `AppContext` as the resource owner, but create the web app with lightweight resources by default. Endpoints that need embeddings or LLMs will request them on demand through existing `ensure_embedding()` and `ensure_llm()` methods. Replace duplicated corrupted fallback literals with a shared constant in the modules being touched.

**Tech Stack:** Python 3.11+, FastAPI, Typer, pytest, existing SQLite/LanceDB abstractions.

---

### Task 1: Prove FastAPI Startup Is Lightweight

**Files:**
- Modify: `tests/test_server.py`
- Verify existing behavior in: `src/kb/server.py`, `src/kb/core/context.py`

- [ ] **Step 1: Write the failing test**

Add this test near the top of `tests/test_server.py`, after the `client` fixture:

```python
def test_create_app_does_not_initialize_ai_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating the web app should not load embedding or LLM providers."""
    vault = tmp_path
    (vault / "notes").mkdir()
    (vault / "attachments").mkdir()
    (vault / ".kb").mkdir()

    def fail_embedding(config):
        raise AssertionError("embedding provider should be lazy")

    def fail_llm(config):
        raise AssertionError("llm provider should be lazy")

    monkeypatch.setattr("kb.core.context.create_embedding_provider", fail_embedding)
    monkeypatch.setattr("kb.core.context.create_llm_provider", fail_llm)

    kb_config = KBConfig(
        vault_path=vault.resolve(),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )

    app = create_app(kb_config)

    assert app.title == "kb"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_server.py::test_create_app_does_not_initialize_ai_providers -q`

Expected: FAIL with `AssertionError: embedding provider should be lazy`.

- [ ] **Step 3: Write minimal implementation**

Change `src/kb/server.py`:

```python
ctx = AppContext.from_config(
    kb_config,
    with_embedding=False,
    with_llm=False,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_server.py::test_create_app_does_not_initialize_ai_providers -q`

Expected: PASS.

### Task 2: Preserve AI Endpoints With On-Demand Providers

**Files:**
- Modify: `src/kb/api/v1.py`
- Modify: `src/kb/routes.py`
- Test: `tests/test_api_v1.py` and `tests/test_server.py`

- [ ] **Step 1: Keep ordinary v1 writes lightweight**

In `src/kb/api/v1.py`, keep note create/update from loading the embedding provider:

```python
def _index_note_if_possible(file_id: str) -> int:
    if ctx.embedding is None:
        return 0
    return index_note_vectors(
        ctx.vault,
        ctx.db,
        ctx.embedding,
        file_id,
        vector_store=ctx.vector_store,
        index_dir=ctx.index_dir,
    )
```

- [ ] **Step 2: Update v1 AI endpoints to request providers lazily**

For `/index/rebuild`, pass `embedding_provider=ctx.ensure_embedding()`.

For `/chat/ask` and `/chat/stream`, use:

```python
embedding = ctx.ensure_embedding()
llm = ctx.ensure_llm()
if llm is None or embedding is None:
    return responses.provider_not_configured(
        "LLM and embedding config required",
    )
```

Then pass local `embedding` and `llm` variables to RAG functions.

- [ ] **Step 3: Update legacy routes to request providers lazily**

In `src/kb/routes.py`, update semantic, related, index, and chat handlers to use `ctx.ensure_embedding()` and `ctx.ensure_llm()` before returning provider-not-configured behavior or running vector/RAG operations.

- [ ] **Step 4: Run focused API tests**

Run: `py -m pytest tests/test_server.py::test_create_app_does_not_initialize_ai_providers tests/test_server.py::test_v1_create_note_does_not_initialize_ai_providers tests/test_api_v1.py::test_v1_list_notes_returns_success_envelope -q`

Expected: all tests PASS.

### Task 3: Repair Uncategorized Fallback Encoding

**Files:**
- Modify: `src/kb/cli.py`
- Modify: `src/kb/core/indexer.py`
- Test: `tests/test_cli.py`, `tests/test_indexer.py`

- [ ] **Step 1: Replace corrupted literals in CLI migrate**

In `src/kb/cli.py`, change:

```python
cat_raw = note.category or "未分类"
```

and ensure move preview/output strings use a readable ASCII arrow such as `->`.

- [ ] **Step 2: Replace corrupted literals in external indexing**

In `src/kb/core/indexer.py`, add:

```python
UNCATEGORIZED_CATEGORY = "未分类"
```

near the module constants, then replace every corrupted uncategorized literal in `index_files()` with `UNCATEGORIZED_CATEGORY`.

- [ ] **Step 3: Run focused fallback tests**

Run: `py -m pytest tests/test_cli.py::test_kb_migrate_no_category_goes_to_weifenlei tests/test_indexer.py::test_index_files_external_sources_handles_non_mapping_frontmatter -q`

Expected: both tests PASS.

### Task 4: Final Verification

**Files:**
- No new modifications unless verification reveals a regression.

- [ ] **Step 1: Run focused backend tests**

Run: `py -m pytest tests/test_server.py tests/test_api_v1.py tests/test_cli.py::test_kb_migrate_no_category_goes_to_weifenlei tests/test_indexer.py::test_index_files_external_sources_handles_non_mapping_frontmatter -q`

Expected: PASS. If the full files remain slow, report exact timeout or failing test.

- [ ] **Step 2: Run frontend build**

Run: `npm run build` from `web/`

Expected: exit code 0. Chunk-size warning may remain because route-level code splitting is not in this first optimization batch.

- [ ] **Step 3: Review diff**

Run: `git diff -- src/kb/server.py src/kb/api/v1.py src/kb/routes.py src/kb/cli.py src/kb/core/indexer.py tests/test_server.py docs/superpowers/plans/2026-06-05-lazy-startup-optimization.md`

Expected: diff only contains lazy startup, provider-on-demand, fallback string cleanup, and the plan.
