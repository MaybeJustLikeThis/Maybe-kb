"""Embedding provider abstraction with local and OpenAI backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from kb.core.config import EmbeddingConfig


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    dimension: int
    tokens_used: int


class EmbeddingProvider(ABC):
    """Abstract interface for text-to-vector embedding."""

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """BGE-small-zh via sentence-transformers, outputs 512-dim vectors."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> EmbeddingResult:
        vector = self._model.encode(text, normalize_embeddings=True)
        return EmbeddingResult(
            vector=vector.tolist(),
            dimension=len(vector),
            tokens_used=len(text),
        )

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        dim = vectors.shape[1]
        return [
            EmbeddingResult(
                vector=v.tolist(),
                dimension=dim,
                tokens_used=len(t),
            )
            for v, t in zip(vectors, texts)
        ]

    @property
    def dimension(self) -> int:
        return self._model.get_embedding_dimension()


def create_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    """Factory: build provider from config."""
    if config.provider == "local":
        return LocalEmbeddingProvider(model_name=config.model or "BAAI/bge-small-zh-v1.5")
    if config.provider == "openai":
        import os as _os
        key = _os.environ.get(config.api_key_env or "OPENAI_API_KEY", "")
        if not key:
            raise ValueError(
                f"OpenAI API key not found in env var {config.api_key_env or 'OPENAI_API_KEY'}"
            )
        return OpenAIEmbeddingProvider(api_key=key, model=config.model)
    raise ValueError(f"Unknown embedding provider: {config.provider}")


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding API backend."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = 1536 if "3-small" in model else 3072

    def embed(self, text: str) -> EmbeddingResult:
        results = self.embed_batch([text])
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        import json
        import urllib.request
        import urllib.error

        body = json.dumps({
            "model": self._model,
            "input": texts,
            "encoding_format": "float",
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenAI embeddings API returned {e.code}: {body_text}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Failed to reach OpenAI embeddings API: {e.reason}"
            ) from e
        except (TimeoutError, OSError) as e:
            raise RuntimeError(
                f"OpenAI embeddings request failed: {e}"
            ) from e

        return [
            EmbeddingResult(
                vector=item["embedding"],
                dimension=len(item["embedding"]),
                tokens_used=item.get("tokens", 0),
            )
            for item in data["data"]
        ]

    @property
    def dimension(self) -> int:
        return self._dimension
