"""Tests for RAG orchestration."""
from kb.data.models import Note
from kb.data.vector import VectorRecord
from kb.core.search import ChunkSearchResult
from kb.core.rag import (
    format_context, build_rag_prompt, RAG_SYSTEM_PROMPT,
    rag_query_stream, build_rag_sources, rag_source_to_dict,
)

from tests._fakes import FakeEmbeddingProvider, FakeLLM, FakeVectorStore


def test_format_context_empty():
    """Empty results produces placeholder text."""
    result = format_context([])
    assert "未找到" in result


def test_format_context_chunk_level():
    """format_context accepts ChunkSearchResult and outputs structured context."""
    results = [
        ChunkSearchResult(
            file_id="a.md", chunk_id=0, text="Python asyncio basics",
            section_path=["## 并发"], score=0.9, source="hybrid", title="Python Guide",
        ),
    ]
    context = format_context(results)
    assert "Python Guide" in context
    assert "## 并发" in context
    assert "Python asyncio basics" in context
    assert "[1]" in context


def test_format_context_respects_budget():
    """format_context truncates at max_context_chars."""
    results = [
        ChunkSearchResult(
            file_id="a.md", chunk_id=0, text="x" * 500,
            section_path=["## A"], score=0.9, source="fts5", title="A",
        ),
        ChunkSearchResult(
            file_id="b.md", chunk_id=0, text="y" * 500,
            section_path=["## B"], score=0.8, source="fts5", title="B",
        ),
    ]
    context = format_context(results, max_context_chars=600)
    assert "[1]" in context
    assert "..." in context


def test_build_rag_prompt_contains_query_and_context():
    prompt = build_rag_prompt("测试问题", "笔记内容")
    assert "测试问题" in prompt
    assert "笔记内容" in prompt


def test_rag_system_prompt_exists():
    assert len(RAG_SYSTEM_PROMPT) > 50
    assert "知识库" in RAG_SYSTEM_PROMPT
    assert "不编造" in RAG_SYSTEM_PROMPT


def test_rag_query_returns_llm_response(db):
    """Verify rag_query signature and orchestration pattern."""
    from kb.core.rag import RAGResponse, rag_query

    llm = FakeLLM(response_text="Mocked answer", model="mock")
    provider = FakeEmbeddingProvider(dimension=512)
    store = FakeVectorStore()

    response = rag_query("test", db, provider, store, llm, top_k=3)
    assert isinstance(response, RAGResponse)
    assert response.text == "Mocked answer"
    assert response.sources == []


def test_rag_query_stream_yields_chunks(db):
    """rag_query_stream collects and joins all streamed LLMResponse chunks."""
    llm = FakeLLM(stream_chunks=["streamed", " answer"])
    provider = FakeEmbeddingProvider(dimension=512)
    store = FakeVectorStore()

    chunks = list(rag_query_stream("test query", db, provider, store, llm))

    assert len(chunks) == 2
    joined = "".join(c.text for c in chunks)
    assert joined == "streamed answer"


def test_rag_query_handles_llm_failure(db):
    """rag_query returns error RAGResponse when LLM raises."""
    from kb.core.rag import RAGResponse, rag_query

    llm = FakeLLM(raises=ConnectionError("Ollama not reachable"))
    provider = FakeEmbeddingProvider(dimension=3)
    store = FakeVectorStore()

    response = rag_query("test", db, provider, store, llm)
    assert isinstance(response, RAGResponse)
    assert "失败" in response.text
    assert response.tokens_used == 0
    assert response.model == ""
    assert response.sources == []


def test_rag_query_stream_handles_failure(db):
    """rag_query_stream yields error chunk when LLM raises."""
    from kb.core.rag import rag_query_stream

    llm = FakeLLM(raises=RuntimeError("stream interrupted"))
    provider = FakeEmbeddingProvider(dimension=3)
    store = FakeVectorStore()

    chunks = list(rag_query_stream("test", db, provider, store, llm))
    assert len(chunks) == 1
    assert "失败" in chunks[0].text


