# Dashboard 总览页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Web UI 新增总览页面作为首页，展示统计卡片、分类/标签分布、最近更新，附带后端 API 增强。

**Architecture:** 5 个任务。Task 1 完成后端变更（database 方法 + routes 增强），Task 2 补充前端 API 函数，Task 3 实现 4 个子组件，Task 4 组装 DashboardPage 并更新路由/导航，Task 5 终验。

**Tech Stack:** Python 3.13, FastAPI, Vue 3 + TypeScript, Tailwind CSS

---

## File Structure

```
New files:
  web/src/pages/DashboardPage.vue       # 总览页容器
  web/src/components/StatCard.vue       # 统计卡片组件
  web/src/components/CategoryList.vue   # 分类分布列表组件
  web/src/components/TagCloud.vue       # 标签云组件
  web/src/components/RecentNotes.vue    # 最近更新列表组件
  tests/test_dashboard.py               # 后端 API 测试

Modified files:
  src/kb/data/database.py               # 新增 count_notes_by_category()
  src/kb/routes.py                       # 新增 attachments/stats, 增强 categories + notes
  web/src/api.ts                         # 新增 getAttachmentsStats, getCategoriesWithCount
  web/src/main.ts                        # 路由变更 + DashboardPage 导入
  web/src/App.vue                        # 导航新增 Overview
```

---

### Task 1: 后端 API — 新建 attachments/stats，增强 categories 和 notes

**Files:**
- Modify: `src/kb/data/database.py:245-252`
- Modify: `src/kb/routes.py:66-73, 180-186, 200-202`
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: 写测试**

```python
"""Tests for dashboard API endpoints."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from kb.core.context import AppContext


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    (tmp_path / "notes").mkdir()
    (tmp_path / "attachments").mkdir()
    (tmp_path / "attachments" / "img.png").write_bytes(b"fake")
    (tmp_path / "attachments" / "doc.pdf").write_bytes(b"fake")
    (tmp_path / ".kb").mkdir()
    ctx = AppContext.from_config(_fake_config(), vault=tmp_path,
                                 with_embedding=False, with_llm=False)

    from kb.core.models import Note

    note1 = Note(
        file_id="notes/tech/docker.md", title="Docker 基础",
        content="Docker 是一个容器化平台。", category="tech",
        tags=["docker", "container"], status="published",
        file_hash="abc123",
    )
    note2 = Note(
        file_id="notes/life/reading.md", title="阅读习惯",
        content="每天阅读一小时。", category="life",
        tags=["reading", "life"], status="published",
        file_hash="def456",
    )
    ctx.db.upsert_note(note1)
    ctx.db.upsert_note(note2)

    from kb.routes import create_api_router
    client = TestClient(create_api_router(ctx))
    return tmp_path, client


def _fake_config():
    from kb.core.config import KBConfig, GeneralConfig, SearchConfig, EmbeddingConfig, LLMConfig, RAGConfig, ServerConfig
    return KBConfig(
        general=GeneralConfig(vault_path="."),
        search=SearchConfig(max_results=20),
        embedding=EmbeddingConfig(provider="local", model="BAAI/bge-small-zh-v1.5"),
        llm=LLMConfig(provider="ollama", model="qwen2.5:7b"),
        rag=RAGConfig(top_k=5),
        server=ServerConfig(host="127.0.0.1", port=8420),
    )


def test_get_attachments_stats(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/attachments/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert data["count"] >= 1


def test_get_categories_with_count(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/categories?with_count=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert isinstance(data["categories"], list)
    for item in data["categories"]:
        assert "name" in item
        assert "count" in item
        assert isinstance(item["count"], int)


def test_get_categories_without_count(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert isinstance(data["categories"], list)
    if data["categories"]:
        assert isinstance(data["categories"][0], str)


def test_list_notes_sort(tmp_vault):
    tmp_path, client = tmp_vault
    resp = client.get("/api/notes?limit=5")
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/c/Users/cherry/AppData/Local/Programs/Python/Python313/python.exe -m pytest tests/test_dashboard.py -v`
Expected: 部分测试 FAIL（`GET /api/attachments/stats` 返回 404，`with_count` 不识别）

- [ ] **Step 3: 在 database.py 添加 count_notes_by_category 方法**

