"""Tests for embedding provider abstraction."""
import pytest
from kb.data.embedding import (
    EmbeddingResult,
    EmbeddingProvider,
    LocalEmbeddingProvider,
    create_embedding_provider,
)
from kb.core.config import EmbeddingConfig


def test_embed_result_fields():
    """EmbeddingResult stores vector, dimension, and token count."""
    r = EmbeddingResult(vector=[0.1, 0.2], dimension=2, tokens_used=5)
    assert r.vector == [0.1, 0.2]
    assert r.dimension == 2
    assert r.tokens_used == 5


def test_local_provider_dimension():
    """Local provider returns 512-dim vectors (BGE-small-zh-v1.5)."""
    provider = LocalEmbeddingProvider("BAAI/bge-small-zh-v1.5")
    result = provider.embed("测试文本")
    assert result.dimension == 512
    assert len(result.vector) == 512
    assert result.tokens_used > 0


def test_local_provider_batch():
    """Batch produces same vectors as individual calls."""
    provider = LocalEmbeddingProvider("BAAI/bge-small-zh-v1.5")
    texts = ["文本一", "文本二"]
    results = provider.embed_batch(texts)
    assert len(results) == 2
    individual = [provider.embed(t) for t in texts]
    for a, b in zip(results, individual):
        assert a.vector == pytest.approx(b.vector, abs=1e-6)


def test_create_provider_local_default():
    """Factory returns local provider when config says 'local'."""
    config = EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5")
    provider = create_embedding_provider(config)
    assert isinstance(provider, LocalEmbeddingProvider)
    assert provider.dimension == 512


def test_openai_provider_http_error(monkeypatch: pytest.MonkeyPatch):
    """OpenAI provider wraps HTTP errors as RuntimeError."""
    from kb.data.embedding import OpenAIEmbeddingProvider
    import urllib.error
    import io

    provider = OpenAIEmbeddingProvider(api_key="sk-test", model="text-embedding-3-small")

    def mock_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            "https://api.openai.com/v1/embeddings", 401, "Unauthorized",
            {}, io.BytesIO(b'{"error": "invalid api key"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    with pytest.raises(RuntimeError, match="OpenAI embeddings API"):
        provider.embed("test")


def test_openai_provider_connection_error(monkeypatch: pytest.MonkeyPatch):
    """OpenAI provider wraps URL errors as RuntimeError."""
    from kb.data.embedding import OpenAIEmbeddingProvider
    import urllib.error

    provider = OpenAIEmbeddingProvider(api_key="sk-test", model="text-embedding-3-small")

    def mock_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    with pytest.raises(RuntimeError, match="Failed to reach OpenAI"):
        provider.embed("test")


def test_create_provider_unknown_raises():
    """Factory raises ValueError for unknown provider."""
    config = EmbeddingConfig(provider="unknown", model="some-model")
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_embedding_provider(config)
