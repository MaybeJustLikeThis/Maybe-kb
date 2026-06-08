"""RAG orchestration — hybrid search + context assembly + LLM generation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from kb.core.search import hybrid_search, ChunkSearchResult
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.llm import LLMProvider, LLMResponse
from kb.data.vector import VectorStore

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """你是个人知识库助手。严格基于提供的笔记回答问题。

规则：
1. 只使用笔记中的信息回答，不编造、不推测
2. 引用时标注来源编号，格式：[1]、[2]
3. 如果笔记中没有相关信息，直接回答"知识库中没有找到相关内容"
4. 如果笔记信息不足以完整回答，说明哪些部分能找到、哪些找不到
5. 保持回答简洁准确，使用中文

回答格式：
- 先给出核心答案
- 再列出引用的笔记片段
- 如果需要补充说明，放在最后"""


@dataclass(frozen=True)
class RAGSource:
    """Traceable source returned with a RAG answer."""
    file_id: str
    title: str
    snippet: str
    section_path: list[str] = field(default_factory=list)
    source_project: str | None = None
    source_path: str | None = None
    content_type: str = "markdown"
    attachments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RAGResponse:
    """LLM answer plus traceable knowledge-base sources."""
    text: str
    tokens_used: int
    model: str
    sources: list[RAGSource] = field(default_factory=list)


def format_context(
    results: list[ChunkSearchResult],
    max_context_chars: int = 6000,
) -> str:
    """Format chunk-level search results into a context block for the LLM.

    Each chunk is rendered with its source number, title, and section path.
    Budget is enforced strictly by character count.
    """
    if not results:
        return "（知识库中未找到相关内容）"

    parts: list[str] = []
    total_chars = 0

    for i, r in enumerate(results, 1):
        section_str = " > ".join(r.section_path) if r.section_path else ""
        header = f"[{i}] {r.title}"
        if section_str:
            header += f" > {section_str}"

        block = f"{header}\n{r.text}"
        remaining = max_context_chars - total_chars
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining] + "..."
        parts.append(block)
        total_chars += len(block)

    if not parts:
        return "（知识库中未找到相关内容）"

    return "\n\n".join(parts)


def build_rag_prompt(query: str, context: str) -> str:
    """Build the user prompt for RAG generation."""
    return f"用户问题：{query}\n\n参考笔记：\n{context}"


def _snippet(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_rag_sources(
    results: list[ChunkSearchResult],
    db: Database,
    snippet_chars: int = 240,
) -> list[RAGSource]:
    """Build traceable source metadata from chunk-level results.

    Deduplicates by file_id — one RAGSource per unique note.
    """
    seen: set[str] = set()
    sources: list[RAGSource] = []
    for r in results:
        if r.file_id in seen:
            continue
        seen.add(r.file_id)
        note = db.get_note(r.file_id)
        if note is None:
            continue
        content = note["content"] or ""
        sources.append(RAGSource(
            file_id=note["id"],
            title=note["title"],
            snippet=_snippet(content, snippet_chars),
            section_path=r.section_path,
            source_project=note["source_project"],
            source_path=note["source_path"],
            content_type=note["content_type"] or "markdown",
            attachments=db.get_attachments(note["id"]),
        ))
    return sources


def rag_source_to_dict(source: RAGSource) -> dict:
    """Convert RAGSource to an API/MCP-ready dict."""
    return {
        "file_id": source.file_id,
        "title": source.title,
        "snippet": source.snippet,
        "section_path": source.section_path,
        "source_project": source.source_project,
        "source_path": source.source_path,
        "content_type": source.content_type,
        "attachments": source.attachments,
    }


def rag_query(
    query: str,
    db: Database,
    embed_provider: EmbeddingProvider,
    store: VectorStore,
    llm: LLMProvider,
    top_k: int = 5,
) -> RAGResponse:
    """Run a full RAG query: hybrid search -> format -> generate."""
    try:
        results = hybrid_search(query, db, embed_provider, store, limit=top_k)
        context = format_context(results)
        prompt = build_rag_prompt(query, context)
        answer = llm.generate(prompt, system_prompt=RAG_SYSTEM_PROMPT)
        return RAGResponse(
            text=answer.text,
            tokens_used=answer.tokens_used,
            model=answer.model,
            sources=build_rag_sources(results, db),
        )
    except Exception as exc:
        logger.error("RAG query failed: %s", exc, exc_info=True)
        return RAGResponse(
            text=f"抱歉，查询失败：{exc}",
            tokens_used=0,
            model="",
            sources=[],
        )


def rag_query_stream(
    query: str,
    db: Database,
    embed_provider: EmbeddingProvider,
    store: VectorStore,
    llm: LLMProvider,
    top_k: int = 5,
):
    """Run RAG query with streaming response."""
    try:
        results = hybrid_search(query, db, embed_provider, store, limit=top_k)
        context = format_context(results)
        prompt = build_rag_prompt(query, context)
        yield from llm.generate_stream(prompt, system_prompt=RAG_SYSTEM_PROMPT)
    except Exception as exc:
        logger.error("RAG query failed: %s", exc, exc_info=True)
        yield LLMResponse(text=f"抱歉，查询失败：{exc}", tokens_used=0, model="")