```python
def count_notes_by_category(self, category: str) -> int:
    """Return the number of notes in a category."""
    conn = self._connect()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM notes WHERE category = ? AND status = 'published'",
        (category,),
    ).fetchone()
    return row["cnt"]
```

在 `list_all_categories` 方法后面（第 252 行之后）插入。

- [ ] **Step 4: 修改 routes.py — 增强 GET /api/categories**

将第 184-186 行的：

```python
@router.get("/categories")
def get_categories():
    return {"categories": ctx.db.list_all_categories()}
```

替换为：

```python
@router.get("/categories")
def get_categories(with_count: bool = Query(False)):
    cats = ctx.db.list_all_categories()
    if not with_count:
        return {"categories": cats}
    return {
        "categories": [
            {"name": c, "count": ctx.db.count_notes_by_category(c)}
            for c in cats
        ]
    }
```

- [ ] **Step 5: 修改 routes.py — 新增 GET /api/attachments/stats**

在第 200 行（`/index` endpoint 之后）插入：

```python
@router.get("/attachments/stats")
def get_attachments_stats():
    att_dir = vault_path / "attachments"
    if not att_dir.is_dir():
        return {"count": 0}
    count = sum(1 for f in att_dir.iterdir() if f.is_file())
    return {"count": count}
```

- [ ] **Step 6: 修改 routes.py — 增强 GET /api/notes 支持 sort**

将第 66-73 行的：

```python
@router.get("/notes")
def list_notes(
    category: str | None = Query(None),
    tag: str | None = Query(None),
    limit: int = Query(50),
):
    rows = ctx.db.list_notes(category=category, tag=tag, limit=limit)
    return [note_row_to_dict(ctx.db, row) for row in rows]
```

替换为：

```python
@router.get("/notes")
def list_notes(
    category: str | None = Query(None),
    tag: str | None = Query(None),
    limit: int = Query(50),
    sort: str | None = Query(None),
):
    rows = ctx.db.list_notes(
        category=category, tag=tag, limit=limit, sort=sort,
    )
    return [note_row_to_dict(ctx.db, row) for row in rows]
```

- [ ] **Step 7: 修改 database.py — list_notes 支持 sort 参数**

将 `list_notes` 方法签名从：

```python
def list_notes(
    self,
    category: str | None = None,
    tag: str | None = None,
    status: str = "published",
    limit: int = 100,
) -> list[sqlite3.Row]:
```

改为：

```python
def list_notes(
    self,
    category: str | None = None,
    tag: str | None = None,
    status: str = "published",
    limit: int = 100,
    sort: str | None = None,
) -> list[sqlite3.Row]:
```

并将方法末尾的 `ORDER BY` 从：

```python
query += " ORDER BY n.updated_at DESC, n.created_at DESC LIMIT ?"
```

改为：

```python
if sort == "updated_at_desc":
    query += " ORDER BY n.updated_at DESC, n.created_at DESC LIMIT ?"
else:
    query += " ORDER BY n.updated_at DESC, n.created_at DESC LIMIT ?"
```

（默认排序已满足"最近更新"需求，`sort` 参数为未来的排序扩展预留接口。）

- [ ] **Step 8: 运行后端测试确认全绿**

Run: `/c/Users/cherry/AppData/Local/Programs/Python/Python313/python.exe -m pytest tests/test_dashboard.py -v`
Expected: 4 tests PASS

- [ ] **Step 9: 提交**

```bash
git add src/kb/data/database.py src/kb/routes.py tests/test_dashboard.py
git commit -m "feat: add attachments stats, categories with_count, notes sort for dashboard"
```

---

### Task 2: 前端 API 函数

**Files:**
- Modify: `web/src/api.ts`

- [ ] **Step 1: 在 api.ts 中添加两个新函数**

在 `api` 对象内，`chatAsk` 方法之前，添加：

```typescript
getAttachmentsStats() {
  return request<{ count: number }>('/attachments/stats')
},

getCategoriesWithCount() {
  return request<{ categories: Array<{ name: string; count: number }> }>('/categories?with_count=1')
},
```

- [ ] **Step 2: TypeScript 编译验证**

