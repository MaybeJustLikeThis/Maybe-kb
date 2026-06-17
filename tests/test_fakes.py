"""Behavior tests for the shared canonical test doubles in tests/_fakes.py.

These pin the doubles' parameter surface so any test that imports them
can rely on the documented behavior.
"""
from kb.data.embedding import EmbeddingResult
from kb.data.llm import LLMResponse
from kb.data.vector import VectorRecord

from tests._fakes import (
    FakeEmbeddingProvider,
    FakeLLM,
    FakeRepository,
    FakeVectorStore,
)


def test_fake_embedding_provider_dimension_and_determinism():
    provider = FakeEmbeddingProvider(dimension=8)
    r = provider.embed("hello")
    assert isinstance(r, EmbeddingResult)
    assert r.dimension == 8
    assert len(r.vector) == 8
    assert provider.embed("hello").vector == r.vector  # deterministic
    assert provider.dimension == 8
    batch = provider.embed_batch(["a", "bb"])
    assert len(batch) == 2 and all(b.dimension == 8 for b in batch)


def test_fake_llm_generate_returns_configured_text_and_records():
    llm = FakeLLM(response_text="answer")
    resp = llm.generate("prompt", system_prompt="sys")
    assert isinstance(resp, LLMResponse)
    assert resp.text == "answer"
    assert llm.recorded_prompts == ["prompt"]
    assert llm.model_name


def test_fake_llm_generate_raises_when_configured():
    llm = FakeLLM(raises=ConnectionError("down"))
    import pytest
    with pytest.raises(ConnectionError):
        llm.generate("p")


def test_fake_llm_tokens_used_is_configurable():
    llm = FakeLLM(tokens_used=7)
    assert llm.generate("p").tokens_used == 7
    chunks = list(llm.generate_stream("p"))
    assert all(c.tokens_used == 7 for c in chunks)


def test_fake_llm_stream_yields_chunks():
    llm = FakeLLM(stream_chunks=["foo", " bar"])
    chunks = list(llm.generate_stream("p"))
    assert [c.text for c in chunks] == ["foo", " bar"]
    assert all(isinstance(c, LLMResponse) for c in chunks)


def test_fake_vector_store_roundtrip_and_delete():
    store = FakeVectorStore()
    rec = VectorRecord(id="notes/a.md", chunk_id=0, vector=[1.0], text="t")
    store.upsert_chunks("notes/a.md", [rec])
    assert store.get_chunks_by_file_id("notes/a.md") == [rec]
    assert store.search([1.0]) == [rec]
    store.delete_note("notes/a.md")
    assert store.get_chunks_by_file_id("notes/a.md") == []
    assert "notes/a.md" in store.deleted
    store.close()
    assert store.closed is True


def test_fake_repository_still_importable():
    # 守卫：迁移过程中 FakeRepository 不能丢
    assert FakeRepository().supports_write is True
