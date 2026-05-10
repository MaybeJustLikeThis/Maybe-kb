# kb 使用手册

本地优先的知识库系统，支持全文搜索、语义搜索、RAG 问答、MCP 协议接入 AI Agent。

---

## 1. 安装

```bash
cd kb/
pip install -e .
```

安装后 `kb` 命令全局可用。

验证安装：

```bash
kb --help
```

---

## 2. 初始化知识库

```bash
# 在项目目录下初始化
kb init

# 如果已有 .md 文件，一次性导入并建立索引
kb init --import-existing
```

初始化会创建：

| 路径 | 用途 |
|------|------|
| `notes/` | 笔记目录（Markdown，Git 管理） |
| `attachments/` | 附件目录（PDF/图片，Git LFS） |
| `config.toml` | 配置文件 |
| `.kb/kb.db` | SQLite 数据库（全文索引 + 元数据） |
| `.kb/vectors.lance/` | LanceDB 向量索引 |
| `.gitignore` | 已配置忽略 `.kb/`、`__pycache__/` 等 |

---

## 3. 配置 config.toml

```toml
[general]
vault_path = "."

[search]
max_results = 20

[embedding]
provider = "local"                      # local / openai
model = "BAAI/bge-small-zh-v1.5"        # 首次运行自动下载（~100MB）

[llm]
provider = "ollama"                     # ollama / openai / anthropic
model = "qwen2.5:7b"                    # 需先通过 ollama pull 拉取

[rag]
top_k = 5                               # RAG 返回参考笔记数
truncate_chars = 800                     # 每条参考笔记截断长度

[server]
host = "127.0.0.1"
port = 8420
# 可选：配置 Hexo 博客源目录，kb serve 启动时自动同步
# watch_dir = "C:/Users/cherry/Desktop/项目/blog_new/blog_new/source/_posts"
```

### 3.1 LLM 提供商配置示例

**Ollama（本地免费，推荐）：**

```toml
[llm]
provider = "ollama"
model = "qwen2.5:7b"
```

前置步骤：

```bash
# 安装 Ollama: https://ollama.com
ollama pull qwen2.5:7b
```

**OpenAI：**

```toml
[llm]
provider = "openai"
model = "gpt-4.1-mini"
api_key_env = "OPENAI_API_KEY"
```

**Anthropic：**

```toml
[llm]
provider = "anthropic"
model = "claude-haiku-4-5-20251001"
api_key_env = "ANTHROPIC_API_KEY"
```

### 3.2 Embedding 提供商配置示例

```toml
# 本地（默认，免费，无需 API key）
[embedding]
provider = "local"
model = "BAAI/bge-small-zh-v1.5"

# OpenAI（需要 API key）
[embedding]
provider = "openai"
model = "text-embedding-3-small"
api_key_env = "OPENAI_API_KEY"
```

---

## 4. CLI 命令参考

### 4.1 创建笔记

```bash
kb add "Python 异步编程" -t "python, async" -c "tech" -d "asyncio 入门指南"
```

| 参数 | 说明 |
|------|------|
| `title` | 笔记标题（必填） |
| `-t` | 逗号分隔的标签 |
| `-c` | 分类（如 tech / projects / daily） |
| `-d` | 简短描述 |

### 4.2 列出笔记

```bash
kb list                          # 全部笔记
kb list -c "tech"                # 按分类过滤
kb list -t "python"              # 按标签过滤
kb list -c "tech" -t "python"    # 组合过滤
kb list --limit 50               # 调整返回数量
```

### 4.3 搜索

```bash
kb search "异步 io 模型"
kb search "docker compose" --limit 20
```

使用 SQLite FTS5 + jieba 中文分词，支持中英文混合搜索。

### 4.4 编辑笔记

```bash
kb edit "notes/python-async.md"
```

用系统默认编辑器打开：
- Windows：关联程序
- macOS：`open`
- Linux：`xdg-open`

