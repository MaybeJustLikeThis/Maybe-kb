# kb — Local Knowledge Base

本地优先的知识库系统，支持全文搜索、语义搜索、MCP 协议接入 AI Agent，一键 Hexo 博客同步。

## 项目状态

**Phase 1-7 全部完成。**

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | CLI 核心（CRUD / FTS5 全文搜索 / 增量索引） | ✓ 完成 |
| Phase 2 | Web UI（FastAPI + Vue 3 + Markdown 编辑器） | ✓ 完成 |
| Phase 3 | 语义搜索 + MCP Server（LanceDB + BGE + 混合搜索 RRF） | ✓ 完成 |
| Phase 4 | RAG 对话（LLM Provider + CLI/API/Web/MCP） | ✓ 完成 |
| Phase 5 | Hexo 自动同步 + 相关笔记推荐（watchdog 监听 + 语义关联） | ✓ 完成 |
| Phase 6 | 评测体系（数据集生成 / kb eval / 评分引擎 / 基线对比） | ✓ 完成 |
| Phase 7 | 统一可视化管理（Dashboard 增强 + /manage 深度管理 + 多源类型系统） | ✓ 完成 |

## 快速启动

```powershell
# Windows（PowerShell）
.\scripts\start.ps1

# 跳过文件监听、自动打开浏览器
.\scripts\start.ps1 -OpenBrowser -SkipWatch
```

```bash
# macOS / Linux
./scripts/start.sh

# 环境变量控制
KB_SKIP_WATCH=1 KB_BACKEND_PORT=8420 ./scripts/start.sh
```

脚本自动处理：查找 Python → 检查依赖 → 清理端口 → 启动前后端 → 健康检查 → 打印地址。

详细说明见 [USER_GUIDE.md](./USER_GUIDE.md) 第 4.9 节。

## 已实现功能

- **笔记 CRUD**：Markdown 文件 + YAML frontmatter（含 `type` 知识类型字段），兼容 Hexo 格式
- **多源类型系统**：5 种知识类型（技术文章/踩坑记录/设计决策/代码片段/文档摘要），按类型分子目录管理，支持来源项目追踪
- **全文搜索**：SQLite FTS5 + jieba 中文分词
- **语义搜索**：BGE-small-zh embedding + LanceDB 向量存储
- **混合搜索**：RRF（Reciprocal Rank Fusion）融合全文与语义结果
- **增量索引**：SHA256 文件哈希检测变更，仅索引变化文件
- **Web UI**：Vue 3 + Tailwind CSS，Dashboard 总览（统计卡片+类型柱状图+索引健康度+来源项目+内容格式饼图）/ 笔记浏览 / Markdown 编辑（语法高亮）/ 搜索 / 附件上传 / Manage 深度管理（按类型/分类/标签/来源/索引五个维度）
- **MCP Server**：7 个工具（kb_search / kb_semantic_search / kb_hybrid_search / kb_read / kb_list / kb_add / kb_rag_query）
- **RAG 对话**：多 LLM 提供商（Ollama / OpenAI / Anthropic），一键配置切换
- **CLI 问答**：`kb ask "问题"` 命令行 RAG 查询，支持流式输出
- **Web Chat**：ChatPage 聊天气泡界面，打字动画，自动滚动
- **笔记详情**：阅读 / 编辑双模式切换，相关笔记推荐
- **路径安全**：所有文件操作统一防穿越
- **多设备同步**：Markdown 文件通过 Git 同步，索引每台设备独立生成
- **Hexo 自动同步**：`kb index --full` / `kb serve` 自动同步 Hexo `_posts/` 目录下的 Markdown 文章及关联图片资源文件夹，`kb serve` 持续监听变更
- **相关笔记推荐**：笔记详情页底部展示语义相似的其他笔记
- **评测体系**：`kb eval` 命令运行搜索评测，支持评分（命中率/MRR/关键词/LLM 裁判）、基线对比、难度分类筛选

## 目录结构

