"""RAG orchestration — hybrid search + context assembly + LLM generation."""
from __future__ import annotations

from kb.core.search import hybrid_search, SearchResult
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.llm import LLMProvider, LLMResponse
from kb.data.vector import VectorStore

RAG_SYSTEM_PROMPT = """你是个人知识库助手。请基于用户提供的笔记内容回答问题。如果笔记中没有相关信息，请如实告知。回答时引用具体的笔记标题和内容片段。保持回答简洁准确，使用中文回复。"""


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


def rag_query(
    query: str,
    db: Database,
    embed_provider: EmbeddingProvider,
    store: VectorStore,
    llm: LLMProvider,
    top_k: int = 5,
) -> LLMResponse:
    """Run a full RAG query: hybrid search → format → generate."""
    results = hybrid_search(query, db, embed_provider, store, limit=top_k)
    context = format_context(results, db)
    prompt = build_rag_prompt(query, context)
    return llm.generate(prompt, system_prompt=RAG_SYSTEM_PROMPT)


def rag_query_stream(
    query: str,
    db: Database,
    embed_provider: EmbeddingProvider,
    store: VectorStore,
    llm: LLMProvider,
    top_k: int = 5,
):
    """Run RAG query with streaming response."""
    results = hybrid_search(query, db, embed_provider, store, limit=top_k)
    context = format_context(results, db)
    prompt = build_rag_prompt(query, context)
    yield from llm.generate_stream(prompt, system_prompt=RAG_SYSTEM_PROMPT)