### 4.5 管理标签

```bash
kb tag "notes/python-async.md" add -t "asyncio, coroutine"
kb tag "notes/python-async.md" remove -t "coroutine"
```

### 4.6 删除笔记

```bash
kb delete "notes/old-note.md"
kb delete "notes/old-note.md" --force    # 跳过确认
```

### 4.7 索引管理

```bash
kb index              # 增量索引（仅索引变化的文件）
kb index --full       # 全量重建（切换 embedding 模型后需要）
```

索引过程：
1. 扫描 `notes/` 下所有 `.md` 文件
2. 计算 SHA256 哈希，比对变化
3. 更新 FTS5 全文索引
4. 生成/更新向量 embedding

### 4.8 RAG 问答

```bash
kb ask "Python 异步编程的核心概念是什么？"
kb ask "解释一下知识库中的设计模式" --stream      # 流式输出
kb ask "Docker 和虚拟机的区别" --top-k 3           # 指定参考笔记数
```

工作流程：
1. 混合搜索（FTS5 + 语义）检索相关笔记
2. 组装上下文
3. LLM 基于上下文生成回答

### 4.9 启动 Web UI

```bash
kb serve                         # 自动读取 config.toml 中 watch_dir 并同步
kb serve --port 3000 --host 0.0.0.0
kb serve --watch ~/blog/source/_posts   # 覆盖配置文件中的 watch_dir
```

浏览器打开 `http://127.0.0.1:8420`。

**Hexo 自动同步：** 在 `config.toml` 的 `[server]` 中配置 `watch_dir` 后，`kb serve` 启动时会自动：
1. 把 Hexo `_posts` 中的新文章复制到 `notes/`
2. 运行增量索引（全文 + 向量）
3. 持续监听 Hexo 目录，`.md` 文件变更时 200ms 防抖后自动重新索引

无需手动 `kb index`，也无需每次传 `--watch` 参数。

### 4.10 MCP 模式

```bash
kb mcp
```

供 Claude Code 等 AI Agent 调用，不要手动执行。

### 4.11 评测搜索质量

```bash
kb eval                          # 运行全部评测
kb eval --subset easy            # 按难度筛选（easy / medium / hard）
kb eval --category notes/tech/   # 按分类筛选
kb eval --search-mode semantic   # 指定搜索模式（hybrid / semantic / fts5）
kb eval --top-k 10               # 调整检索结果数量
kb eval --rag                    # 运行 RAG 并评分回答质量
kb eval --baseline               # 将本次结果设为基线
kb eval --compare baseline       # 与基线对比
```

评测维度：

| 指标 | 权重 | 说明 |
|------|------|------|
| Hit Rate | 25% | 期望来源是否出现在搜索结果中 |
| Avg Rank | 15% | 期望来源的平均排名 |
| MRR | 15% | 倒数排名均值（Mean Reciprocal Rank） |
| Keyword Score | 15% | 关键词覆盖率得分 |
| LLM Judge | 30% | LLM 对 RAG 回答质量评分（1-5） |

**生成评测数据集：**

```bash
python eval/generate_dataset.py
```

脚本遍历 vault 中所有笔记，用 LLM 生成 single-hop 和 multi-hop 查询对，输出到 `eval/dataset.json`。生成后请人工审核确认。

**评测结果文件结构：**

- `eval/results/baseline.json` — 基线结果（`--baseline` 生成）
- `eval/results/<timestamp>.json` — 每次评测的详细结果

```json
{
  "timestamp": "2026-05-10T...",
  "config": {"search_mode": "hybrid", "top_k": 5, "with_rag": false},
  "summary": {
    "total": 10,
    "hit_rate": 0.8,
    "avg_rank": 2.3,
    "mrr": 0.65,
    "keyword_score": 0.75,
    "llm_judge_avg": null,
    "overall": 0.6425
  },
  "details": [
    {
      "id": "q001",
      "hit": true,
      "rank": 1,
      "keyword_score": 1.0,
      "llm_judge": null,
      "llm_judge_reason": null
    }
  ]
}
```