```
kb/
├── pyproject.toml              # Python 项目配置
├── config.toml                 # 知识库配置（提交到 Git）
├── README.md
├── .gitignore
│
├── notes/                      # 知识内容（Markdown，Git 管理）
│   ├── tech-article/            # 技术文章
│   ├── document/                # 文档摘要
│   ├── troubleshooting/         # 踩坑记录
│   ├── design-decision/         # 设计决策
│   └── code-snippet/            # 代码片段
│
├── attachments/                # 附件（PDF/图片，Git LFS）
│
├── .kb/                        # 生成数据（.gitignore 忽略）
│   ├── kb.db                   # SQLite 数据库（FTS5 + 元数据）
│   └── vectors.lance/          # LanceDB 向量索引
│
├── eval/                        # 评测系统
│   ├── README.md                # 评测使用文档
│   ├── dataset.json             # 评测查询集（版本控制）
│   ├── generate_dataset.py      # 从 vault 笔记自动生成评测数据
│   └── results/                 # 评测结果（.gitignore 忽略）
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
│   │   ├── context.py          # AppContext 统一资源容器
│   │   ├── services.py         # 共享 CRUD 服务编排
│   │   ├── search.py           # 混合搜索 RRF 融合
│   │   ├── indexer.py          # 索引编排（文件发现 / 同步 / 向量化）
│   │   ├── rag.py              # RAG 编排（搜索→组装→生成）
│   │   ├── eval.py             # 评测引擎（评分/LLM 裁判/基线对比）
│   │   ├── serializers.py     # 统一序列化（Note → API dict）
│   │   ├── watcher.py          # 文件监听（watchdog，自动索引）
│   │
│   └── data/                   # 数据持久化层
│       ├── storage.py          # Markdown 文件读写 + chunk + 路径安全
│       ├── database.py         # SQLite + FTS5 索引
│       ├── vector.py           # LanceDB 向量存储
│       ├── embedding.py        # Embedding Provider 抽象（local + openai）
│       ├── llm.py              # LLM Provider 抽象（ollama / openai / anthropic）
│       └── attachments.py      # 附件存储（内容哈希去重）
│
├── web/                        # 前端（Vue 3 + Vite + Tailwind CSS）
│   ├── scripts/
│   │   └── kill-port.js        # 开发前清理端口占用
│   └── src/
│       ├── App.vue
│       ├── main.ts             # 路由注册
│       ├── api.ts              # API 客户端
│       ├── topBar.ts           # 顶部工具栏状态管理
│       ├── assets/
│       │   └── base.css        # 全局基础样式 + CSS 变量
│       ├── pages/
│       │   ├── DashboardPage.vue   # 首页 Overview（统计卡片+图表+快捷操作）
│       │   ├── ManagePage.vue      # 深度管理（5 个 Tab 维度切换）
│       │   ├── NoteList.vue
│       │   ├── NoteDetail.vue
│       │   ├── SearchPage.vue
│       │   └── ChatPage.vue
│       └── components/
│           ├── MarkdownEditor.vue
│           ├── StatCard.vue
│           ├── TypeDistribution.vue  # 类型柱状图（纯 CSS）
│           ├── IndexHealth.vue       # 索引健康度面板
│           ├── SourceProjects.vue    # 来源项目列表
│           ├── ContentFormatPie.vue  # 内容格式饼图（CSS conic-gradient）
│           ├── QuickActions.vue      # 快捷操作按钮
│           ├── CategoryList.vue
│           ├── TagCloud.vue
│           └── RecentNotes.vue       # 最近更新（带 type badge）
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
    ├── test_indexer.py
    ├── test_dashboard.py
    ├── test_mcp.py
    ├── test_eval.py
    ├── test_eval_cli.py
    └── test_watcher.py
```

## 与 Hexo 博客集成

kb 配置 `watch_dir` 指向 Hexo 博客的 `source/_posts/` 后：

- `kb index --full` 或 `kb serve` 启动时将博客文章同步到 kb vault
- **图片资源文件夹**（Hexo asset folder）同步拷贝，Web UI 中图片可正常显示
- `kb serve` 持续监听博客目录变更，自动增量索引
- 通过 MCP Server，Claude Code 可以直接搜索、阅读、问答博客内容

**Markdown 图片路径建议**：使用 `![](文章名/图片名.webp)` 格式，兼容 Typora / VS Code / Hexo / kb 所有环境；避免裸文件名 `![](图片名.webp)`，该格式仅 Hexo `postAsset: true` 支持。

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

# 启动 Web UI（自动同步 Hexo 博客）
kb serve
kb serve --skip-watch  # 跳过文件监听，仅启动 API

# 评测搜索质量
kb eval
kb eval --subset easy --rag
kb eval --baseline
kb eval --compare baseline

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
# 配置 Hexo 博客源目录，kb serve 启动时自动同步
# 同步内容包括 Markdown 文章 + 同名资源文件夹（图片等）
watch_dir = "C:/Users/cherry/Desktop/项目/blog_new/blog_new/source/_posts"

# 知识类型定义（Dashboard 类型分布 + 搜索过滤）
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

[kb_types.design-decision]
label = "设计决策"
description = "架构选择、取舍理由、上下文"
default_tags = ["design"]
parser = "markdown"

[kb_types.code-snippet]
label = "代码片段"
description = "可复用的代码模式、脚本"
default_tags = ["snippet"]
parser = "markdown"

[kb_types.document]
label = "文档摘要"
description = "PDF、论文、文档的阅读笔记，可上传文件"
default_tags = ["document"]
parser = "auto"
```
