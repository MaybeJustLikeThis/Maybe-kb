# kb 使用手册

`kb` 是本地优先的个人知识库：Markdown 是知识源，索引和向量数据可以随时重建。

## 1. 安装

```bash
pip install -e .
kb --help
```

## 2. 初始化

```bash
kb init
kb index --full
kb serve
```

启动后访问 `http://127.0.0.1:8420`。

## 3. 系统健康

首次打开 Web UI 时，先在 Overview 查看 `System Health`。系统健康会检查 vault、notes、attachments、索引目录、Obsidian、embedding、LLM 和向量覆盖率。

如果看到 `Rebuild index`，先运行：

```bash
kb index --full
```

## 4. 添加、搜索与问答

```bash
kb add "我的第一篇笔记"
kb search "关键词"
kb ask "根据我的知识库回答一个问题"
```

Web UI 中可以使用 Search 和 Chat 完成搜索与 RAG 问答。

## 5. 默认来源

- 博客：Hexo 博客文章
- Agent 沉淀：Agent 自动沉淀的知识
- 手动录入：手动创建的知识笔记
- 未分类：缺少分类时的默认分类

这些名称来自 `config.toml`，侧边栏会在读取失败时使用同样的中文兜底文案。

## 6. 常见处理

- 搜索不到内容：运行 `kb index --full` 后重试。
- LLM 问答失败：检查 Ollama 或对应 API key 环境变量。
- 换设备迁移：同步 Markdown、attachments 和 `config.toml`，然后在新设备运行 `kb index --full`。
