"""Tests for Claude Code plugin packaging."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_claude_plugin_manifest_declares_kb_plugin() -> None:
    manifest_path = ROOT / ".claude-plugin" / "plugin.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "maybe-kb"
    assert manifest["version"] == "0.1.0"
    assert "MCP" in manifest["description"]
    assert manifest["repository"].endswith("MaybeJustLikeThis/Maybe-kb")


def test_claude_plugin_marketplace_exposes_local_plugin() -> None:
    marketplace_path = ROOT / ".claude-plugin" / "marketplace.json"

    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

    assert marketplace["name"] == "maybe-kb"
    assert "Claude Code" in marketplace["description"]
    assert marketplace["owner"]["name"] == "MaybeJustLikeThis"
    plugin = marketplace["plugins"][0]
    assert plugin["name"] == "maybe-kb"
    assert plugin["source"] == "./"


def test_claude_plugin_mcp_config_starts_kb_mcp() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))

    kb_server = config["mcpServers"]["kb"]

    assert kb_server["command"] == "kb"
    assert kb_server["args"] == ["mcp", "--path", "."]


def test_claude_plugin_includes_usage_skills() -> None:
    skill_root = ROOT / "skills" / "use-kb"
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")

    assert "kb_search" in skill_text
    assert "kb_save" in skill_text
    assert "kb_rag_query" in skill_text
