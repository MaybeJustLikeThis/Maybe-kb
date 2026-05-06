"""Tests for RAG orchestration."""
from pathlib import Path
from kb.core.search import SearchResult
from kb.core.rag import format_context, build_rag_prompt, RAG_SYSTEM_PROMPT


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
    from kb.core.rag import rag_query
    from kb.data.llm import LLMResponse
    from kb.data.database import Database
    from kb.data.embedding import EmbeddingProvider, EmbeddingResult
    from kb.data.vector import VectorStore, VectorRecord

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
    assert isinstance(response, LLMResponse)
    assert response.text == "Mocked answer"
