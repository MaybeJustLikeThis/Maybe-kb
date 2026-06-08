"""Configuration management."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

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
    max_context_chars: int = 6000
    reranker: str = "score"  # "none" | "score" | "cross-encoder"


@dataclass(frozen=True)
class GeneralConfig:
    notes_dir: str = "notes"
    attachments_dir: str = "attachments"
    index_dir: str = ".kb"


@dataclass(frozen=True)
class ObsidianConfig:
    enabled: bool = False
    vault_name: str = ""
    vault_path: Path | None = None
    open_uri_strategy: str = "file"


@dataclass(frozen=True)
class SourceConfig:
    label: str
    description: str = ""
    icon: str = ""
    default_category: str | None = None
    auto_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8420
    watch_dir: str | None = None
    watch_enabled: bool = True


@dataclass(frozen=True)
class KBConfig:
    vault_path: Path = field(default_factory=lambda: Path("."))
    search: SearchConfig = field(default_factory=SearchConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    sources: dict[str, SourceConfig] = field(default_factory=dict)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    obsidian: ObsidianConfig = field(default_factory=ObsidianConfig)

    @property
    def notes_path(self) -> Path:
        return self.vault_path / self.general.notes_dir

    @property
    def attachments_path(self) -> Path:
        return self.vault_path / self.general.attachments_dir

    @property
    def index_path(self) -> Path:
        return self.vault_path / self.general.index_dir


def _validate_vault_subpath(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty relative vault subpath")

    path = Path(value)
    windows_path = PureWindowsPath(value)
    if path.is_absolute() or windows_path.is_absolute():
        raise ValueError(f"{name} must be a relative vault subpath")
    if ".." in path.parts or ".." in windows_path.parts:
        raise ValueError(f"{name} must not contain '..' path segments")

    return value


def load_config(base_path: Path) -> KBConfig:
    """Load config from config.toml in base_path, with defaults."""
    config_file = base_path / "config.toml"

    if not config_file.exists():
        return KBConfig(vault_path=base_path.resolve())

    with open(config_file, "rb") as f:
        data = tomllib.load(f)

    general = data.get("general", {})
    obsidian_data = data.get("obsidian", {})
    search_data = data.get("search", {})
    embedding_data = data.get("embedding", {})
    llm_data = data.get("llm", {})
    rag_data = data.get("rag", {})
    server_data = data.get("server", {})

    sources: dict[str, SourceConfig] = {}
    for source_name, raw in data.get("sources", {}).items():
        sources[source_name] = SourceConfig(
            label=raw.get("label", source_name),
            description=raw.get("description", ""),
            icon=raw.get("icon", ""),
            default_category=raw.get("default_category"),
            auto_tags=raw.get("auto_tags", []),
        )

    vault_rel = general.get("vault_path", ".")
    vault_path_raw = Path(vault_rel).expanduser()
    vault_path = (
        vault_path_raw.resolve()
        if vault_path_raw.is_absolute()
        else (base_path / vault_path_raw).resolve()
    )

    obsidian_vault_raw = obsidian_data.get("vault_path")
    obsidian_vault_path = None
    if obsidian_vault_raw:
        raw_path = Path(obsidian_vault_raw).expanduser()
        obsidian_vault_path = (
            raw_path.resolve()
            if raw_path.is_absolute()
            else (base_path / raw_path).resolve()
        )

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
            max_context_chars=rag_data.get("max_context_chars", 6000),
            reranker=rag_data.get("reranker", "score"),
        ),
        server=ServerConfig(
            host=server_data.get("host", "127.0.0.1"),
            port=server_data.get("port", 8420),
            watch_dir=server_data.get("watch_dir"),
            watch_enabled=server_data.get("watch_enabled", True),
        ),
        sources=sources,
        general=GeneralConfig(
            notes_dir=_validate_vault_subpath(
                "general.notes_dir", general.get("notes_dir", "notes")
            ),
            attachments_dir=_validate_vault_subpath(
                "general.attachments_dir",
                general.get("attachments_dir", "attachments"),
            ),
            index_dir=_validate_vault_subpath(
                "general.index_dir", general.get("index_dir", ".kb")
            ),
        ),
        obsidian=ObsidianConfig(
            enabled=obsidian_data.get("enabled", False),
            vault_name=obsidian_data.get("vault_name", ""),
            vault_path=obsidian_vault_path,
            open_uri_strategy=obsidian_data.get("open_uri_strategy", "file"),
        ),
    )
