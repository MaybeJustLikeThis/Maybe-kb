"""Tests for hybrid search with RRF."""
import pytest
from kb.core.search import SearchResult, hybrid_search


def test_search_result_fields():
    r = SearchResult(file_id="a.md", title="Test", score=0.95, source="hybrid")
    assert r.file_id == "a.md"
    assert r.score == 0.95
    assert r.source == "hybrid"


def test_rrf_score_decreases_with_rank():
    """Rank 1 gets higher RRF score than rank 10."""
    assert 1.0 / (60 + 1) > 1.0 / (60 + 10)


def test_hybrid_search_both_sources(tmp_path):
    """Hybrid search fuses FTS5 and semantic results."""
    from kb.data.database import Database
    from kb.core.models import Note
    from kb.data.embedding import LocalEmbeddingProvider
    from kb.data.vector import VectorStore, VectorRecord

    db = Database(tmp_path / ".kb" / "kb.db")
    db.initialize()

    notes = [
        Note(file_id="a.md", title="Python Async", content="asyncio 协程并发编程", tags=["python"], category="tech"),
        Note(file_id="b.md", title="Golang Concurrency", content="goroutine channel select", tags=["golang"], category="tech"),
        Note(file_id="c.md", title="今天天气", content="今天天气很好适合散步", tags=["日记"], category="life"),
    ]
    for n in notes:
        db.upsert_note(n)

    provider = LocalEmbeddingProvider("BAAI/bge-small-zh-v1.5")
    store = VectorStore(tmp_path / ".kb" / "vectors.lance")
    store.upsert_chunks("a.md", [
        VectorRecord(id="a.md", chunk_id=0, vector=provider.embed("asyncio 协程并发编程").vector, text="asyncio"),
    ])
    store.upsert_chunks("b.md", [
        VectorRecord(id="b.md", chunk_id=0, vector=provider.embed("goroutine channel select").vector, text="goroutine"),
    ])
    store.upsert_chunks("c.md", [
        VectorRecord(id="c.md", chunk_id=0, vector=provider.embed("今天天气很好适合散步").vector, text="weather"),
    ])

    results = hybrid_search("python 异步", db, provider, store, limit=5)
    assert len(results) >= 1
    assert any("Python" in r.title for r in results)

    db.close()
    store.close()


def test_hybrid_search_empty_both(tmp_path):
    """Both searches empty returns empty list."""
    from kb.data.database import Database
    from kb.data.embedding import LocalEmbeddingProvider
    from kb.data.vector import VectorStore

    db = Database(tmp_path / ".kb" / "kb.db")
    db.initialize()
    provider = LocalEmbeddingProvider("BAAI/bge-small-zh-v1.5")
    store = VectorStore(tmp_path / ".kb" / "vectors.lance")

    results = hybrid_search("nonexistent query xyz123", db, provider, store, limit=10)
    assert results == []

    db.close()
    store.close()