**工作流建议：**

1. 初始上线时运行 `kb eval --baseline` 建立基线
2. 修改搜索/索引策略后运行 `kb eval --compare baseline` 检查是否退化
3. 定期补充 `eval/dataset.json` 中的评测查询
4. 将 `dataset.json` 提交到 Git，`results/` 不提交

---

## 5. Web UI

启动后访问 `http://127.0.0.1:8420`，左侧导航包含四个页面：

| 页面 | 路由 | 功能 |
|------|------|------|
| Notes | `/` | 笔记列表，支持按分类/标签过滤 |
| Detail | `/note/:id` | 查看笔记全文，Markdown 渲染，底部展示语义相关笔记推荐 |
| Search | `/search` | 三种搜索模式：全文 / 语义 / 混合 |
| Chat | `/chat` | RAG 对话，基于知识库内容的问答 |

### 5.1 搜索模式对比

| 模式 | 原理 | 适用场景 |
|------|------|----------|
| FTS5 | 关键词匹配 + jieba 中文分词 | 精确查找术语、文件名 |
| Semantic | BGE 向量 + 余弦相似度 | 模糊语义查询、近义词 |
| Hybrid | RRF 融合（推荐） | 综合两种结果，兼顾精确与语义 |

### 5.2 笔记编辑器

- 支持 Markdown 语法高亮
- 自动保存到文件
- 支持标签、分类、附件管理

---

## 6. MCP 集成（Claude Code）

### 6.1 配置

在 Claude Code 的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "kb": {
      "command": "kb",
      "args": ["mcp"]
    }
  }
}
```

配置文件位置：
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 6.2 可用工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `kb_search` | 全文搜索（FTS5 + jieba） | `query`, `limit` |
| `kb_semantic_search` | 语义搜索（BGE + LanceDB） | `query`, `limit` |
| `kb_hybrid_search` | 混合搜索（RRF 融合） | `query`, `limit` |
| `kb_read` | 读取笔记全文 | `file_id` |
| `kb_list` | 按分类/标签列出笔记 | `category`, `tag`, `limit` |
| `kb_add` | 创建新笔记 | `title`, `content`, `category`, `tags`, `description` |
| `kb_rag_query` | RAG 问答 | `query`, `top_k` |

### 6.3 使用示例

在 Claude Code 中直接说：

> "搜索知识库中关于 Python 异步的内容"

> "知识库里有哪些 tech 分类的笔记？"

> "根据我的知识库，Docker Compose 应该怎么用？"

---

## 7. 笔记格式

kb 使用 Hexo 兼容的 YAML frontmatter + Markdown：

```markdown
---
title: Python 异步编程
tags: python, async, asyncio
category: tech
date: 2026-05-06
description: asyncio 标准库详解
---

# Python 异步编程

asyncio 是 Python 3.4+ 引入的标准库。

## 事件循环

事件循环（Event Loop）是 asyncio 的核心概念...

## 协程

