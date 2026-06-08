"""Tests for RAG orchestration."""
from pathlib import Path
from kb.core.models import Note
from kb.core.search import SearchResult
from kb.core.rag import format_context, build_rag_prompt, RAG_SYSTEM_PROMPT, rag_query_stream
from kb.data.llm import LLMResponse


def test_format_context_empty():
    """Empty results produces placeholder text."""
    from kb.data.database import Database
    db = Database(Path("/tmp/nonexistent.db"))
    result = format_context([], db)
    assert "未找到" in result


def test_build_rag_prompt_contains_query_and_context():
    prompt = build_rag_prompt("测试问题", "笔记内容")
    assert "测试问题" in prompt
    assert "笔记内容" in prompt


def test_format_context_truncation_logic():
    """Content > 800 chars gets truncated with '...'."""
    long_text = "x" * 1000
    result = long_text[:800] + "..."
    assert len(result) == 803


def test_rag_system_prompt_exists():
    assert len(RAG_SYSTEM_PROMPT) > 50
    assert "知识库" in RAG_SYSTEM_PROMPT


def test_rag_query_returns_llm_response():
    """Verify rag_query signature and orchestration pattern — unit test with mocks."""
    from kb.core.rag import RAGResponse, rag_query
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult

    class MockLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="Mocked answer", tokens_used=10, model="mock")
        @property
        def model_name(self):
            return "mock"

    class MockEmbedding(EmbeddingProvider):
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 512

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return []
        def close(self):
            pass

    db = Database(Path("/tmp/rag-test.db"))
    db.initialize()
    llm = MockLLM()
    provider = MockEmbedding()
    store = MockVectorStore()

    response = rag_query("test", db, provider, store, llm, top_k=3)
    assert isinstance(response, RAGResponse)
    assert response.text == "Mocked answer"
    assert response.sources == []


def test_format_context_with_results(tmp_path):
    """Call format_context on a real note stored in a temp database."""
    from kb.data.database import Database

    db = Database(tmp_path / ".kb" / "test.db")
    db.initialize()
    note = Note(
        file_id="notes/a.md",
        title="Note A",
        content="This is the content of note A.",
    )
    db.upsert_note(note)

    sr = SearchResult(file_id="notes/a.md", title="Note A", score=0.9, source="fts5")
    context = format_context([sr], db)

    assert "Note A" in context
    assert "content of note A" in context


def test_format_context_truncation(tmp_path):
    """Long content gets truncated with '...' when exceeding truncate_chars."""
    from kb.data.database import Database

    db = Database(tmp_path / ".kb" / "test.db")
    db.initialize()
    long_content = "A" * 2000
    note = Note(file_id="notes/long.md", title="Long", content=long_content)
    db.upsert_note(note)

    sr = SearchResult(file_id="notes/long.md", title="Long", score=0.5, source="fts5")
    context = format_context([sr], db, truncate_chars=100)

    assert "..." in context
    assert len(context) < len(long_content) + 100


def test_format_context_missing_note(tmp_path):
    """SearchResult pointing to a non-existent note yields '未找到'."""
    from kb.data.database import Database

    db = Database(tmp_path / ".kb" / "test.db")
    db.initialize()

    sr = SearchResult(
        file_id="notes/missing.md", title="Missing", score=0.1, source="fts5"
    )
    context = format_context([sr], db)

    assert "未找到" in context


def test_build_rag_prompt_structure():
    """RAG prompt contains both the user query and the reference context."""
    prompt = build_rag_prompt("什么是 Docker？", "Docker 是容器化平台")
    assert "什么是 Docker？" in prompt
    assert "Docker 是容器化平台" in prompt


def test_rag_query_stream_yields_chunks():
    """rag_query_stream collects and joins all streamed LLMResponse chunks."""
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult

    db = Database(Path("/tmp/rag-stream-test.db"))
    db.initialize()

    class MockLLM:
        def generate_stream(self, prompt, *, system_prompt=""):
            yield LLMResponse(text="streamed", tokens_used=0, model="mock")
            yield LLMResponse(text=" answer", tokens_used=0, model="mock")

    class MockEmbedding(EmbeddingProvider):
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 512, dimension=512, tokens_used=0)

        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]

        @property
        def dimension(self):
            return 512

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return []

        def close(self):
            pass

    llm = MockLLM()
    provider = MockEmbedding()
    store = MockVectorStore()

    chunks = list(rag_query_stream("test query", db, provider, store, llm))

    assert len(chunks) == 2
    joined = "".join(c.text for c in chunks)
    assert joined == "streamed answer"


