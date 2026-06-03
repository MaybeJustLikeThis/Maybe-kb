# Obsidian Vault-First Redesign

日期：2026-06-03

状态：待用户 review

## 1. 背景

当前 `kb` 已经从普通本地笔记系统演进成一个本地优先的知识引擎：它支持 Markdown 存储、全文搜索、语义搜索、混合检索、RAG 问答、MCP 工具、Agent 知识沉淀、附件上传、Dashboard、Manage 页面和评测体系。

与此同时，项目内 Web UI 也承担了一部分 Markdown 编辑器职责。这个方向会和 Obsidian、Typora、VS Code 等成熟编辑器重复，并且会把维护重点拉向低差异化的编辑体验。

本设计将个人知识库部分调整为 Obsidian-first：Obsidian 负责主编辑和个人浏览体验，`kb` 保持独立知识引擎定位，负责采集、索引、搜索、RAG、MCP、Agent 沉淀和控制台管理。

## 2. 目标

- 将个人知识 vault 从代码仓库中分离出来，迁移到 `D:\ObsidianVault`。
- 让 Obsidian 成为主编辑器和个人笔记浏览入口。
- 让 `kb` 继续作为独立知识引擎运行，不依赖 Obsidian 正在打开。
- Web UI 调整为知识控制中心，弱化 Web 编辑入口。
- 第一阶段支持从 Web 搜索、详情、RAG sources 打开对应 Obsidian 笔记。
- 迁移过程中保留旧 `notes/` 作为回滚备份，验证稳定后再停用或删除。

## 3. 非目标

- 第一阶段不开发 Obsidian 插件。
- 第一阶段不把 `kb` 改造成 Obsidian 插件或只依附于 Obsidian 的服务。
- 第一阶段不重构完整多 source registry。
- 第一阶段不删除 MCP、CLI、API 的写入能力，Agent 仍可通过 `kb_save` 或 API 沉淀知识。
- 第一阶段不自动删除旧 `C:\Users\cherry\Desktop\kb\notes`。

## 4. 推荐路线

采用 Vault-First 重构：

- `C:\Users\cherry\Desktop\kb` 保持为 `kb` 引擎项目代码仓库。
- `D:\ObsidianVault` 成为个人知识数据根目录。
- Obsidian 打开 `D:\ObsidianVault`。
- `kb` 通过配置读取、索引、问答和管理 `D:\ObsidianVault`。
- Web UI 使用 Obsidian URI 回跳到具体笔记。

该路线比最小兼容改动更清楚，也避免第一阶段一次性吃下完整多源系统重构。

## 5. 目录结构

目标结构：

```text
C:\Users\cherry\Desktop\kb
  ├─ src/
  ├─ web/
  ├─ tests/
  ├─ docs/
  ├─ config.toml
  └─ ...代码项目文件

D:\ObsidianVault
  ├─ .obsidian/
  ├─ notes/
  │  ├─ AI/
  │  ├─ 前端/
  │  ├─ 技术/
  │  ├─ 杂谈/
  │  └─ ...
  ├─ attachments/
  └─ .kb/
     ├─ kb.db
     └─ vectors.lance/
```

`D:\ObsidianVault` 中保留 `notes/` 子目录，而不是把所有 Markdown 平铺在 vault 根目录。原因：

- Obsidian 可以正常打开整个 vault。
- `kb` 可以只索引 `notes/`，避免扫到 `.obsidian/`、`.kb/`、附件、模板和插件数据。
- 当前 `notes/AI`、`notes/前端`、`notes/杂谈` 等目录可以原样迁移。
- `attachments/` 和 `.kb/` 属于知识数据，放在 vault 内更自然。

## 6. 配置模型

当前配置中的 `general.vault_path = "."` 和 `server.watch_dir` 混合了项目目录、知识 vault 和外部博客监听。第一阶段改为明确区分：

```toml
[general]
vault_path = "D:/ObsidianVault"
notes_dir = "notes"
attachments_dir = "attachments"
index_dir = ".kb"

[obsidian]
enabled = true
vault_name = "ObsidianVault"
vault_path = "D:/ObsidianVault"
open_uri_strategy = "file"

[server]
host = "127.0.0.1"
port = 8420
watch_enabled = true
```

