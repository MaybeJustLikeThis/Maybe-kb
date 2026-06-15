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
    """BGE-small-zh via transformers (bypasses sentence-transformers import).

    Uses AutoTokenizer + AutoModel directly, with manual mean pooling.
    This avoids the sentence_transformers package __init__ which hangs
    inside the MCP server's thread-pool executor (import deadlock in
    sentence_transformers 5.x sub-module chain).
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5") -> None:
        import logging
        import torch
        from transformers import AutoModel, AutoTokenizer

        _log = logging.getLogger(__name__)

        # Cache-first: skip HuggingFace network check when model is already
        # cached locally.
        _log.info("Loading embedding model %s (local_files_only=True)...", model_name)
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name, local_files_only=True
            )
            self._model = AutoModel.from_pretrained(
                model_name, local_files_only=True
            )
            _log.info("Model loaded from cache successfully")
        except Exception as e:
            _log.warning("local_files_only failed (%s: %s), downloading...", type(e).__name__, e)
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModel.from_pretrained(model_name)

        self._model.eval()
        self._device = torch.device("cpu")
        self._dimension = self._model.config.hidden_size

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling – take attention mask into account for correct averaging."""
        import torch
        token_embeddings = model_output[0]  # last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
            input_mask_expanded.sum(1), min=1e-9
        )

    def embed(self, text: str) -> EmbeddingResult:
        import torch
        with torch.no_grad():
            encoded = self._tokenizer(
                text, padding=True, truncation=True, max_length=512, return_tensors="pt"
            )
            outputs = self._model(**encoded)
            pooled = self._mean_pooling(outputs, encoded["attention_mask"])
            # Normalize
            vector = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vec = vector[0].tolist()
        return EmbeddingResult(vector=vec, dimension=len(vec), tokens_used=len(text))

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        import torch
        with torch.no_grad():
            encoded = self._tokenizer(
                texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
            )
            outputs = self._model(**encoded)
            pooled = self._mean_pooling(outputs, encoded["attention_mask"])
            vectors = torch.nn.functional.normalize(pooled, p=2, dim=1)
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
        return self._dimension


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
