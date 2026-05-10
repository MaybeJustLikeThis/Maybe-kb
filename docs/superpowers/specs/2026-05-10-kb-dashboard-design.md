# KB 总览页面（Dashboard）设计

**日期:** 2026-05-10
**状态:** 已确认

---

## 目标

为 Web UI 新增总览页面作为首页，一站式展示知识库整体状况：统计数字、分类/标签分布、最近更新。

---

## 范围

本 spec 覆盖三个板块中的前两个（第三个评测/运维板块后续迭代）：

| 板块 | 内容 | 本 spec |
|------|------|---------|
| 一：统计卡片 | 笔记总数、分类数、标签数、附件数 | ✓ |
| 二：分布 + 导航 | 分类分布（含数量）、标签云、最近更新，可点击跳转 | ✓ |
| 三：评测/运维 | 评测分数趋势、LLM 配置状态 | 后续 |

---

## 路由变更

| 原来 | 改为 | 说明 |
|------|------|------|
| `/` → NoteList | `/` → DashboardPage | 总览页替换笔记列表为首页 |
| — | `/notes` → NoteList | 笔记列表移到新路由 |

侧边栏导航新增"Overview (🏠)"项，放在最上方。

---

## 后端 API

### 新建：`GET /api/attachments/stats`

返回附件目录下文件总数。

```
响应: { "count": 3 }
```

实现：遍历 `attachments/` 目录，统计文件数（不含子目录）。

### 增强：`GET /api/categories?with_count=true`

在原有分类名列表基础上，可选返回每个分类下的笔记数量。

```
GET /api/categories              → { "categories": ["tech", "projects"] }
GET /api/categories?with_count=1  → { "categories": [{"name": "tech", "count": 12}, ...] }
```

### 增强：`GET /api/notes?sort=updated_at_desc&limit=5`

新增 `sort` 参数，支持 `updated_at_desc` 按更新时间倒序排列，用于"最近更新"列表。

---

## 前端

### 页面布局

```
┌──────────────────────────────────────────────────────────┐
│  Overview                                                │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 📄 N     │ │ 📁 N     │ │ 🏷  N    │ │ 📎 N     │   │
│  │ Notes    │ │ Categori │ │ Tags     │ │ Attachme │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                          │
│  ┌──────────────────────┐ ┌──────────────────────┐      │
│  │ CATEGORIES           │ │ TAGS                 │      │
│  │ tech        12 篇 → │ │ python docker async  │      │
│  │ projects     5 篇 → │ │ rust typescript      │      │
│  │ daily        3 篇 → │ │ react css vue      │      │
│  └──────────────────────┘ └──────────────────────┘      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ RECENT UPDATES                                    │   │
│  │ 笔记标题          分类       更新时间              │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 组件树

```
DashboardPage.vue          # 新建, 总览页容器
  ├── StatCard.vue          # 新建, 统计卡片（接收 icon/value/label props）
  ├── CategoryList.vue      # 新建, 分类分布列表（点击跳转 /notes?category=X）
  ├── TagCloud.vue          # 新建, 标签云（点击跳转 /notes?tag=X）
  └── RecentNotes.vue       # 新建, 最近更新列表（点击进入笔记详情）
```

### 数据流

```
DashboardPage.onMounted()
  ├── Promise.all([
  │     api.getIndexStatus(),           // { notes_count }
  │     api.getAttachmentsStats(),      // { count }
  │     api.getCategories(true),        // { categories: [{ name, count }] }
  │     api.getTags(),                  // { tags: [...] }
  │     api.listNotes({ sort: 'updated_at_desc', limit: 5 })
  │   ])
  ├── 统计卡片: notes_count / categories.length / tags.length / count
  ├── 分类列表: categories 数组渲染
  ├── 标签云: tags 数组渲染为 badge
  └── 最近更新: notes 前 5 条渲染为链接列表
```

### 交互

- 分类行点击 → 跳转 `/notes?category={name}`
- 标签 badge 点击 → 跳转 `/notes?tag={name}`
- 最近更新行点击 → 跳转 `/note/{file_id}`
- 卡片 hover → 边框变色、轻微阴影

### 样式

复用现有设计系统，无新增 CSS 文件或依赖：
- 统计卡片：`.card` 类
- 标签：`.badge` + `.badge-muted` / `.badge-primary`
- 标题：`.section-heading`
- 按钮：`.btn`、`.btn-ghost`
- 空状态：`.empty-state`

### API 函数新增（api.ts）

```typescript
getAttachmentsStats() {
  return request<{ count: number }>('/attachments/stats')
},

getCategoriesWithCount() {
  return request<{ categories: Array<{ name: string; count: number }> }>('/categories?with_count=1')
},
```

### 路由注册（main.ts）

```typescript
import DashboardPage from './pages/DashboardPage.vue'

const routes = [
  { path: '/', component: DashboardPage },
  { path: '/notes', component: NoteList },
  { path: '/note/:fileId', component: NoteDetail, props: true },
  { path: '/search', component: SearchPage },
  { path: '/chat', component: ChatPage },
]
```

### 导航更新（App.vue）

```typescript
const navItems = [
  { to: '/', label: 'Overview', icon: '🏠' },
  { to: '/notes', label: 'Notes', icon: '📄' },
  { to: '/search', label: 'Search', icon: '🔍' },
  { to: '/chat', label: 'Chat', icon: '💬' },
]
```

---

## 测试

| 层 | 内容 |
|----|------|
| 后端 | `test_attachments_stats`（新建接口返回 count）、`test_categories_with_count`（with_count 返回带数量的结构） |
| 前端 | DashboardPage 组件渲染测试：统计卡片显示正确数值、分类列表/标签云渲染、链接指向正确路由 |

---

## 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `web/src/pages/DashboardPage.vue` |
| 新建 | `web/src/components/StatCard.vue` |
| 新建 | `web/src/components/CategoryList.vue` |
| 新建 | `web/src/components/TagCloud.vue` |
| 新建 | `web/src/components/RecentNotes.vue` |
| 修改 | `web/src/main.ts`（路由） |
| 修改 | `web/src/App.vue`（导航） |
| 修改 | `web/src/api.ts`（两个新函数） |
| 修改 | `src/kb/routes.py`（一个新接口 + 一个增强 + 一个增强） |
| 新建 | `tests/test_dashboard.py`（后端 API 测试） |
