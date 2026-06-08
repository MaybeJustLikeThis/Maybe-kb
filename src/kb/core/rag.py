"""RAG orchestration — hybrid search + context assembly + LLM generation."""
from __future__ import annotations

from dataclasses import dataclass, field

from kb.core.search import hybrid_search, SearchResult
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.llm import LLMProvider, LLMResponse
from kb.data.vector import VectorStore

RAG_SYSTEM_PROMPT = """你是个人知识库助手。请基于用户提供的笔记内容回答问题。如果笔记中没有相关信息，请如实告知。回答时引用具体的笔记标题和内容片段。保持回答简洁准确，使用中文回复。"""


@dataclass(frozen=True)
class RAGSource:
    """Traceable source returned with a RAG answer."""

    file_id: str
    title: str
    snippet: str
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
    results: list[SearchResult],
    db: Database,
    truncate_chars: int = 800,
) -> str:
    """Format search results into a context block for the LLM prompt."""
    if not results:
        return "（知识库中未找到相关内容）"

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        note = db.get_note(r.file_id)
        if note is None:
            continue
        content = note["content"] or ""
        if len(content) > truncate_chars:
            content = content[:truncate_chars] + "..."
        parts.append(f"[{i}] {note['title']}\n{content}")

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
    results: list[SearchResult],
    db: Database,
    snippet_chars: int = 240,
) -> list[RAGSource]:
    """Build traceable source metadata for RAG responses."""
    sources: list[RAGSource] = []
    for result in results:
        note = db.get_note(result.file_id)
        if note is None:
            continue
        content = note["content"] or ""
        sources.append(RAGSource(
            file_id=note["id"],
            title=note["title"],
            snippet=_snippet(content, snippet_chars),
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
    """Run a full RAG query: hybrid search → format → generate."""
    try:
        results = hybrid_search(query, db, embed_provider, store, limit=top_k)
        context = format_context(results, db)
        prompt = build_rag_prompt(query, context)
        answer = llm.generate(prompt, system_prompt=RAG_SYSTEM_PROMPT)
        return RAGResponse(
            text=answer.text,
            tokens_used=answer.tokens_used,
            model=answer.model,
            sources=build_rag_sources(results, db),
        )
    except Exception as exc:
        return RAGResponse(
            text=f"抱歉，LLM 调用失败：{exc}",
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
        context = format_context(results, db)
        prompt = build_rag_prompt(query, context)
        yield from llm.generate_stream(prompt, system_prompt=RAG_SYSTEM_PROMPT)
    except Exception as exc:
        yield LLMResponse(text=f"[错误] {exc}", tokens_used=0, model="")
