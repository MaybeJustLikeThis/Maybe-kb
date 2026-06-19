# kb 使用手册

`kb` 是本地优先的个人知识库：Markdown 是知识源，搜索索引和向量数据可以随时重建。

## 1. 第一次使用

普通用户优先使用 setup 向导，不需要手动编辑配置：

```bash
pip install -e .
kb setup
kb serve
```

`kb setup` 会帮你连接 Obsidian、已有 Markdown 文件夹，或创建新的空知识库。建立搜索数据只会生成本地 `.kb/` 索引文件，不会修改原始笔记。

启动后访问 `http://127.0.0.1:8420`，先在 Overview 查看 `System Health` 系统健康。

## 2. 我用 Obsidian

运行 `kb setup` 后选择 `Obsidian vault`，输入你的 vault 路径。完成后运行 `kb serve`，在 Overview 的 `System Health` 检查 notes、vectors、coverage 是否正常。

Obsidian 模式会启用 `Open in Obsidian`。如果只想把一个普通文件夹当作 Markdown 来源，也可以选择 Markdown folder。

## 3. 我有 Markdown 文件夹

运行 `kb setup` 后选择 `Markdown folder`，输入包含 `.md` 或 `.pdf` 的文件夹路径。`kb` 会把这个文件夹作为知识来源，并在其中创建 `.kb/` 搜索数据目录。

这个模式不会修改原始笔记。之后如果你在 Web UI 或 CLI 中新建笔记，`kb` 会把新笔记写入这个文件夹下的分类目录。

## 4. 我想先试用

运行 `kb setup` 后选择 `New empty vault`。它会创建一个新的空知识库目录，包含 `notes/`、`attachments/` 和 `.kb/`。

之后可以创建第一篇笔记：

```bash
kb add "我的第一篇笔记"
kb index --full
kb serve
```

## 5. 搜索不到内容

先运行：

```bash
kb index --full
```

然后回到 Web UI 的 `System Health` 看：

- notes：是否已经读取到笔记。
- vectors：是否已经建立语义搜索数据。
- coverage：是否有足够内容可用于智能搜索和 Chat。

如果 notes 是 0，通常是连接的目录不对，重新运行 `kb setup` 选择正确的 Obsidian vault 或 Markdown 文件夹。

## 6. Chat 不能回答

Chat 需要搜索数据，也需要 LLM/embedding provider 可用。先确认 `System Health` 没有 setup issue；如果只是 LLM 未准备好，Search 仍然可以使用。

默认来源包括：

- 博客：Hexo 博客文章
- Agent 沉淀：Agent 自动沉淀的知识
- 手动录入：手动创建的知识笔记
- 未分类：缺少分类时的默认分类

## 7. 高级配置

只有当你需要改端口、模型、来源标签、Obsidian 打开方式时，再编辑 `config.toml`。

常见高级命令：

```bash
kb index --full
kb import /path/to/document.pdf
kb import /path/to/notes.docx
kb ask "根据我的知识库回答一个问题"
```