def test_build_rag_sources_includes_note_metadata(db):
    """RAG sources expose note identity, snippet, source, and attachments."""
    from kb.core.rag import build_rag_sources

    db.upsert_note(Note(
        file_id="notes/doc/imported.md",
        title="Imported Doc",
        content="Important imported content for the user.",
        source_project="upload",
        source_path="attachments/2026/06/doc.pdf",
        content_type="pdf",
        attachments=["attachments/2026/06/doc.pdf"],
    ))
    result = ChunkSearchResult(
        file_id="notes/doc/imported.md",
        chunk_id=0,
        text="Important imported content",
        section_path=["## Intro"],
        score=0.5,
        source="hybrid",
        title="Imported Doc",
    )

    sources = build_rag_sources([result], db, snippet_chars=12)

    assert len(sources) == 1
    source = sources[0]
    assert source.file_id == "notes/doc/imported.md"
    assert source.title == "Imported Doc"
    assert source.snippet == "Important im..."
    assert source.section_path == ["## Intro"]
    assert source.source_project == "upload"
    assert source.source_path == "attachments/2026/06/doc.pdf"
    assert source.content_type == "pdf"
    assert source.attachments == ["attachments/2026/06/doc.pdf"]


def test_rag_source_to_dict_includes_section_path():
    from kb.core.rag import RAGSource
    source = RAGSource(
        file_id="a.md", title="A", snippet="...", section_path=["## S"],
    )
    d = rag_source_to_dict(source)
    assert d["section_path"] == ["## S"]
    assert d["file_id"] == "a.md"


def test_rag_query_returns_sources(db):
    """rag_query returns answer metadata plus traceable sources."""
    from kb.core.rag import RAGResponse, rag_query

    db.upsert_note(Note(
        file_id="notes/a.md",
        title="Source A",
        content="Pinia store setup notes",
        tags=["pinia"],
        attachments=["attachments/a.png"],
    ))

    llm = FakeLLM(response_text="Mocked answer", model="mock")
    provider = FakeEmbeddingProvider(dimension=3)
    store = FakeVectorStore()
    store.upsert_chunks("notes/a.md", [
        VectorRecord(
            id="notes/a.md",
            chunk_id=0,
            vector=[0.1, 0.2, 0.3],
            text="Pinia store setup notes",
            section_path=["## Setup"],
            content_type="paragraph",
        ),
    ])

    response = rag_query(
        "Pinia",
        db,
        provider,
        store,
        llm,
        top_k=3,
    )

    assert isinstance(response, RAGResponse)
    assert response.text == "Mocked answer"
    assert response.sources[0].file_id == "notes/a.md"
    assert response.sources[0].attachments == ["attachments/a.png"]


def test_rag_end_to_end_chunk_level(db, tmp_path):
    """Full RAG flow: search -> context -> generate returns chunk-aware sources."""
    from kb.core.rag import RAGResponse, rag_query
    from kb.data.vector import VectorStore

    db.upsert_note(Note(
        file_id="notes/python.md",
        title="Python 异步编程",
        content="## asyncio 基础\n\nasyncio 是 Python 的异步编程框架。\n\n## 协程\n\n使用 async/await 语法定义协程。",
        tags=["python"],
    ))

    llm = FakeLLM(response_text="asyncio 是 Python 的异步框架", model="mock")
    provider = FakeEmbeddingProvider(dimension=512)

    store = VectorStore(tmp_path / ".kb" / "vectors.lance")
    store.upsert_chunks("notes/python.md", [
        VectorRecord(
            id="notes/python.md", chunk_id=0,
            vector=[0.1] * 512,
            text="asyncio 是 Python 的异步编程框架",
            section_path=["## asyncio 基础"],
            content_type="paragraph",
        ),
        VectorRecord(
            id="notes/python.md", chunk_id=1,
            vector=[0.1] * 512,
            text="使用 async/await 语法定义协程",
            section_path=["## 协程"],
            content_type="paragraph",
        ),
    ])

    response = rag_query(
        "什么是 asyncio",
        db, provider, store, llm, top_k=3,
    )

    assert isinstance(response, RAGResponse)
    assert "asyncio" in response.text
    assert len(response.sources) >= 1
    assert response.sources[0].file_id == "notes/python.md"
    store.close()
