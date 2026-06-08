# Changelog

## 0.2.0 (2026-06-08)

### Bug Fixes

- **RAG error handling**: `rag_query()` and `rag_query_stream()` now catch exceptions and return graceful error responses instead of crashing. Added `logging` for error visibility.
- **RAG context budget**: Replaced fixed 800-char per-note truncation with `max_context_chars=6000` total budget. Notes are included in full; only the last note is truncated when the budget is exceeded.
- **Vector store safety**: `VectorStore.delete_note()` now validates input instead of using manual SQL escaping.
- **MCP kb_read**: Distinguishes `not_found` from `path_traversal_blocked` instead of returning `None` for both.

### Refactoring

- **Legacy API removed**: Deleted `routes.py` (327 lines) and its `/api` prefix mount. All endpoints now live under `/api/v1` with consistent `{data, meta, error}` envelope responses. Web UI was already using `/api/v1` exclusively.
- **Architecture fix**: Moved `models.py` from `core/` to `data/` to fix reverse dependency (`data` no longer imports from `core`).
- **Code deduplication**:
  - Extracted shared `index_note_if_possible()` to `core/indexer.py` (was duplicated in `mcp_server.py` and `api/v1.py`).
  - Extracted `_create_note()` helper in `mcp_server.py` (eliminated ~100 lines of duplication between `kb_add` and `kb_save`).
  - Added `_build_messages()` to `LLMProvider` base class (eliminated duplicate message building in Ollama and OpenAI providers).
- **Config cleanup**: Renamed `RAGConfig.truncate_chars` to `max_context_chars` with updated default (6000).

### Breaking Changes

- `/api/*` endpoints no longer exist. Use `/api/v1/*` instead.
- `from kb.core.models import Note` → `from kb.data.models import Note`
- MCP `kb_read` returns error dicts (`{"error": "not_found"}`) instead of `None`.
- `format_context()` parameter renamed from `truncate_chars` to `max_context_chars`.

## 0.1.0

Initial release.
