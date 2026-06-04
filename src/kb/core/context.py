"""Application context — unified resource container with guaranteed cleanup."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kb.core.config import KBConfig
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider, create_embedding_provider
from kb.data.llm import LLMProvider, create_llm_provider
from kb.data.vector import VectorStore


@dataclass
class AppContext:
    """Holds all initialized service resources.

    Always use from_config() to create, then call close() when done.
    Supports context manager protocol.
    """

    vault: Path
    db: Database
    config: KBConfig | None = None
    embedding: EmbeddingProvider | None = None
    llm: LLMProvider | None = None
    vector_store: VectorStore | None = None
    suggestion_engine: object | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)

    @classmethod
    def from_config(
        cls,
        config: KBConfig,
        *,
        vault: Path | None = None,
        with_embedding: bool = True,
        with_llm: bool = True,
    ) -> AppContext:
        """Initialize resources from KBConfig.

        Args:
            config: Loaded KBConfig.
            vault: Override vault path (defaults to config.vault_path).
            with_embedding: If False, skip embedding provider init.
            with_llm: If False, skip LLM provider init.
        """
        if vault is None:
            vault = config.vault_path
            index_path = config.index_path
        else:
            index_path = vault / config.general.index_dir
        index_path.mkdir(parents=True, exist_ok=True)

        db_path = index_path / "kb.db"
        db = Database(db_path)
        db.initialize()

        embedding = None
        if with_embedding and config.embedding:
            embedding = create_embedding_provider(config.embedding)

        llm = None
        if with_llm and config.llm:
            llm = create_llm_provider(config.llm)

        vector_store = VectorStore(index_path / "vectors.lance")

        return cls(
            vault=vault,
            db=db,
            config=config,
            embedding=embedding,
            llm=llm,
            vector_store=vector_store,
        )

    def ensure_embedding(self) -> EmbeddingProvider | None:
        """Initialize embedding provider on demand."""
        if self.embedding is not None:
            return self.embedding
        if self.config is None or self.config.embedding is None:
            return None
        self.embedding = create_embedding_provider(self.config.embedding)
        return self.embedding

    def ensure_llm(self) -> LLMProvider | None:
        """Initialize LLM provider on demand."""
        if self.llm is not None:
            return self.llm
        if self.config is None or self.config.llm is None:
            return None
        self.llm = create_llm_provider(self.config.llm)
        return self.llm

    def close(self) -> None:
        """Release all resources. Idempotent — safe to call multiple times."""
        if self._closed:
            return
        if self.vector_store is not None:
            self.vector_store.close()
        if self.db is not None:
            self.db.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
