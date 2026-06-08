# 更新日志

## 0.2.0 (2026-06-08)

### 修复

- **RAG 错误处理**：`rag_query()` 和 `rag_query_stream()` 现在会捕获异常并返回友好的错误信息，不再直接崩溃。同时增加了 `logging` 日志输出。
- **RAG 上下文预算**：将原来每条笔记固定截断 800 字符的策略，改为总预算 `max_context_chars=6000`（约 2000 token）。笔记内容完整放入上下文，仅在超出预算时截断最后一条。
- **向量存储安全**：`VectorStore.delete_note()` 改用输入校验，替代原来的手动 SQL 转义。
- **MCP kb_read**：区分"笔记不存在"和"路径穿越拦截"两种错误，不再统一返回 `None`。

### 重构

- **移除旧版 API**：删除 `routes.py`（327 行）及 `/api` 前缀路由。所有接口统一到 `/api/v1`，返回标准 `{data, meta, error}` 响应格式。Web UI 此前已全部使用 `/api/v1`。
- **修复架构违规**：将 `models.py` 从 `core/` 移至 `data/`，消除 `data` 层反向依赖 `core` 层的问题。
- **代码去重**：
  - 提取共享函数 `index_note_if_possible()` 到 `core/indexer.py`（此前在 `mcp_server.py` 和 `api/v1.py` 中各有一份）。
  - 在 `mcp_server.py` 中提取 `_create_note()` 辅助函数（消除 `kb_add` 与 `kb_save` 之间约 100 行重复代码）。
  - 在 `LLMProvider` 基类中添加 `_build_messages()` 方法（消除 Ollama 和 OpenAI Provider 中重复的消息构建逻辑）。
- **配置清理**：`RAGConfig.truncate_chars` 重命名为 `max_context_chars`，默认值更新为 6000。

### 不兼容变更

- `/api/*` 接口已移除，请使用 `/api/v1/*`。
- `from kb.core.models import Note` → `from kb.data.models import Note`
- MCP `kb_read` 返回错误字典（如 `{"error": "not_found"}`）而非 `None`。
- `format_context()` 参数从 `truncate_chars` 改为 `max_context_chars`。

## 0.1.0

首次发布。
