"""Tests for focused TOML section updates."""
from __future__ import annotations

import tomllib
from pathlib import Path

from kb.core.config_writer import update_toml_sections


def test_update_toml_sections_preserves_unrelated_content(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "# project comment\n"
        "[general]\n"
        'vault_path = "." # old vault\n'
        'custom_key = "keep-me"\n'
        "\n"
        "[search]\n"
        "# search comment\n"
        "max_results = 42\n"
        "\n"
        "[obsidian]\n"
        'custom_obsidian = "keep-too"\n',
        encoding="utf-8",
    )

    update_toml_sections(
        config_path,
        {
            "general": {
                "vault_path": "D:/Knowledge Vault",
                "notes_dir": "notes",
                "attachments_dir": "attachments",
                "index_dir": ".kb",
            },
            "obsidian": {
                "enabled": True,
                "vault_name": "Knowledge Vault",
                "vault_path": "D:/Knowledge Vault",
                "open_uri_strategy": "file",
            },
        },
    )

    text = config_path.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert "# project comment" in text
    assert "# search comment" in text
    assert 'custom_key = "keep-me"' in text
    assert 'custom_obsidian = "keep-too"' in text
    assert parsed["search"]["max_results"] == 42
    assert parsed["general"]["vault_path"] == "D:/Knowledge Vault"
    assert parsed["general"]["notes_dir"] == "notes"
    assert parsed["obsidian"]["enabled"] is True
    assert parsed["obsidian"]["open_uri_strategy"] == "file"


def test_update_toml_sections_adds_missing_sections_and_escapes_strings(
    tmp_path: Path,
):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[search]\nmax_results = 20\n", encoding="utf-8")

    update_toml_sections(
        config_path,
        {
            "general": {"vault_path": 'C:/A "quoted" Vault'},
            "obsidian": {"enabled": False},
        },
    )

    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert parsed["general"]["vault_path"] == 'C:/A "quoted" Vault'
    assert parsed["obsidian"]["enabled"] is False


def test_update_toml_sections_handles_dotted_and_quoted_keys(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "# dotted general key\n"
        'general.custom = "keep"\n'
        'general.extra.nested = "keep-nested"\n'
        '"general"."vault_path" = "." # quoted dotted key\n'
        "\n"
        "[obsidian]\n"
        '"vault_path" = "." # quoted key\n',
        encoding="utf-8",
    )

    update_toml_sections(
        config_path,
        {
            "general": {
                "vault_path": "D:/ObsidianVault",
                "notes_dir": "notes",
            },
            "obsidian": {
                "vault_path": "D:/ObsidianVault",
                "enabled": True,
            },
        },
    )

    text = config_path.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert "# dotted general key" in text
    assert parsed["general"]["vault_path"] == "D:/ObsidianVault"
    assert parsed["general"]["notes_dir"] == "notes"
    assert parsed["general"]["custom"] == "keep"
    assert parsed["general"]["extra"]["nested"] == "keep-nested"
    assert parsed["obsidian"]["vault_path"] == "D:/ObsidianVault"
    assert parsed["obsidian"]["enabled"] is True


def test_update_toml_sections_treats_array_tables_as_section_boundaries(
    tmp_path: Path,
):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[general]\n"
        'vault_path = "."\n'
        "\n"
        "[[plugins]]\n"
        'name = "keep"\n',
        encoding="utf-8",
    )

    update_toml_sections(
        config_path,
        {
            "general": {
                "vault_path": "D:/ObsidianVault",
                "notes_dir": "notes",
            },
        },
    )

    parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert parsed["general"]["vault_path"] == "D:/ObsidianVault"
    assert parsed["general"]["notes_dir"] == "notes"
    assert parsed["plugins"] == [{"name": "keep"}]
