# Knowledge Import and Indexing: 文档与图片导入闭环设计

## 目标

把 `kb` 的下一阶段重心收束为个人知识库管理工具，而不是以 Claude/Codex 长期记忆插件为主线。Claude/Codex 入口保持可用，但核心能力优先服务本地知识资产的导入、整理、检索和追溯。

第一阶段要打通文档与图片资料导入闭环：

- PDF/DOCX 导入后保存原件，转换成 Markdown note，并进入全文与语义索引。
- 图片上传后由用户选择“作为独立知识”或“挂到已有笔记”。
- 导入生成的 note 保留来源、原始附件、内容类型、解析器状态等可追溯信息。
- 新建、导入、挂载附件后保持 SQLite/FTS 与 LanceDB 向量索引一致。
- RAG 与 MCP 问答返回引用来源，用户可以回读原文和原件。

## 非目标

本阶段不做这些事情：

- 不做网页/URL 导入。
- 不把 Claude/Codex 自动长期记忆作为主产品能力。
- 不做复杂图片理解作为强依赖；OCR 和视觉 caption 只保留扩展接口。
- 不做大规模外部文件库批量同步。
- 不把附件系统变成独立网盘；附件仍然服务于 note。

## 当前问题

### 入库字段没有完整打通

当前 API schema、`services.create_note()`、数据库列已经出现 `source_path`、`content_type`、attachments 等字段，但 `IngestRequest` 与 `ingest()` 主入口没有完整承接这些字段。结果是多个入口看起来支持元数据，实际落盘时会丢失一部分信息。

### 保存后索引不一致

`kb_save`、`kb_add` 和 API 创建 note 后会写 Markdown、SQLite、FTS，但不会保证单篇向量索引同步更新。用户可能遇到“列表有、关键词能搜、语义搜索或 RAG 找不到”的割裂体验。

### attachments 仍是旁路存储

当前附件上传主要是保存文件并返回路径，没有自动关联 note，也没有解析、索引或可见状态。对个人知识库来说，上传文件后没有真正变成知识。

### parser registry 没接入主流程

项目已有 `ParserRegistry`、PDF/DOCX/Image parser，但主要入口仍然围绕 Markdown 文件或直接传入的 content 字段。解析器设计已经有雏形，但导入链路还没有闭环。

### RAG 缺少引用来源

RAG 当前偏向只返回答案，缺少 `file_id`、标题、片段和附件引用。个人知识库问答必须能回溯资料，否则可信度不足。

## 产品定位

`kb` 的核心体验是个人知识库管理：

1. 用户把资料导入知识库。
2. 系统保存原件并生成可读 Markdown note。
3. note 进入全文搜索、语义搜索和 RAG。
4. 用户能在 Web UI 中整理标题、分类、标签、描述和附件关系。
5. Claude/Codex 通过 MCP 访问同一套知识，但不主导知识管理流程。

## 架构设计

新增或重整一条统一导入主干：

```text
ImportRequest
-> AttachmentStore
-> Parser / Converter
-> Ingest
-> IndexUpdater
-> Search / RAG
```

### AttachmentStore

职责是保存原始文件资产，沿用现有 `attachments/YYYY/MM/{hash}{ext}` 去重策略。

它只负责：

- 读取上传文件或本地文件。
- 计算内容 hash。
- 保存到 vault 的 attachments 目录。
- 返回相对路径、原始文件名、扩展名、大小等基础元数据。

它不负责：

- 判断文件含义。
- 生成 note。
- 更新索引。

### Parser / Converter

职责是把文件转换成统一的 `ParsedContent`。

建议输出结构扩展为：

```python
ParsedContent(
    text: str,
    metadata: dict[str, Any],
    attachments: list[Path],
)
```

其中 metadata 至少包含：

- `parser.name`
- `parser.status`
- `parser.original_filename`
- `parser.converted_at`
- `content_type`

PDF/DOCX 的优先级：

1. 优先使用 MarkItDown 转换成 Markdown。
2. MarkItDown 失败时 fallback 到现有 PDF/DOCX parser。
3. 所有失败都保留 attachment，并返回明确失败阶段。

图片第一阶段的策略：

