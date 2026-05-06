"""Tests for config module."""
import pytest
from pathlib import Path
from kb.core.config import load_config, KBConfig


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
