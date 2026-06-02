# Claude Code Plugin

This repository can be used as a Claude Code plugin for the Maybe-kb local knowledge base.

## What It Provides

- A `.claude-plugin/plugin.json` manifest so Claude Code can identify the plugin.
- A root `.mcp.json` that starts the existing `kb mcp --path .` server.
- A `use-kb` skill that teaches Claude Code when to search, read, answer with RAG, or save notes.

## Prerequisites

Install the Python package in the environment where Claude Code will launch MCP servers:

```bash
pip install -e .
```

Initialize a vault if the target project is not already a Maybe-kb vault:

```bash
kb init
```

## Local Plugin Development

From Claude Code, add this repository as a local marketplace, then install the `maybe-kb` plugin:

```bash
claude plugin marketplace add ./
claude plugin install maybe-kb@maybe-kb --scope project
```

For a one-off session without installing the plugin:

```bash
claude --plugin-dir .
```

The MCP configuration included in this repository starts:

```bash
kb mcp --path .
```

That means the active Claude Code workspace is treated as the knowledge-base vault. Edit `.mcp.json` if you want the plugin to always point at a dedicated vault path instead.

## MCP Tools

The server exposes:

- `kb_search`
- `kb_semantic_search`
- `kb_hybrid_search`
- `kb_read`
- `kb_list`
- `kb_add`
- `kb_save`
- `kb_rag_query`

## Distribution Notes

The repository root is the plugin root. Keep `.claude-plugin/plugin.json`, `.mcp.json`, and `skills/` at the repository root so Claude Code can discover them when installed from a marketplace or local plugin source.