- 独立知识：生成 Markdown 图片引用和基础 metadata。
- 挂到已有笔记：只返回 attachment metadata，正文插入由调用方决定。
- OCR/caption 暂不作为强依赖。

### Ingest

`ingest()` 继续作为创建 note 的唯一主入口。它需要补齐对这些字段的支持：

- `source_path`
- `content_type`
- `attachments`
- `extra_frontmatter` 或 parser metadata

所有入口都应该通过 `ingest()` 或明确的 update service，不应绕过主干：

- Web API
- CLI
- MCP
- 文件导入服务
- 后续批量同步

### IndexUpdater

新增单篇索引更新能力，用于导入、保存、编辑和附件挂载后的即时同步。

它负责：

- 更新 SQLite notes 表和 FTS。
- 对目标 note 重新 chunk。
- 删除旧 LanceDB chunks。
- 写入新 LanceDB chunks。
- 返回索引状态。

它不负责：

- 创建 note。
- 解析文件。
- 调用 LLM 总结。

### Search / RAG

搜索和 RAG 需要返回可追溯来源。RAG 响应建议包含：

```json
{
  "answer": "...",
  "model": "...",
  "tokens_used": 0,
  "sources": [
    {
      "file_id": "notes/document/paper.md",
      "title": "Paper",
      "snippet": "...",
      "source_project": "upload",
      "attachments": ["attachments/2026/06/abc123.pdf"]
    }
  ]
}
```

## 数据模型

### 文档导入 note

PDF/DOCX 导入后，原件存在 attachments，note 正文是转换后的 Markdown。

建议 frontmatter：

```yaml
---
title: Example Paper
categories: document
tags:
  - imported
  - pdf
source_project: upload
source_path: attachments/2026/06/abc123.pdf
source_context: 用户上传的资料
content_type: pdf
attachments:
  - attachments/2026/06/abc123.pdf
parser:
  name: markitdown
  status: success
  original_filename: example.pdf
  converted_at: "2026-06-02T15:30:00"
---
```

这里 `content_type` 表示导入原件类型，不表示 note 正文格式。note 正文仍然是 Markdown。

### 图片作为独立知识

适合错误截图、架构图、设计图、白板照片、资料截图。

建议 frontmatter：

```yaml
---
title: 支付失败截图
categories: troubleshooting
tags:
  - screenshot
  - payment
source_project: upload
source_path: attachments/2026/06/img123.png
source_context: 用户上传的截图
content_type: image
attachments:
  - attachments/2026/06/img123.png
parser:
  name: image-reference-parser
  status: success
  original_filename: payment-error.png
  converted_at: "2026-06-02T15:30:00"
---
```

正文：

```markdown
# 支付失败截图

![](/vault/attachments/2026/06/img123.png)

## 备注

等待补充说明。
```

### 图片挂到已有笔记

适合博客配图、排障步骤中的截图、设计决策中的架构图。

流程：

1. 保存图片到 attachments。
2. 更新目标 note frontmatter 的 `attachments`。
3. 可选把 Markdown 图片引用插入正文。
4. 更新目标 note 的 FTS 与向量索引。

不新建独立 note。

## API 设计

保留现有 `/api/v1/attachments` 作为低层“只上传文件”的接口。

新增高层导入接口：

```text
POST /api/v1/imports
```

用途：

- 上传 PDF/DOCX 并创建独立 note。
- 上传图片并按用户选择创建独立 note 或返回待挂载 attachment。

新增 note 附件接口：

```text
POST /api/v1/notes/{file_id}/attachments
```

用途：

- 上传或关联图片到已有 note。
- 可选择是否插入 Markdown 图片引用。
- 完成后重新索引该 note。

可选新增单篇索引接口：

```text
POST /api/v1/notes/{file_id}/index
```

用途：

- 对单篇 note 重建 FTS 和向量索引。
- 作为导入失败恢复和手动修复入口。

## CLI 设计

新增：

```bash
kb import ./paper.pdf --category document --tags ai,paper
kb import ./error.png --as-note --category troubleshooting
kb attach notes/troubleshooting/login-bug.md ./screenshot.png
```

