# KB 统一可视化管理 Dashboard 设计

**日期:** 2026-05-14
**状态:** 已确认
**前置:** [2026-05-10-kb-dashboard-design.md](./2026-05-10-kb-dashboard-design.md), [2026-05-13-kb-multi-source-design.md](./2026-05-13-kb-multi-source-design.md)

---

## 目标

在现有 Dashboard 基础上加入 multi-source 维度的可视化，新增 /manage 深度管理页，让用户一站式掌握知识库全貌：知识类型分布、来源项目、内容格式、索引健康度。

---

## 范围

| 板块 | 内容 | 本 spec |
|------|------|---------|
| Dashboard 增强 | 统计卡片扩展（+知识类型）、类型柱状图、来源/索引/格式面板、快捷操作 | ✓ |
| /manage 管理页 | Tab 切换 5 个维度（类型/分类/标签/来源/索引）+ 快速跳转 | ✓ |
| /manage 分类/标签/来源 Tab | 对应维度的明细视图 | ✓ |
| /manage 索引 Tab | 向量统计、索引日志、重建操作 | 本 spec 只做基础版（统计+重建按钮） |

---

## 路由变更

| 路由 | 组件 | 说明 |
|------|------|------|
| `/` | DashboardPage | 增强版：5 统计卡片 + 类型柱状图 + 面板 + 快捷操作 |
| `/manage` | ManagePage | **新建**，Tab 切换 5 个维度的深度视图 |
| `/notes` | NoteList | 不变 |

侧边栏导航新增 `{ to: '/manage', label: 'Manage', icon: '📊' }`。

---

## 后端 API

### 新建：`GET /api/type-distribution`

返回各 entry_type 的笔记数量及中文标签。

```
响应: {
  "types": [
    {"name": "tech-article", "count": 12, "label": "技术文章"},
    {"name": "document", "count": 7, "label": "文档摘要"},
    {"name": "troubleshooting", "count": 3, "label": "踩坑记录"},
    {"name": "design-decision", "count": 1, "label": "设计决策"},
    {"name": "code-snippet", "count": 1, "label": "代码片段"}
  ]
}
```

实现：Database 新增 `count_notes_by_entry_type()`，聚合 `SELECT entry_type, COUNT(*) FROM notes WHERE status='published' GROUP BY entry_type`，label 从 config.toml `[kb_types.*]` 读取。

### 新建：`GET /api/source-projects`

返回各 source_project 的笔记数量。

```
响应: {
  "projects": [
    {"name": "kb", "count": 24}
  ]
}
```

实现：Database 新增 `list_source_projects()`，聚合 `SELECT source_project, COUNT(*) FROM notes WHERE status='published' AND source_project IS NOT NULL GROUP BY source_project`。

### 新建：`GET /api/content-type-stats`

返回各 content_type 的笔记数量。

```
响应: {
  "content_types": [
    {"name": "markdown", "count": 24},
    {"name": "pdf", "count": 0},
    {"name": "docx", "count": 0}
  ]
}
```

实现：Database 新增 `count_notes_by_content_type()`。

### 新建：`GET /api/index-health`

返回索引健康度指标。

```
响应: {
  "notes_count": 24,
  "vectors_count": 53,
  "coverage": 1.0
}
```

实现：`notes_count` 从 `get_all_hashes()` 取长度，`vectors_count` 从 vector_store 取表行数，`coverage` 简化计算为向量数 > 0 时取 1.0，否则 0。

### Database 新增方法 (`src/kb/data/database.py`)

```python
def count_notes_by_entry_type(self) -> list[dict]:
    """Return [{entry_type, count}] for all published notes."""

def list_source_projects(self) -> list[dict]:
    """Return [{source_project, count}] for all published notes."""

def count_notes_by_content_type(self) -> list[dict]:
    """Return [{content_type, count}] for all published notes."""
```

---

## 前端

### api.ts 改动

**Note 接口扩展：**

```typescript
export interface Note {
  file_id: string
  title: string
  description: string | null
  content: string
  category: string | null
  tags: string[]
  attachments: string[]
  created_at: string | null
  updated_at: string | null
  status: string
  // 新增字段
  entry_type: string | null
  source_project: string | null
  source_path: string | null
  source_context: string | null
  content_type: string
}
```

**新增 API 方法：**

```typescript
getTypeDistribution() {
  return request<{ types: Array<{ name: string; count: number; label: string }> }>('/type-distribution')
},

getSourceProjects() {
  return request<{ projects: Array<{ name: string; count: number }> }>('/source-projects')
},

getContentTypeStats() {
  return request<{ content_types: Array<{ name: string; count: number }> }>('/content-type-stats')
},

getIndexHealth() {
  return request<{ notes_count: number; vectors_count: number; coverage: number }>('/index-health')
},
```