Run: `cd web && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: 无新增类型错误

- [ ] **Step 3: 提交**

```bash
git add web/src/api.ts
git commit -m "feat: add getAttachmentsStats and getCategoriesWithCount to API client"
```

---

### Task 3: 前端子组件

**Files:**
- Create: `web/src/components/StatCard.vue`
- Create: `web/src/components/CategoryList.vue`
- Create: `web/src/components/TagCloud.vue`
- Create: `web/src/components/RecentNotes.vue`

- [ ] **Step 1: 创建 StatCard.vue**

```vue
<template>
  <div class="card flex items-center gap-4 p-5">
    <span class="text-2xl">{{ icon }}</span>
    <div>
      <p class="text-2xl font-bold" style="color: var(--color-text);">{{ value }}</p>
      <p class="text-xs" style="color: var(--color-text-muted);">{{ label }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  value: number
  label: string
}>()
</script>
```

- [ ] **Step 2: 创建 CategoryList.vue**

```vue
<template>
  <div class="card">
    <h3 class="section-heading">Categories</h3>
    <div v-if="categories.length === 0" class="text-sm" style="color: var(--color-text-muted);">
      No categories yet.
    </div>
    <router-link
      v-for="cat in categories"
      :key="cat.name"
      :to="`/notes?category=${encodeURIComponent(cat.name)}`"
      class="flex items-center justify-between py-2 px-1 rounded-md text-sm transition-colors hover:bg-gray-50"
    >
      <span style="color: var(--color-text);">{{ cat.name }}</span>
      <span class="flex items-center gap-1" style="color: var(--color-text-muted);">
        {{ cat.count }} 篇
        <span class="text-xs">&rarr;</span>
      </span>
    </router-link>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  categories: Array<{ name: string; count: number }>
}>()
</script>
```

- [ ] **Step 3: 创建 TagCloud.vue**

```vue
<template>
  <div class="card">
    <h3 class="section-heading">Tags</h3>
    <div v-if="tags.length === 0" class="text-sm" style="color: var(--color-text-muted);">
      No tags yet.
    </div>
    <div v-else class="flex flex-wrap gap-1.5">
      <router-link
        v-for="tag in tags"
        :key="tag"
        :to="`/notes?tag=${encodeURIComponent(tag)}`"
        class="badge badge-muted hover:bg-gray-200 cursor-pointer transition-colors"
      >
        {{ tag }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  tags: string[]
}>()
</script>
```

- [ ] **Step 4: 创建 RecentNotes.vue**

```vue
<template>
  <div class="card">
    <h3 class="section-heading">Recent Updates</h3>
    <div v-if="notes.length === 0" class="empty-state">
      <div class="empty-state-icon">📝</div>
      <p>No notes yet.</p>
    </div>
    <ul v-else class="space-y-1">
      <li v-for="note in notes" :key="note.file_id">
        <router-link
          :to="`/note/${encodeURIComponent(note.file_id)}`"
          class="flex items-center justify-between py-2 px-1 rounded-md text-sm transition-colors hover:bg-gray-50"
        >
          <div class="flex items-center gap-3 min-w-0">
            <span class="truncate font-medium" style="color: var(--color-text);">{{ note.title }}</span>
            <span v-if="note.category" class="badge badge-primary flex-shrink-0">{{ note.category }}</span>
          </div>
          <span class="text-xs flex-shrink-0 ml-3" style="color: var(--color-text-muted);">
            {{ formatTime(note.updated_at || note.created_at) }}
          </span>
        </router-link>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { type Note } from '../api'

defineProps<{
  notes: Note[]
}>()

function formatTime(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}
</script>
```

- [ ] **Step 5: TypeScript 编译验证**

Run: `cd web && npx vue-tsc --noEmit 2>&1`
Expected: 无类型错误

- [ ] **Step 6: 提交**

```bash
git add web/src/components/StatCard.vue web/src/components/CategoryList.vue web/src/components/TagCloud.vue web/src/components/RecentNotes.vue
git commit -m "feat: add StatCard, CategoryList, TagCloud, RecentNotes components"
```

---

### Task 4: DashboardPage + 路由 + 导航

**Files:**
- Create: `web/src/pages/DashboardPage.vue`
- Modify: `web/src/main.ts:7-17`
- Modify: `web/src/App.vue:72-76`

- [ ] **Step 1: 创建 DashboardPage.vue**

```vue
<template>
  <div>
    <h2 class="text-2xl font-bold mb-6" style="color: var(--color-text);">Overview</h2>

    <!-- Stat Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <StatCard icon="📄" :value="stats.notesCount" label="Notes" />
      <StatCard icon="📁" :value="stats.categoriesCount" label="Categories" />
      <StatCard icon="🏷" :value="stats.tagsCount" label="Tags" />
      <StatCard icon="📎" :value="stats.attachmentsCount" label="Attachments" />
    </div>

    <!-- Category Distribution + Tag Cloud -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
      <CategoryList :categories="categoriesWithCount" />
      <TagCloud :tags="tags" />
    </div>

    <!-- Recent Updates -->
    <RecentNotes :notes="recentNotes" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type Note } from '../api'
