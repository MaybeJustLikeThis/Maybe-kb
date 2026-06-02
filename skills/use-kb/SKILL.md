---
name: use-kb
description: Use when Claude Code should search, read, save, or answer questions from a Maybe-kb knowledge base through the kb MCP server.
---

# Use Maybe-kb

Maybe-kb exposes a local Markdown knowledge base through the `kb` MCP server.

## Before Using Tools

Confirm the `kb` MCP server is available. If it is missing, ask the user to install the Python package and add this repository's `.mcp.json` configuration to Claude Code.

## Search

Use `kb_search` for exact or keyword-oriented lookups. Good first move for titles, tags, function names, error messages, and Chinese text.

Use `kb_semantic_search` for fuzzy concept searches when the user remembers the idea but not the wording.

Use `kb_hybrid_search` when recall matters most. It combines full-text and semantic search.

## Read

After search returns a promising `file_id`, call `kb_read` to inspect the full Markdown note before answering or editing.

## Answer

Use `kb_rag_query` when the user asks a question that should be answered from the vault. Prefer reading the cited notes when the answer will guide implementation or decisions.

## Save

Use `kb_save` when the user asks to remember durable knowledge, record a decision, preserve a troubleshooting result, or capture reusable context.

Write notes as clear Markdown:

- Put the core idea in the first paragraph.
- Include why it matters and where it applies.
- Add practical takeaways or open questions.
- Use `source_project` to identify where the note came from, such as `blog`, `agent`, or `manual`.
- Add tags such as `Type-Troubleshooting`, `Type-DesignDecision`, `Type-CodeSnippet`, `Type-TechArticle`, or `Type-Document`.

## Local CLI Fallback

If MCP is unavailable but the `kb` command is installed, use local commands from the knowledge-base root:

```bash
kb search "query"
kb ask "question"
kb add "title" --source-project agent
kb mcp --path .
```
