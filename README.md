# kb — 本地优先的个人知识库

> Markdown 是知识源，索引和向量可以随时重建。不依赖任何云服务。

`kb` 是一个本地优先的个人知识库系统。以 Markdown 文件作为唯一数据源，提供全文搜索（FTS5 + jieba）、语义搜索（BGE-small-zh + LanceDB）、RAG 问答、Web 管理界面以及 MCP 工具接入，可被 Claude Code / Codex 等 Agent 直接调用。

> **当前版本：v0.2.0** · [更新日志](CHANGELOG.md)

## 功能

| 能力 | 说明 |
|------|------|
| **笔记管理** | Markdown + YAML frontmatter，支持 `blog` / `agent` / `manual` 多来源分类 |
| **全文搜索** | SQLite FTS5 + jieba 中文分词 |
| **语义搜索** | `BAAI/bge-small-zh-v1.5` 本地 embedding + LanceDB 余弦相似度 |
| **混合搜索 + RAG** | FTS5 与语义搜索 RRF 融合，接入本地 LLM（默认 Ollama qwen2.5:7b）生成回答 |
| **Web UI** | Vite + Tailwind 构建的管理界面，含搜索、编辑、Dashboard、系统健康检查 |
| **MCP Server** | 内置 MCP Server，提供 `kb_search` / `kb_add` / `kb_save` / `kb_rag_query` 等工具 |
| **文件导入** | `kb import` 支持通过 markitdown 将 PDF、DOCX、图片等转为 Markdown 导入 |
| **目录监听** | `kb serve` 启动后可监听指定目录，新增/修改的 Markdown 自动入库 |
| **本地可重建** | 所有索引和向量数据从 Markdown 源文件重建，换设备只需同步源文件 + `kb index --full` |

## 快速开始

```bash
# 安装
pip install -e .

# 初始化项目结构
kb init

# 全量建索引
kb index --full

# 启动 Web 服务
kb serve
```

打开 `http://127.0.0.1:8420`，在 Overview 的 **System Health** 查看 vault、索引、embedding、LLM 等组件是否就绪。

### 导入已有文件

```bash
kb import /path/to/document.pdf
kb import /path/to/notes.docx
```

### 安装可选依赖

```bash
pip install -e ".[markitdown]"   # 启用 markitdown 文件转换
pip install -e ".[dev]"          # 开发依赖（pytest、pytest-cov）
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `kb init` | 初始化 vault 目录和配置文件 |
| `kb add "标题"` | 创建新笔记 |
| `kb import <file>` | 导入文件（PDF / DOCX / 图片等） |
| `kb list` | 列出笔记 |
| `kb search "关键词"` | 全文搜索 |
| `kb ask "问题"` | RAG 问答 |
| `kb edit <file_id>` | 编辑笔记 |
| `kb delete <file_id>` | 删除笔记 |
| `kb tag <file_id> <tags>` | 管理标签 |
| `kb index [--full]` | 建立/重建索引 |
| `kb serve [--skip-watch]` | 启动 Web 服务 |
| `kb migrate` | 数据迁移 |
| `kb mcp` | 以 MCP Server 模式运行 |

## MCP 工具

`kb` 内置 MCP Server，可被 Claude Code、Codex 等 Agent 直接调用：

```json
{
  "mcpServers": {
    "kb": {
      "command": "kb",
      "args": ["mcp", "--path", "."]
    }
  }
}
```

| 工具 | 说明 |
|------|------|
| `kb_search` | 全文搜索（FTS5 + jieba） |
| `kb_semantic_search` | 语义搜索（embedding + LanceDB） |
| `kb_hybrid_search` | 混合搜索（FTS5 + 语义 RRF 融合） |
| `kb_read` | 读取笔记完整内容 |
| `kb_list` | 按来源/标签筛选笔记列表 |
| `kb_add` | 创建新笔记 |
| `kb_save` | 保存知识条目到 vault |
| `kb_rag_query` | RAG 问答（检索 + LLM 生成） |

## Web UI

前端使用 Vite + Vue 3 + Tailwind 构建，所有 API 统一在 `/api/v1` 前缀下，返回标准 `{data, meta, error}` 响应格式。

提供：

- **搜索** — 全文搜索与语义搜索
- **笔记管理** — 浏览、创建、编辑、删除笔记
- **Dashboard** — 来源统计、内容类型分布、标签概览
- **RAG Chat** — 基于知识库的问答对话
- **System Health** — 一站式检查 vault、索引、embedding、LLM、向量覆盖率

## 搜索与 RAG

- **全文搜索**：jieba 分词 → SQLite FTS5
- **语义搜索**：BGE-small-zh embedding → LanceDB 余弦相似度
- **混合搜索**：FTS5 + 语义 RRF 融合（k=60）
- **RAG 问答**：检索 → 上下文拼接（6000 字符预算）→ LLM 生成回答
- **评估框架**：内置 `kb eval`，支持 hit rate、MRR、keyword coverage、LLM judge，可做 baseline 对比和回归检测

## 配置

编辑项目根目录下的 `config.toml`：

```toml
[general]
vault_path = "D:/ObsidianVault"
notes_dir = "notes"
attachments_dir = "attachments"
index_dir = ".kb"

[embedding]
provider = "local"
model = "BAAI/bge-small-zh-v1.5"

[llm]
provider = "ollama"
model = "qwen2.5:7b"

[server]
host = "127.0.0.1"
port = 8420

[obsidian]
enabled = true
vault_name = "ObsidianVault"
vault_path = "D:/ObsidianVault"
open_uri_strategy = "file"

[sources.blog]
label = "博客"
description = "Hexo 博客文章"

[sources.agent]
label = "Agent 沉淀"
description = "Agent 自动沉淀的知识"

[sources.manual]
label = "手动录入"
description = "手动创建的知识笔记"
```

API key 建议通过环境变量设置，不要写入仓库。

## 项目结构

```
src/kb/
├── cli.py                 # Typer CLI 入口
├── server.py              # FastAPI 服务
├── mcp_server.py          # MCP Server
├── api/v1.py              # REST API（/api/v1）
├── core/
│   ├── config.py          # 配置加载
│   ├── search.py          # 全文搜索
│   ├── rag.py             # RAG 问答
│   ├── indexer.py         # 索引构建
│   ├── ingest.py          # 数据入库
│   ├── services.py        # 业务逻辑层
│   ├── health.py          # 系统健康检查
│   ├── import_file.py     # 文件导入
│   ├── watcher.py         # 目录监听
│   └── ...
├── data/
│   ├── models.py          # 数据模型（Note、IngestRequest）
│   ├── database.py        # SQLite + FTS5
│   ├── vector.py          # LanceDB 向量存储
│   ├── embedding.py       # Embedding 服务
│   ├── llm.py             # LLM 调用
│   └── storage.py         # 文件存储
└── parsers/
    └── markitdown_converter.py  # markitdown 文件转换

web/                       # Vite + Vue 3 + Tailwind 前端
tests/                     # pytest 测试套件
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 带覆盖率
pytest --cov=kb --cov-report=term-missing

# 构建前端
cd web && npm install && npm run build
```

## 迁移

换设备或重建环境时：

1. 同步 Markdown 源文件、`attachments/` 和 `config.toml`
2. 在新设备 `pip install -e . && kb index --full`
3. 所有索引和向量数据会从源文件重新生成