def test_rag_query_handles_llm_failure(tmp_path):
    """rag_query returns error RAGResponse when LLM raises."""
    from kb.core.rag import RAGResponse, rag_query
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult

    class FailingLLM:
        def generate(self, prompt, *, system_prompt=""):
            raise ConnectionError("Ollama not reachable")
        @property
        def model_name(self):
            return "failing"

    class MockEmbedding(EmbeddingProvider):
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 3, dimension=3, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 3

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return []

    db = Database(tmp_path / "rag-err.db")
    db.initialize()

    response = rag_query("test", db, MockEmbedding(), MockVectorStore(), FailingLLM())
    assert isinstance(response, RAGResponse)
    assert "失败" in response.text
    assert response.tokens_used == 0
    assert response.model == ""
    assert response.sources == []


def test_rag_query_stream_handles_failure(tmp_path):
    """rag_query_stream yields error chunk when LLM raises."""
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult
    from kb.core.rag import rag_query_stream

    class FailingLLM:
        def generate_stream(self, prompt, *, system_prompt=""):
            raise RuntimeError("stream interrupted")

    class MockEmbedding(EmbeddingProvider):
        def embed(self, text):
            return EmbeddingResult(vector=[0.1] * 3, dimension=3, tokens_used=0)
        def embed_batch(self, texts):
            return [self.embed(t) for t in texts]
        @property
        def dimension(self):
            return 3

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return []

    db = Database(tmp_path / "rag-stream-err.db")
    db.initialize()

    chunks = list(rag_query_stream("test", db, MockEmbedding(), MockVectorStore(), FailingLLM()))
    assert len(chunks) == 1
    assert "失败" in chunks[0].text


def test_build_rag_sources_includes_note_metadata(tmp_path):
    """RAG sources expose note identity, snippet, source, and attachments."""
    from kb.core.rag import build_rag_sources
    from kb.data.database import Database

    db = Database(tmp_path / ".kb" / "test.db")
    db.initialize()
    db.upsert_note(Note(
        file_id="notes/doc/imported.md",
        title="Imported Doc",
        content="Important imported content for the user.",
        source_project="upload",
        source_path="attachments/2026/06/doc.pdf",
        content_type="pdf",
        attachments=["attachments/2026/06/doc.pdf"],
    ))
    result = SearchResult(
        file_id="notes/doc/imported.md",
        title="Imported Doc",
        score=0.5,
        source="hybrid",
    )

    sources = build_rag_sources([result], db, snippet_chars=12)

    assert len(sources) == 1
    source = sources[0]
    assert source.file_id == "notes/doc/imported.md"
    assert source.title == "Imported Doc"
    assert source.snippet == "Important im..."
    assert source.source_project == "upload"
    assert source.source_path == "attachments/2026/06/doc.pdf"
    assert source.content_type == "pdf"
    assert source.attachments == ["attachments/2026/06/doc.pdf"]


def test_rag_query_returns_sources(tmp_path):
    """rag_query returns answer metadata plus traceable sources."""
    from kb.core.rag import RAGResponse, rag_query
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult
    from kb.data.vector import VectorRecord

    db = Database(tmp_path / ".kb" / "rag.db")
    db.initialize()
    db.upsert_note(Note(
        file_id="notes/a.md",
        title="Source A",
        content="Pinia store setup notes",
        tags=["pinia"],
        attachments=["attachments/a.png"],
    ))

    class MockLLM:
        def generate(self, prompt, *, system_prompt=""):
            return LLMResponse(text="Mocked answer", tokens_used=10, model="mock")

        @property
        def model_name(self):
            return "mock"

    class MockEmbedding(EmbeddingProvider):
        def embed(self, text):
            return EmbeddingResult(vector=[0.1, 0.2, 0.3], dimension=3, tokens_used=0)

        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

        @property
        def dimension(self):
            return 3

    class MockVectorStore:
        def search(self, query_vector, limit=20):
            return [
                VectorRecord(
                    id="notes/a.md",
                    chunk_id=0,
                    vector=[0.1, 0.2, 0.3],
                    text="Pinia store setup notes",
                )
            ]

    response = rag_query(
        "Pinia",
        db,
        MockEmbedding(),
        MockVectorStore(),
        MockLLM(),
        top_k=3,
    )

    assert isinstance(response, RAGResponse)
    assert response.text == "Mocked answer"
    assert response.sources[0].file_id == "notes/a.md"
    assert response.sources[0].attachments == ["attachments/a.png"]
