"""Tests for config module."""
import pytest
from pathlib import Path
from kb.core.config import (
    EmbeddingConfig,
    KBConfig,
    LLMConfig,
    RAGConfig,
    SearchConfig,
    ServerConfig,
    SourceConfig,
    load_config,
)


def test_load_config_defaults(tmp_path: Path):
    """Config with no file returns defaults."""
    config = load_config(tmp_path)
    assert config.vault_path == tmp_path
    assert config.search.max_results == 20


def test_load_config_from_toml(tmp_path: Path):
    """Config loads values from config.toml."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[general]\nvault_path = "."\n\n[search]\nmax_results = 50\n'
    )
    config = load_config(tmp_path)
    assert config.search.max_results == 50


def test_config_vault_path_resolved(tmp_path: Path):
    """vault_path is resolved to absolute path."""
    config = load_config(tmp_path)
    assert config.vault_path.is_absolute()


def test_load_config_supports_obsidian_vault_paths(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[general]
vault_path = "D:/ObsidianVault"
notes_dir = "knowledge"
attachments_dir = "assets"
index_dir = ".kb-data"

[obsidian]
enabled = true
vault_name = "ObsidianVault"
vault_path = "D:/ObsidianVault"
open_uri_strategy = "path"

[server]
watch_enabled = true
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.vault_path == Path("D:/ObsidianVault").resolve()
    assert config.general.notes_dir == "knowledge"
    assert config.general.attachments_dir == "assets"
    assert config.general.index_dir == ".kb-data"
    assert config.notes_path == Path("D:/ObsidianVault").resolve() / "knowledge"
    assert config.attachments_path == Path("D:/ObsidianVault").resolve() / "assets"
    assert config.index_path == Path("D:/ObsidianVault").resolve() / ".kb-data"
    assert config.obsidian.enabled is True
    assert config.obsidian.vault_name == "ObsidianVault"
    assert config.obsidian.vault_path == Path("D:/ObsidianVault").resolve()
    assert config.obsidian.open_uri_strategy == "path"
    assert config.server.watch_enabled is True


def test_load_config_keeps_legacy_defaults(tmp_path: Path):
    (tmp_path / "config.toml").write_text(
        """
[general]
vault_path = "."
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.vault_path == tmp_path.resolve()
    assert config.general.notes_dir == "notes"
    assert config.general.attachments_dir == "attachments"
    assert config.general.index_dir == ".kb"
    assert config.obsidian.enabled is False
    assert config.server.watch_enabled is True


def test_load_config_supports_disabling_server_watch(tmp_path: Path):
    (tmp_path / "config.toml").write_text(
        """
[general]
vault_path = "."

[server]
watch_enabled = false
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.server.watch_enabled is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("notes_dir", ""),
        ("notes_dir", "../notes"),
        ("attachments_dir", "D:/attachments"),
        ("index_dir", "folder/../.kb"),
    ],
)
def test_load_config_rejects_invalid_vault_subpaths(
    tmp_path: Path, field: str, value: str
):
    (tmp_path / "config.toml").write_text(
        f"""
[general]
vault_path = "."
{field} = {value!r}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_config(tmp_path)


def test_kbconfig_preserves_legacy_positional_constructor_order():
    vault_path = Path("vault")
    search = SearchConfig(max_results=7)
    embedding = EmbeddingConfig(provider="test-embedding")
    llm = LLMConfig(provider="test-llm")
    rag = RAGConfig(top_k=3)
    server = ServerConfig(host="0.0.0.0")
    sources = {"docs": SourceConfig(label="Docs")}

    config = KBConfig(vault_path, search, embedding, llm, rag, server, sources)

    assert config.vault_path == vault_path
    assert config.search is search
    assert config.embedding is embedding
    assert config.llm is llm
    assert config.rag is rag
    assert config.server is server
    assert config.sources is sources
