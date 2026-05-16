# Ingest Pipeline: 统一笔记入口管道

## 目标

在所有笔记创建入口（CLI、MCP、API、watch_dir）之上建立统一的 `ingest()` 入口函数，确保元数据完整性和来源可扩展性。

## 背景

当前四条数据入口各自处理，存在碎片化问题：

- `kb add` CLI — 调 `services.create_note()`，刚补上 source_project
- `kb_save` MCP — 参数完整，但直接调 `services.create_note()`
- `kb_add` MCP — 缺少 source_project、source_context
- `kb serve` watch_dir — 走 `index_files()` 批量同步，元数据注入在 indexer 里
- API `POST /notes` — 直接调 `services.create_note()`

后续要在管道中加入即时 embedding、内容校验、hooks 等能力，分散的入口会增加改造成本。

## 设计

### 架构

```
CLI / MCP / API / watch_dir
        │
        ▼  各自组装 IngestRequest
        │
   ┌────┴─────────────────────┐
   │      ingest()             │
   │  校验 → 默认值 → 写入     │
   └──────────────────────────┘
        │
        ▼
  services.create_note()
  (slug → file → DB upsert)
        │
        ▼
  notes/ + FTS5 + LanceDB
```

### IngestRequest 数据模型

```python
@dataclass(frozen=True)
class IngestRequest:
    title: str
    content: str
    source_project: str          # 必填
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    description: str | None = None
    source_context: str | None = None
```

放在 `src/kb/core/models.py`。

### 配置扩展

`config.toml` 的每个 source 新增两个可选字段：

```toml
[sources.blog]
label = "博客"
default_category = "未分类"    # 新
auto_tags = []                 # 新
```

`SourceConfig` frozen dataclass 增加 `default_category: str | None = None` 和 `auto_tags: list[str] = field(default_factory=list)`。

### ingest() 函数

签名：
```python
def ingest(
    request: IngestRequest,
    vault: Path,
    db: Database,
    *,
    source_config: SourceConfig | None = None,
) -> Note:
```

逻辑流程：
1. 参数校验：title/content 非空，source_project 在 config.sources 中存在
2. 加载 source_config（未传入时从 config 读取）
3. 补全默认值：category 为空时用 default_category
4. 合并标签：用户传入的 tags + source.auto_tags
5. 调用 `services.create_note()` 写文件 + 入库
6. 返回 Note

新文件：`src/kb/core/ingest.py`。

### 各渠道改动

| 渠道 | 改动 |
|------|------|
| `kb save` MCP | 不改参数，内部改调 ingest() |
| `kb add` MCP | 加 source_project（默认"manual"）、source_context 参数，改调 ingest() |
| `kb add` CLI | 加 --source-context 参数，改调 ingest() |
| API routes | POST /notes（两处）改调 ingest() |
| watch_dir | indexer 同步时用 IngestRequest 补元数据，流程不变 |

### 测试计划

- **test_ingest_validation**: 空 title/content/非法 source_project → ValueError
- **test_ingest_defaults**: category 为空时应用 default_category，auto_tags 自动追加
- **test_ingest_merges_tags**: 用户 tags 与 auto_tags 不重复合并
- **test_ingest_creates_note**: 标准输入产生正确 Note
- **test_ingest_new_source**: config.toml 新增来源后 ingest 正常工作
- **test_cli_add_passes_to_ingest**: CLI add 组装正确的 IngestRequest
- **test_mcp_add_has_source_project**: MCP kb_add 的 source_project 参数生效
- **test_api_create_uses_ingest**: API 创建笔记经过 ingest 校验

### 扩展性

新增来源只需两步，零代码改动：
1. config.toml 加 `[sources.xxx]` 段，声明 label、default_category、auto_tags
2. 集成代码调用 `ingest(IngestRequest(source_project="xxx", ...), ...)`

### 不在本轮范围

- 即时 embedding（后续在 ingest() 步骤 4.5 加入）
- 内容质量门禁（重复检测、格式校验）
- ingest 前后 hooks
- services.create_note() 签名重构
