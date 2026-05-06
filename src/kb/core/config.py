"""Configuration management."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomllib


@dataclass(frozen=True)
class SearchConfig:
    max_results: int = 20


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = "local"
    model: str = "BAAI/bge-small-zh-v1.5"
    api_key_env: str | None = None


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    api_key_env: str | None = None


@dataclass(frozen=True)
class RAGConfig:
    top_k: int = 5
    truncate_chars: int = 800


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8420


@dataclass(frozen=True)
class KBConfig:
    vault_path: Path = field(default_factory=lambda: Path("."))
    search: SearchConfig = field(default_factory=SearchConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def load_config(base_path: Path) -> KBConfig:
    """Load config from config.toml in base_path, with defaults."""
    config_file = base_path / "config.toml"

    if not config_file.exists():
        return KBConfig(vault_path=base_path.resolve())

    with open(config_file, "rb") as f:
        data = tomllib.load(f)

    general = data.get("general", {})
    search_data = data.get("search", {})
    embedding_data = data.get("embedding", {})
    llm_data = data.get("llm", {})
    rag_data = data.get("rag", {})
    server_data = data.get("server", {})

    vault_rel = general.get("vault_path", ".")
    vault_path = (base_path / vault_rel).resolve()

    return KBConfig(
        vault_path=vault_path,
        search=SearchConfig(max_results=search_data.get("max_results", 20)),
        embedding=EmbeddingConfig(
            provider=embedding_data.get("provider", "local"),
            model=embedding_data.get("model", "BAAI/bge-small-zh-v1.5"),
            api_key_env=embedding_data.get("api_key_env"),
        ),
        llm=LLMConfig(
            provider=llm_data.get("provider", "ollama"),
            model=llm_data.get("model", "qwen2.5:7b"),
            api_key_env=llm_data.get("api_key_env"),
        ),
        rag=RAGConfig(
            top_k=rag_data.get("top_k", 5),
        ),
        server=ServerConfig(
            host=server_data.get("host", "127.0.0.1"),
            port=server_data.get("port", 8420),
        ),
    )