含义：

- `general.vault_path` 是知识数据根目录。
- `general.notes_dir` 是 `kb` 索引的 Markdown 子目录。
- `general.attachments_dir` 是附件目录。
- `general.index_dir` 是 SQLite 和 LanceDB 等生成数据目录。
- `obsidian.enabled` 控制 Web UI 是否显示 Obsidian 打开入口。
- `obsidian.vault_name` 用于生成 `obsidian://open` URI。
- `server.watch_enabled` 控制 `kb serve` 是否监听 vault 内笔记变化。

现有 `[sources.blog]`、`[sources.agent]`、`[sources.manual]` 第一阶段保留，但其语义应明确为知识来源标签，而不是文件系统 root。

`server.watch_dir` 第一阶段保留兼容读取，但新流程不依赖它。博客同步应在后续阶段改成显式导入命令。

## 7. 索引设计

第一阶段只索引：

```text
D:\ObsidianVault\notes/**/*.md
```

明确忽略：

```text
D:\ObsidianVault\.obsidian/**
D:\ObsidianVault\.kb/**
D:\ObsidianVault\attachments/**
D:\ObsidianVault\templates/**
```

`discover_notes()` 应从扫描整个 vault 改为扫描 `vault / notes_dir`。生成的 `file_id` 仍使用相对 vault 的路径，例如：

```text
notes/AI/mcp-server-搭建踩坑记录.md
```

这样 API、MCP、Obsidian URI 和静态文件访问都可以共享同一个相对路径语义。

索引流程保持现有能力：

1. 发现 `notes/**/*.md`。
2. 解析 Markdown 和 frontmatter。
3. 更新 SQLite note 元数据和 FTS5。
4. 对变更文件更新 LanceDB 向量 chunks。
5. 对已删除文件清理数据库记录和向量记录。

## 8. 监听设计

`kb serve` 启动后监听：

```text
D:\ObsidianVault\notes
```

监听到 `.md` 创建、修改、删除、移动后：

1. debounce。
2. 增量调用索引流程。
3. 更新 FTS5。
4. 更新对应向量。
5. 清理已不存在文件的记录。

附件变化第一阶段不主动触发索引。附件本身通常不是独立知识条目，除非 Markdown 引用发生变化。

## 9. 迁移流程

推荐新增迁移命令：

```powershell
kb obsidian init-vault --target D:\ObsidianVault --from-notes C:\Users\cherry\Desktop\kb\notes
```

命令职责：

1. 检查目标目录，不存在则创建。
2. 创建 `notes/`、`attachments/`、`.obsidian/` 基础目录。
3. 复制旧 `notes/` 到 `D:\ObsidianVault\notes`。
4. 复制旧 `attachments/` 到 `D:\ObsidianVault\attachments`。
5. 不复制旧 `.kb`，新 vault 重新生成索引。
6. 更新项目 `config.toml`。
7. 运行一次 `kb index --full`。
8. 输出验证摘要：复制笔记数、附件数、索引笔记数、向量数。
9. 不自动删除旧 `notes/`。

旧 `notes/` 的停用应在验证后执行，可以重命名为：

```text
C:\Users\cherry\Desktop\kb\notes.legacy-backup
```

## 10. Web UI 设计

Web UI 调整为知识控制中心。

保留并强化：

- Overview：vault 状态、索引健康、最近活动、来源分布。
- Search：全文、语义、混合搜索，展示命中片段和来源。
- Chat：RAG 问答，答案 sources 可回跳笔记。
- Manage：标签、分类、来源、索引维护。
- Source 页面：按 `source_project` 查看 blog、agent、manual 等沉淀。

弱化：

- NoteDetail 的编辑模式。
- MarkdownEditor 主入口。
- Web 上的 New Note 主路径。

第一阶段可以保留编辑相关代码，但默认阅读，主操作改为 `Open in Obsidian`。创建笔记能力仍保留给 MCP、API、CLI 和 Agent。

## 11. Obsidian URI

Obsidian 打开链接格式：

```text
obsidian://open?vault=ObsidianVault&file=notes%2FAI%2Fxxx.md
```

规则：