### DashboardPage.vue 增强

布局从 4 卡片 + 分类列表 + 标签云 + 最近更新，变为 5 卡片 + 类型柱状图 + 右侧面板（索引健康度/来源项目/内容格式饼图）+ 快捷操作 + 最近更新（带 type badge）。

数据获取：在原有 5 个 API 调用基础上增加 4 个，共 9 个并行请求。

### ManagePage.vue 新建

5 个 Tab：按类型 / 按分类 / 按标签 / 按来源 / 索引

**按类型 Tab（默认）：** 5 张类型明细卡片，每张显示：类型 key、中文名、数量、关联标签。点击卡片跳转 `/notes?entry_type=xxx`。
右侧面板：其他 Tab 预览 + 快速跳转按钮（新建技术文章、记录踩坑、全量重建索引）。

**按分类 Tab：** 复用现有 CategoryList，增强显示每个分类下的类型分布。

**按标签 Tab：** 复用现有 TagCloud，增强显示每个标签关联的笔记数和类型。

**按来源 Tab：** 来源项目卡片列表，显示项目名、笔记数、包含的知识类型。

**索引 Tab：** 索引健康度仪表盘（大百分比 + 进度条）、向量/文件统计数字、重建索引按钮。

### 组件树

```
DashboardPage.vue              # 增强
  ├── StatCard.vue              # 不变（新增一个 type 卡片实例）
  ├── TypeDistribution.vue      # 新建，柱状图（纯 CSS）
  ├── IndexHealth.vue           # 新建，索引健康度面板
  ├── SourceProjects.vue        # 新建，来源项目列表
  ├── ContentFormatPie.vue      # 新建，内容格式饼图（CSS conic-gradient）
  ├── QuickActions.vue          # 新建，快捷操作按钮组
  └── RecentNotes.vue           # 增强，每行显示 type badge

ManagePage.vue                 # 新建
  ├── TypeTab.vue               # 新建，按类型明细卡片
  ├── CategoryTab.vue           # 复用 CategoryList 增强
  ├── TagTab.vue                # 复用 TagCloud 增强
  ├── SourceTab.vue             # 新建，来源项目明细
  └── IndexTab.vue              # 新建，索引仪表盘
```

### 交互

- 类型柱状图 bar 点击 → 跳转 `/notes?entry_type=xxx`
- 来源项目行点击 → 跳转 `/notes?source_project=xxx`
- 快捷操作按钮 → 跳转对应页面或触发 API
- ManagePage Tab 切换 → 本地状态切换，不刷路由
- 类型明细卡片点击 → 跳转 `/notes?entry_type=xxx`
- 最近更新每行显示 type badge（5 种类型各一种颜色）

### 样式

复用现有设计系统，无新增 CSS 依赖：
- 柱状图：纯 CSS div + gradient 实现，不引入图表库
- 饼图：CSS `conic-gradient` 实现
- Type badge：5 种类型各一种颜色（blue/green/amber/pink/purple）
- Tab：复用 `.btn` / `.btn-ghost` 样式
- 进度条：纯 CSS div + background

---

## 测试

| 层 | 内容 |
|----|------|
| 后端 | `test_type_distribution`、`test_source_projects`、`test_content_type_stats`、`test_index_health` |
| 前端 | DashboardPage 新卡片/图表渲染、ManagePage Tab 切换、链接指向正确路由 |

---

## 文件清单

| 操作 | 文件 |
|------|------|
| 修改 | `src/kb/data/database.py`（3 个新方法） |
| 修改 | `src/kb/routes.py`（4 个新端点） |
| 新建 | `web/src/pages/ManagePage.vue` |
| 修改 | `web/src/pages/DashboardPage.vue` |
| 新建 | `web/src/components/TypeDistribution.vue` |
| 新建 | `web/src/components/IndexHealth.vue` |
| 新建 | `web/src/components/SourceProjects.vue` |
| 新建 | `web/src/components/ContentFormatPie.vue` |
| 新建 | `web/src/components/QuickActions.vue` |
| 修改 | `web/src/components/RecentNotes.vue` |
| 修改 | `web/src/App.vue`（导航 + 路由） |
| 修改 | `web/src/main.ts`（路由注册） |
| 修改 | `web/src/api.ts`（Note 接口 + 4 个新方法） |
| 新建 | `tests/test_dashboard_enhanced.py` |
