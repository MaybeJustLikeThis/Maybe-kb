# MarkItDown 集成设计

> 日期：2026-06-07
> 状态：待实现
> 取代：`2026-06-02-knowledge-import-indexing-design.md` 中的 Phase 2/3 MarkItDown 部分

---

## 背景与动机

kb 是一个以 Markdown 为唯一真相源的本地知识库。现有 `ParserRegistry` 注册了 PDF/DOCX/Image parser，但 indexer 只处理 `.md` 文件——非 MD parser 从未接入索引管线。

Microsoft [markitdown](https://github.com/microsoft/markitdown) 能将 PDF、DOCX、PPTX、XLSX、CSV、HTML、EPUB 等格式高质量转换为结构化 Markdown（保留标题、列表、表格、链接）。

引入 Obsidian 作为主要编辑界面后，kb 的定位进一步明确为"机器侧的知识引擎"，不需要自建编辑 UI。这简化了导入方案——导入的终点就是"让文件变成 vault 里的 .md"，Obsidian 负责后续的浏览和编辑。

### 原设计文档的重新审视

`2026-06-02-knowledge-import-indexing-design.md` 规划了三阶段导入管线，但 vault 实际状态与之差距较大：

| 设计假设 | 实际情况 |
|---------|---------|
| 需要导入大量 PDF/DOCX/PPTX | attachments/ 里零个非图片文件 |
| Phase 1 的 `content_type`、`source_path`、`parser` 字段 | 零个文件使用了这些字段 |
| 需要独立 ImportService + ImportRequest 抽象 | 59 篇笔记，全是 `.md` |
| 需要导入状态追踪、批量导入队列 | 个人知识库规模，不需要 |

基于此，本设计大幅简化原方案：不建 ImportService 类，不做 Phase 1 的细粒度 metadata 扩展，用一个 `import_file()` 函数 + markitdown 直接解决问题。

---

## 核心决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 转换器 | markitdown 唯一 | 一个库覆盖所有格式，避免维护多套 parser |
| 现有 parser | 删除 PDFParser (PyMuPDF)、DocxParser (python-docx)、ImageParser | 从未真正使用，markitdown 完全替代 |
| Fallback | 无，markitdown 失败直接报错 | 简化代码路径，不维护 fallback 链 |
| 导入抽象 | `import_file()` 函数 | 不建 ImportService 类，不引入新抽象层级 |
| 元数据 | `source_project: "imported"` + `source_file: 原始文件名` | 复用现有字段，够用于区分来源 |
| 原始文件 | 存入 `attachments/`，通过 `source_file` 关联 | 保留原始文件，方便后续重新转换 |
| Phase 1 遗留 | Phase 1 的 `source_path`/`content_type`/`attachments`/`extra_frontmatter` **已在 `IngestRequest` 中实现**，直接复用。通过 `extra_frontmatter` 写入 `source_file: 原始文件名`，不需要新增字段 |
| watcher | 不变，继续只监听 `.md` 变更 | 非 .md 文件的导入是显式操作，不需要自动触发 |

---

## 架构与数据流

```
用户操作                    kb 内部
─────────                  ────────
kb import paper.pdf
                           1. AttachmentStore.store(paper.pdf)
                              → attachments/YYYY/MM/{hash}.pdf
                           2. MarkItDown.convert(paper.pdf)
                              → Markdown 文本
                           3. 组装 IngestRequest（字段均已存在）:
                              title: "paper" (文件名去扩展名)
                              content: 转换后的 Markdown
                              source_project: "imported"
                              content_type: "pdf" (原始文件扩展名)
                              source_path: "attachments/YYYY/MM/{hash}.pdf"
                              attachments: ["attachments/YYYY/MM/{hash}.pdf"]
                              extra_frontmatter: {"source_file": "paper.pdf"}
                           4. ingest(req) → 现有管线
                              → 写 notes/{category}/{slug}.md
                              → FTS5 索引
                              → 向量嵌入（best-effort）
                           5. 返回结果（成功/失败 + 笔记路径）

kb import paper.pdf --title "论文标题" --category "AI"
                           同上，但 title/category 覆盖默认值
```

### 转换失败处理

- markitdown 抛异常 → 原始文件已存入 attachments/，报错返回文件路径，用户可手动处理
- 转换结果为空文本 → 同上，报错提示"文件内容为空或无法提取"
- 两种情况都不产生笔记文件，不进入索引

### 新增模块

- `src/kb/parsers/markitdown_converter.py` — 封装 `MarkItDown().convert(path)` → `ParsedContent`
  - 处理 markitdown 未安装的情况（import 时检查，给出安装提示）
  - 处理 markitdown 转换异常（捕获、包装、向上抛出）
  - 返回 `ParsedContent(text=转换后的 Markdown, metadata={"converter": "markitdown", "source_file": 原始文件名})`

### 删除模块

- `src/kb/parsers/pdf.py`
- `src/kb/parsers/docx.py`
- `src/kb/parsers/image.py`
- `ParserRegistry` 中对上述三个 parser 的注册逻辑
- `pyproject.toml` 中 `PyMuPDF`、`python-docx` 依赖（如有）

### 不变模块

- `src/kb/core/parsers.py` — `ParsedContent` dataclass 和 `ParserRegistry` 本身保留，`MarkdownParser` 保留
- `src/kb/core/watcher.py` — 继续只监听 `.md`
- `src/kb/core/indexer.py` — 现有索引逻辑不变
- `src/kb/core/ingest.py` — 现有 ingest 管线不变
- `src/kb/core/models.py` — `IngestRequest` 已有所需全部字段（`source_path`、`content_type`、`attachments`、`extra_frontmatter`），无需修改
- `src/kb/core/services.py` — `create_note()` 已支持写入 `extra_frontmatter` 到 YAML frontmatter，无需修改

---

## 接口设计

### CLI

```
kb import <file_path> [--title "..."] [--category "..."] [--tags "a,b"]
```

- 支持单文件导入
- `--title`：默认取文件名去扩展名
- `--category`：默认 "未分类"
- `--tags`：逗号分隔，默认无
- 输出：导入成功后的笔记路径 + 附件路径
- markitdown 未安装时：提示 `pip install 'kb[markitdown]'`

### API

```
POST /api/v1/import
  Content-Type: multipart/form-data
  file: <binary>           # 必填
  title: string            # 可选，默认文件名去扩展名
  category: string         # 可选，默认 "未分类"
  tags: string             # 可选，逗号分隔
```

- 文件上传 → 临时存储 → markitdown 转换 → ingest → 返回结果
- 返回：`{ success: true, file_id, title, category, source_file, attachment_path }`
- 失败：`{ success: false, error: "转换失败: ...", attachment_path: "..." }`
- `source_project` 固定为 `"imported"`；若 `config.toml` 无 `[sources.imported]` section，`ingest()` 使用默认值（default_category="未分类"，auto_tags=[]）

### MCP

**不做。** 当前 kb MCP 工具面向 Claude Code 的笔记读写场景，文件导入不是 agent 的典型操作。

### Web UI

**不做。** Obsidian 接管编辑界面，Web UI 不需要文件上传入口。

---

## 不在范围内

- 批量导入（一次一个文件，不做目录扫描批量转换）
- 导入历史/状态追踪
- 转换失败重试队列
- `kb attach`（把文件附加到已有笔记）
- 图片 OCR/caption（markitdown 支持但需要 OpenAI API，以后再说）
- 音频/视频转录（markitdown 支持但依赖重，以后再说）

---

## 依赖管理

```toml
# pyproject.toml
[project.optional-dependencies]
markitdown = ["markitdown[all]"]

# 或更精细（按需启用格式）：
pdf = ["markitdown[pdf]"]
docx = ["markitdown[docx]"]
xlsx = ["markitdown[xlsx]"]
```

用户 `pip install 'kb[markitdown]'` 启用全格式支持。不装时 kb 正常运行，`kb import` 命令给出安装提示。

---

## 支持格式

由 markitdown 决定，kb 不做格式白名单限制：

| 格式 | 扩展名 | 备注 |
|------|--------|------|
| PDF | `.pdf` | 用户明确需要 |
| Word | `.docx` | 用户明确需要 |
| CSV | `.csv` | 用户明确需要 |
| PowerPoint | `.pptx` | markitdown 天然支持 |
| Excel | `.xlsx` | markitdown 天然支持 |
| HTML | `.html`, `.htm` | markitdown 天然支持 |
| EPUB | `.epub` | markitdown 天然支持 |
| 纯文本 | `.txt`, `.json`, `.xml` | markitdown 天然支持 |
| ZIP | `.zip` | markitdown 天然支持（解压后逐个转换） |

---

## 测试策略

- 单元测试：`markitdown_converter.py` 的转换逻辑（mock markitdown 返回值）
- 单元测试：`import_file()` 函数（mock converter + ingest，验证 IngestRequest 组装正确）
- 集成测试：CLI `kb import` 命令（使用小型 PDF/DOCX fixture 文件）
- 集成测试：API `POST /api/v1/import` endpoint
- 边界测试：markitdown 未安装、转换异常、空文本结果、不支持的格式
