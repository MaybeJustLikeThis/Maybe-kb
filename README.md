# kb — Local Knowledge Base

本地优先的知识库系统，支持全文搜索、语义搜索、MCP 协议接入 AI Agent。

## 项目状态

**Phase 1-4 全部完成。**

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | CLI 核心（CRUD / FTS5 全文搜索 / 增量索引） | ✓ 完成 |
| Phase 2 | Web UI（FastAPI + Vue 3 + Markdown 编辑器） | ✓ 完成 |
| Phase 3 | 语义搜索 + MCP Server（LanceDB + BGE + 混合搜索 RRF） | ✓ 完成 |
| Phase 4 | RAG 对话（LLM Provider + 对话历史 + CLI/API/Web/MCP） | ✓ 完成 |

## 已实现功能

- **笔记 CRUD**：Markdown 文件 + YAML frontmatter，兼容 Hexo 格式
- **全文搜索**：SQLite FTS5 + jieba 中文分词
- **语义搜索**：BGE-small-zh embedding + LanceDB 向量存储
- **混合搜索**：RRF（Reciprocal Rank Fusion）融合全文与语义结果
- **增量索引**：SHA256 文件哈希检测变更，仅索引变化文件
- **Web UI**：Vue 3 + Tailwind CSS，笔记浏览 / Markdown 编辑 / 搜索 / 附件上传
- **MCP Server**：7 个工具（kb_search / kb_semantic_search / kb_hybrid_search / kb_read / kb_list / kb_add / kb_rag_query）
- **RAG 对话**：多 LLM 提供商（Ollama / OpenAI / Anthropic），一键配置切换
- **CLI 问答**：`kb ask "问题"` 命令行 RAG 查询，支持流式输出
- **Web Chat**：ChatPage 聊天面板，多轮对话界面
- **对话历史**：SQLite 持久化聊天会话和消息
- **路径安全**：所有文件操作统一防穿越
- **多设备同步**：Markdown 文件通过 Git 同步，索引每台设备独立生成
- **Embedding Provider**：支持 local（BGE-small-zh）和 OpenAI，通过工厂模式切换

## 目录结构

```
kb/
├── pyproject.toml              # Python 项目配置
├── config.toml                 # 知识库配置（提交到 Git）
├── README.md
├── .gitignore
│
├── notes/                      # 知识内容（Markdown，Git 管理）
│   ├── tech/
│   ├── projects/
│   ├── daily/
│   └── snippets/
│
├── attachments/                # 附件（PDF/图片，Git LFS）
│
├── .kb/                        # 生成数据（.gitignore 忽略）
│   ├── kb.db                   # SQLite 数据库（FTS5 + 元数据）
│   └── vectors.lance/          # LanceDB 向量索引
│
├── src/kb/                     # Python 源码
│   ├── cli.py                  # CLI 入口（typer）
│   ├── routes.py               # API routes（FastAPI APIRouter 工厂）
│   ├── server.py               # FastAPI app + 静态文件服务
│   ├── mcp_server.py           # MCP Server（FastMCP）
│   │
│   ├── core/                   # 领域逻辑层
│   │   ├── models.py           # Note 数据模型（dataclass）
│   │   ├── config.py           # KBConfig 配置管理（frozen dataclass）
│   │   ├── services.py         # 共享 CRUD 服务编排
│   │   ├── search.py           # 混合搜索 RRF 融合
│   │   └── rag.py              # RAG 编排（搜索→组装→生成）
│   │
│   └── data/                   # 数据持久化层
│       ├── storage.py          # Markdown 文件读写 + chunk + 路径安全
│       ├── database.py         # SQLite + FTS5 索引
│       ├── vector.py           # LanceDB 向量存储
│       ├── embedding.py        # Embedding Provider 抽象（local + openai）
│       ├── llm.py              # LLM Provider 抽象（ollama / openai / anthropic）
│       ├── chat_history.py     # 对话历史 SQLite 存储
│       └── attachments.py      # 附件存储（内容哈希去重）
│
├── web/                        # 前端（Vue 3 + Vite + Tailwind CSS）
│   └── src/
│       ├── App.vue
│       ├── pages/
│       │   ├── NoteList.vue
│       │   ├── NoteDetail.vue
│       │   ├── SearchPage.vue
│       │   └── ChatPage.vue
│       └── components/
│           └── MarkdownEditor.vue
│
└── tests/                      # 测试
    ├── test_cli.py
    ├── test_server.py
    ├── test_integration.py
    ├── test_storage.py
    ├── test_services.py
    ├── test_embedding.py
    ├── test_vector.py
    ├── test_search.py
    ├── test_rag.py
    ├── test_llm.py
    ├── test_chat_history.py
    └── test_mcp.py
```

## 技术栈

| 层 | 技术 | 用途 |
|---|------|------|
| 内容 | Markdown + YAML frontmatter | 知识本体 |
| 全文搜索 | SQLite FTS5 + jieba 分词 | 中文全文检索 |
| 语义向量 | LanceDB + BGE-small-zh | 向量索引与语义搜索 |
| CLI | Python 3.11+ + Typer + Rich | 命令行 |
| API | FastAPI + Uvicorn | REST API |
| 前端 | Vue 3 + Vite + Tailwind CSS | Web UI |
| LLM | httpx + Ollama / OpenAI / Anthropic API | RAG 生成 |
| RAG | 混合搜索 + LLM 编排 | 知识库问答 |
| MCP | mcp Python SDK (FastMCP) | AI Agent 接入 |
| 附件 | Git LFS | 二进制文件管理 |

## 快速开始

```bash
# 安装
pip install -e .

# 初始化知识库
kb init

# 创建笔记
kb add "我的第一篇笔记" -t "python, 学习"

# 搜索
kb search "python 异步"

# RAG 问答
kb ask "Python 异步编程的关键概念是什么？"
kb ask "解释一下知识库中的设计模式" --stream

# 启动 Web UI
kb serve

# MCP 模式（给 Claude Code 用）
kb mcp
```

## 配置

编辑 `config.toml`：

```toml
[general]
vault_path = "."

[search]
max_results = 20

[embedding]
provider = "local"              # local / openai
model = "BAAI/bge-small-zh-v1.5"

[llm]
provider = "ollama"             # ollama / openai / anthropic
model = "qwen2.5:7b"

[rag]
top_k = 5

[server]
host = "127.0.0.1"
port = 8420
```
