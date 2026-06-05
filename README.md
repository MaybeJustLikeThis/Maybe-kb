# kb - 本地优先知识库

`kb` 是一个本地优先的个人知识库系统。它以 Markdown 作为知识源，提供全文搜索、语义搜索、RAG 问答、Web 管理界面和 MCP Agent 接入。

## 快速开始

```bash
pip install -e .
kb init
kb index --full
kb serve
```

打开 `http://127.0.0.1:8420` 后，先查看 Overview 里的 `System Health`。系统健康会提示 vault、notes、attachments、索引、Obsidian、embedding、LLM 和向量覆盖率是否已经就绪。

## 核心能力

- Markdown + YAML frontmatter 笔记管理
- SQLite FTS5 + jieba 中文全文搜索
- LanceDB + embedding 语义搜索
- Hybrid Search 与 RAG Chat
- Obsidian 打开目标集成
- MCP 工具接入 Claude Code / Codex 等 Agent
- 本地索引可重建，知识源保持为普通文件

## 常用命令

```bash
kb add "标题"
kb search "关键词"
kb ask "根据我的知识库回答一个问题"
kb index --full
kb serve --skip-watch
```

## 默认来源

- 博客：Hexo 博客文章
- Agent 沉淀：Agent 自动沉淀的知识
- 手动录入：手动创建的知识笔记
- 未分类：缺少分类时的默认分类

## 配置

编辑 `config.toml` 设置 vault、embedding、LLM、Obsidian 和来源。API key 建议放在环境变量中，不要写入仓库。
