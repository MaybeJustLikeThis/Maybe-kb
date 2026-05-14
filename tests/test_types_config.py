"""Tests for knowledge type configuration."""
import pytest
from pathlib import Path
from kb.core.config import load_config, KBTypeConfig, KBConfig


def test_kb_type_config_defaults():
    """KBTypeConfig has expected defaults."""
    kt = KBTypeConfig(label="测试", description="描述")
    assert kt.label == "测试"
    assert kt.description == "描述"
    assert kt.default_tags == []
    assert kt.parser == "markdown"


def test_load_config_with_kb_types(tmp_path: Path):
    """config.toml [kb_types.*] sections are loaded."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""\
[general]
vault_path = "."

[kb_types.tech-article]
label = "技术文章"
description = "技术分析、教程、原理解析"
default_tags = []
parser = "markdown"

[kb_types.troubleshooting]
label = "踩坑记录"
description = "问题现象、根因、解决方案"
default_tags = ["troubleshooting"]
parser = "markdown"
""", encoding="utf-8")
    config = load_config(tmp_path)
    assert "tech-article" in config.kb_types
    assert config.kb_types["tech-article"].label == "技术文章"
    assert config.kb_types["tech-article"].parser == "markdown"
    assert config.kb_types["troubleshooting"].default_tags == ["troubleshooting"]


def test_load_config_no_kb_types_defaults(tmp_path: Path):
    """When no [kb_types] defined, returns empty dict."""
    config = load_config(tmp_path)
    assert config.kb_types == {}


def test_kb_config_empty_types_not_frozen():
    """KBConfig.kb_types is a plain dict, not frozen."""
    config = KBConfig()
    assert isinstance(config.kb_types, dict)
    assert config.kb_types == {}