import StatCard from '../components/StatCard.vue'
import CategoryList from '../components/CategoryList.vue'
import TagCloud from '../components/TagCloud.vue'
import RecentNotes from '../components/RecentNotes.vue'

const stats = ref({ notesCount: 0, categoriesCount: 0, tagsCount: 0, attachmentsCount: 0 })
const categoriesWithCount = ref<Array<{ name: string; count: number }>>([])
const tags = ref<string[]>([])
const recentNotes = ref<Note[]>([])

onMounted(async () => {
  const [indexData, attData, catData, tagData, notesData] = await Promise.all([
    api.getIndexStatus(),
    api.getAttachmentsStats(),
    api.getCategoriesWithCount(),
    api.getTags(),
    api.listNotes({ limit: 5 }),
  ])
  stats.value = {
    notesCount: indexData.notes_count,
    categoriesCount: catData.categories.length,
    tagsCount: tagData.tags.length,
    attachmentsCount: attData.count,
  }
  categoriesWithCount.value = catData.categories
  tags.value = tagData.tags
  recentNotes.value = notesData
})
</script>
```

- [ ] **Step 2: 修改 main.ts 路由**

将路由从：

```typescript
const routes = [
  { path: '/', component: NoteList },
  { path: '/note/:fileId', component: NoteDetail, props: true },
  { path: '/search', component: SearchPage },
  { path: '/chat', component: ChatPage },
]
```

改为：

```typescript
const routes = [
  { path: '/', component: DashboardPage },
  { path: '/notes', component: NoteList },
  { path: '/note/:fileId', component: NoteDetail, props: true },
  { path: '/search', component: SearchPage },
  { path: '/chat', component: ChatPage },
]
```

并在文件顶部添加：

```typescript
import DashboardPage from './pages/DashboardPage.vue'
```

- [ ] **Step 3: 修改 App.vue 导航**

将 `navItems` 从：

```typescript
const navItems = [
  { to: '/', label: 'Notes', icon: '📄' },
  { to: '/search', label: 'Search', icon: '🔍' },
  { to: '/chat', label: 'Chat', icon: '💬' },
]
```

改为：

```typescript
const navItems = [
  { to: '/', label: 'Overview', icon: '🏠' },
  { to: '/notes', label: 'Notes', icon: '📄' },
  { to: '/search', label: 'Search', icon: '🔍' },
  { to: '/chat', label: 'Chat', icon: '💬' },
]
```

- [ ] **Step 4: TypeScript + Vite 构建验证**

Run: `cd web && npm run build 2>&1`
Expected: 构建成功，无错误

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/DashboardPage.vue web/src/main.ts web/src/App.vue
git commit -m "feat: add DashboardPage as home, update routes and navigation"
```

---

### Task 5: 终验 — 全栈测试 + E2E

- [ ] **Step 1: 运行后端全量测试**

```bash
/c/Users/cherry/AppData/Local/Programs/Python/Python313/python.exe -m pytest tests/ -v -x
```

Expected: 全部通过，覆盖率保持 >= 80%

- [ ] **Step 2: 启动 dev server 手动验证总览页**

```bash
# Terminal 1: 启动后端
kb serve

# 浏览器打开 http://127.0.0.1:8420
# 验证:
#   1. 首页显示 Overview 页面（非之前的 Notes 列表）
#   2. 4 张统计卡片数字正确
#   3. 分类分布显示名字 + 数量，点击跳到 /notes?category=X
#   4. 标签云正确渲染，点击跳到 /notes?tag=X
#   5. 最近更新显示前 5 篇笔记
#   6. 侧边栏 Overview 是第一个导航项，高亮正确
#   7. 点击 Notes 导航 → /notes，回到原笔记列表
```

- [ ] **Step 3: 微调提交（如有）**

```bash
git add -A
git commit -m "chore: final verification for dashboard"
```