CLI 应覆盖基本导入和挂载，不需要承担复杂管理交互。更细的整理工作由 Web UI 完成。

## Web UI 设计

新增“导入资料”入口，可放在 Quick Actions 或主导航中。

交互分两步：

1. 选择文件并上传。
2. 如果是图片，选择用途：
   - 作为独立知识。
   - 挂到已有笔记。

导入完成后跳转到 note detail，用户可以整理：

- 标题
- 分类
- 标签
- 描述
- 正文
- 附件关系

Web UI 需要展示导入状态：

- 原件已保存。
- 已解析。
- 已创建 note。
- 已完成全文索引。
- 已完成语义索引。
- 失败阶段和错误原因。

## MCP / Claude / Codex 设计

MCP 在本阶段保持轻量，不作为主产品入口。

保留最低可用能力：

- `kb_search`
- `kb_hybrid_search`
- `kb_read`
- `kb_save`
- `kb_rag_query`

后续可选增加：

- `kb_import_file`
- `kb_attach_file`

限制：

- 不让 Agent 默认自动批量导入本地文件。
- 导入类 MCP 工具需要明确文件路径和用户意图。
- 基础 `kb_search` 和 `kb_read` 不应依赖 embedding 或 LLM 初始化成功。

## 错误处理与状态

导入链路建议用阶段状态表达：

- `stored`: 原件已保存。
- `parsed`: 已转换成 Markdown 或图片引用内容。
- `ingested`: 已创建或更新 note。
- `indexed`: FTS 和向量索引都已更新。
- `failed`: 失败，并记录失败阶段和原因。

失败策略：

- 解析失败时保留 attachment，不丢文件。
- 向量索引失败时保留 note，并标记语义索引待重建。
- FTS 或数据库写入失败时返回操作失败，不创建半残缺 note。
- MarkItDown 失败时 fallback 到现有 parser；fallback 也失败时记录 parser failure。

## 测试策略

优先补这些测试：

- `IngestRequest` 完整保留 `source_path`、`content_type`、`attachments` 和 parser metadata。
- 文档导入保存原件、创建 note、写 DB、更新 FTS、更新向量。
- 图片作为独立知识会生成 note 和 Markdown 图片引用。
- 图片挂到已有 note 会更新 frontmatter attachments 和正文。
- 导入后 `kb_search` 能搜到。
- 导入后 `kb_hybrid_search` 能搜到。
- RAG 返回 sources，不再返回空 sources。
- parser 失败时 attachment 不丢失，返回明确阶段状态。
- MCP 基础搜索和读取在 embedding/LLM 不可用时仍可用。

## 阶段拆分

### Phase 1: 可靠入库主干

目标是先消除当前链路断点。

范围：

- 扩展 `IngestRequest` 元数据字段。
- 让 `ingest()` 写入 source_path、content_type、attachments 和 parser metadata。
- 新增单篇向量索引更新能力。
- 保存、导入、编辑后保持 FTS 与 LanceDB 一致。
- RAG 返回来源引用。

### Phase 2: 文档和图片导入闭环

目标是让个人知识库真正能吸收文档和截图。

范围：

- 新增 import service。
- 新增 `/api/v1/imports`。
- 新增 CLI `kb import` 和 `kb attach`。
- PDF/DOCX 通过 MarkItDown 或 fallback parser 转 Markdown。
- 图片支持独立 note 和挂载到已有 note。
- attachments 与 note 关系稳定落盘。

### Phase 3: 管理体验和插件增强

目标是提升可见性、整理效率和 Agent 辅助能力。

范围：

- Web 导入 UI。
- 导入状态展示。
- 单篇索引重建入口。
- MCP 可选增加 `kb_import_file` 和 `kb_attach_file`。
- 图片 OCR/caption。
- MarkItDown 扩展到 PPTX、XLSX、HTML 等格式。

## 设计原则

- attachments 存原件，note 存知识，index 存可检索状态。
- Web/CLI 是个人知识库主入口，MCP 是辅助入口。
- 所有创建和导入都走统一 ingest 主干。
- 导入失败不丢原件。
- 搜索和 RAG 必须可追溯。
- 先打通单个资料导入闭环，再扩展批量和更多格式。