协程通过 `async def` 定义，使用 `await` 等待...
```

创建笔记有两种方式：
1. `kb add "标题"` — CLI 创建，自动生成模板
2. 手动创建 `.md` 文件后运行 `kb index` 建立索引

---

## 8. 跨平台迁移

整个知识库就是一个普通文件夹，迁移只需 Git：

### 8.1 从 Windows 导出

```bash
cd ~/Desktop/kb
git init
git add -A
git commit -m "init knowledge base"
git remote add origin <your-repo-url>
git push -u origin main
```

### 8.2 在 Mac 上导入

```bash
git clone <your-repo-url> ~/kb
cd ~/kb
pip install -e .
kb index --full
```

### 8.3 同步策略

| 内容 | 同步方式 | 说明 |
|------|----------|------|
| `notes/` | Git | Markdown 文件，跨设备同步 |
| `attachments/` | Git LFS | 二进制附件 |
| `config.toml` | Git | 配置共享（API key 用环境变量，不写入文件） |
| `.kb/` | 不同步 | 索引文件，每台设备独立运行 `kb index --full` 生成 |

---

## 9. 前置依赖

| 功能 | 依赖 | 安装 |
|------|------|------|
| 基础功能 | Python 3.11+ | `pip install -e .` |
| 全文搜索 | SQLite FTS5 | 内置，无需额外安装 |
| 语义搜索 | BGE-small-zh | 首次使用自动下载（~100MB） |
| RAG / 问答 | LLM 提供商 | Ollama（推荐，本地免费）或 OpenAI/Anthropic API key |

### 9.1 安装 Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# 下载安装包: https://ollama.com/download/windows

# 拉取模型
ollama pull qwen2.5:7b

# 验证
ollama run qwen2.5:7b "Hello"
```

---

## 10. 常见问题

### Q: 修改了 config.toml 后需要重启吗？

CLI 命令每次读取最新配置，无需重启。但 `kb serve` 需要重启以应用新配置。

### Q: 切换了 embedding 模型，搜索不准怎么办？

```bash
kb index --full
```

这会删除旧向量并重新生成所有 embedding。

### Q: .kb 目录很大怎么办？

`.kb/vectors.lance/` 存储向量数据，体积与笔记量成正比。可以安全删除后重建：

```bash
rm -rf .kb
kb index --full
```

### Q: kb ask 报 LLM 错误？

检查配置中的 LLM provider：
- Ollama：确认 `ollama serve` 正在运行，模型已 pull
- OpenAI / Anthropic：确认设置了对应的环境变量 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`

### Q: 搜索不到想要的内容？

1. 确认文件已索引：`kb index`
2. 尝试语义搜索模式（上传到 Web UI 搜索页选择 "semantic"）
3. 尝试混合搜索模式（"hybrid"）

### Q: 如何备份？

```bash
git add -A && git commit -m "backup"
git push
```

Markdown 文件是知识的唯一源，只要 Git 仓库在，一切都可以重建。

---

## 11. API 参考

### 11.1 REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notes` | 列出笔记 |
| POST | `/api/notes` | 创建笔记 |
| GET | `/api/notes/{file_id}` | 读取笔记 |
| PUT | `/api/notes/{file_id}` | 更新笔记 |
| DELETE | `/api/notes/{file_id}` | 删除笔记 |
| GET | `/api/search?q=&mode=&limit=` | 搜索笔记 |
| GET | `/api/semantic-search?q=&limit=` | 语义搜索 |
| GET | `/api/tags` | 获取所有标签 |
| GET | `/api/categories` | 获取所有分类 |
| POST | `/api/attachments` | 上传附件 |
| GET | `/api/index` | 索引进度 |
| POST | `/api/index` | 触发索引 |
| POST | `/api/chat/ask` | RAG 问答（非流式） |
| GET | `/api/notes/{file_id}/related?limit=5` | 相关笔记推荐 |
| POST | `/api/chat` | RAG 问答（SSE 流式） |

### 11.2 Chat 接口

**非流式请求：**

```bash
curl -X POST http://127.0.0.1:8420/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是 Python 异步？", "top_k": 5}'
```

响应：

```json
{
  "answer": "Python 异步编程基于 asyncio 标准库...",
  "model": "qwen2.5:7b",
  "tokens_used": 150
}
```

**流式请求：**

```bash
curl -X POST http://127.0.0.1:8420/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "解释 Docker Compose", "top_k": 3}'
```

SSE 事件流：

```
data: {"text":"Docker"}
data: {"text":" Compose"}
data: {"text":" 是"}
data: {"text":"..."}
data: {"done":true}
```