- `vault` 来自 `config.obsidian.vault_name`。
- `file` 是相对 vault 的路径。
- 中文、空格、括号等字符必须 URL encode。
- 后端必须校验路径在 vault 内，不能暴露任意 D 盘文件。

新增 API：

```http
GET /api/v1/notes/{file_id}/open-target
```

返回：

```json
{
  "data": {
    "obsidian_uri": "obsidian://open?vault=ObsidianVault&file=notes%2FAI%2Fxxx.md",
    "file_path": "D:/ObsidianVault/notes/AI/xxx.md",
    "relative_path": "notes/AI/xxx.md"
  },
  "meta": {},
  "error": null
}
```

前端展示位置：

- NoteDetail 顶部主按钮。
- Search result item。
- RAG source item。
- Related notes 和 recent activity 的辅助操作。

## 12. 博客同步处理

当前 `server.watch_dir` 指向 Hexo `_posts`，并在 `index_files(... external_sources, source_project="blog")` 中隐式同步博客。

第一阶段不把博客同步纳入主监听流程。建议后续改为显式命令：

```powershell
kb import-blog --path "C:\...\source\_posts"
```

博客导入仍写入：

```yaml
source_project: blog
```

这样 Obsidian 主 vault 监听和博客同步不会互相污染。

## 13. 测试策略

后端测试：

- 配置加载：绝对路径 `D:/ObsidianVault`、缺省值、兼容旧配置。
- 路径安全：API 不能读取 vault 外文件。
- storage：只发现 `notes/**/*.md`。
- storage：忽略 `.obsidian/`、`.kb/`、`attachments/`、`templates/`。
- indexer：迁移后可正确 upsert/delete。
- Obsidian URI：中文路径、空格、括号、斜杠 encode 正确。
- MCP：`kb_save` 写入新 vault。
- API：`/api/v1/notes/{file_id}/open-target` 返回正确 envelope。

前端测试：

- `npm run build` 通过。
- NoteDetail 显示 `Open in Obsidian`。
- Search result 和 RAG source 能获取 open target。
- Web UI 不再把编辑作为主路径。

手动验收：

- Obsidian 能打开 `D:\ObsidianVault`。
- `kb index --full` 成功。
- Web Search 能找到旧笔记。
- Chat/RAG sources 能指向 vault 内笔记。
- Agent `kb_save` 创建的新笔记能在 Obsidian 中出现。

## 14. 回滚策略

- 迁移时只复制，不删除旧 `notes/`。
- 旧 `.kb` 不迁移，新 vault 重新生成。
- 如果新配置有问题，可以把 `config.toml` 的 `vault_path` 改回 `"."`。
- 旧 `notes/` 只在验证稳定后重命名为 `notes.legacy-backup` 或删除。
- 本次设计不要求修改远端博客源目录。

## 15. 分阶段实施

### Phase 1：Vault-First 基础迁移

- 新建 `D:\ObsidianVault`。
- 复制旧 `notes/` 和 `attachments/`。
- 更新配置模型。
- 修改 storage/indexer/AppContext/CLI/API 使用配置中的 vault。
- 对新 vault 重建索引。
- 验证 Obsidian、搜索、RAG、MCP。

### Phase 2：Web UI 控制台化

- NoteDetail 默认阅读。
- 顶部主按钮改为 `Open in Obsidian`。
- Search result 和 RAG source 增加打开入口。
- 弱化 Web 编辑和 New Note 主入口。
- 保留 API/MCP/CLI 创建笔记能力。

### Phase 3：Source Sync 整理

- 废弃 `server.watch_dir` 的默认隐式同步语义。
- 新增显式博客导入或 source sync 命令。
- 保留 source distribution 和 Dashboard 展示。
- 第二阶段以后再评估 Obsidian 插件。

## 16. 成功标准

- `kb` 项目代码和个人知识数据完成分离。
- `D:\ObsidianVault` 可作为 Obsidian vault 正常使用。
- `kb` 在 Obsidian 未启动时也能索引、搜索、问答和响应 MCP。
- Web UI 的主要操作从编辑转为控制、检索、问答和打开 Obsidian。
- 旧笔记无损迁移，旧 `notes/` 可作为回滚备份。
