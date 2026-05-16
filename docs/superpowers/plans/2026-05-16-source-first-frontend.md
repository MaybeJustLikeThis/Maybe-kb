# Source-First Architecture — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the frontend around source-first navigation — two-tier sidebar (function entries + source tabs), new SourcePage driven by `source_project`, OverviewPage without TypeDistribution, and routing aligned with the source-first model.

**Architecture:** Vue 3 + TypeScript + Vue Router (hash mode), FastAPI v1 backend, `api.ts` as the single API client layer. Pages are decoupled — each page independently calls the API.

**Tech Stack:** Vue 3, TypeScript, Vue Router, marked + highlight.js + DOMPurify

---

## Task 1: Update api.ts types and functions

**Files:**
- Modify: `web/src/api.ts:56,89,97,144,214-218`

- [ ] **Step 1: Remove entry_type from NoteSummary**

```typescript
export interface NoteSummary {
  file_id: string
  title: string
  description: string | null
  category: string | null
  tags: string[]
  created_at: string | null
  updated_at: string | null
  status: string
  source_project: string | null
  source_path: string | null
  source_context: string | null
  content_type: string
}
```

- [ ] **Step 2: Remove entry_types from Taxonomy**

```typescript
export interface Taxonomy {
  tags: string[]
  categories: CountItem[]
  source_projects: CountItem[]
  content_types: CountItem[]
}
```

- [ ] **Step 3: Remove type_distribution from DashboardStats**

```typescript
export interface DashboardStats {
  notes_count: number
  attachments_count: number
  source_projects: CountItem[]
  content_types: CountItem[]
  index_health: {
    notes_count: number
    vectors_count: number
    coverage: number
  }
}
```

- [ ] **Step 4: Add SourceItem type and getSources method**

Add types:
```typescript
export interface SourceItem {
  name: string
  label: string
  description: string
  icon: string
}

export interface SourcesResponse {
  sources: SourceItem[]
}
```

Remove `getTypeDistribution()` method. Add `getSources()`:

```typescript
  getSources() {
    return request<SourcesResponse>('/sources').then((data) => data.sources)
  },
```

Remove `entry_type` from `createNote()` parameters (line 144).

Add `source_project` parameter to `listNotes()`:

```typescript
  listNotes(params?: {
    category?: string
    tag?: string
    source_project?: string
    limit?: number
    offset?: number
  }) {
    const qs = new URLSearchParams()
    if (params?.category) qs.set('category', params.category)
    if (params?.tag) qs.set('tag', params.tag)
    if (params?.source_project) qs.set('source_project', params.source_project)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    const q = qs.toString()
    return request<NoteSummary[]>(`/notes${q ? '?' + q : ''}`)
  },
```

- [ ] **Step 5: Commit**

```bash
git add web/src/api.ts
git commit -m "refactor: remove entry_type from API types, add getSources and source_project filter"
```

---

## Task 2: Update Vue Router

**Files:**
- Modify: `web/src/main.ts`

- [ ] **Step 1: Update routes**

Replace the entire routes definition:

```typescript
import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './assets/base.css'

import OverviewPage from './pages/OverviewPage.vue'
import SourcePage from './pages/SourcePage.vue'
import NoteDetail from './pages/NoteDetail.vue'
import SearchPage from './pages/SearchPage.vue'
import ChatPage from './pages/ChatPage.vue'
import ManagePage from './pages/ManagePage.vue'

const routes = [
  { path: '/', component: OverviewPage },
  { path: '/source/:name', component: SourcePage, props: true },
  { path: '/source/:name/:fileId', component: NoteDetail, props: true },
  { path: '/manage', component: ManagePage },
  { path: '/search', component: SearchPage },
  { path: '/chat', component: ChatPage },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
```

- [ ] **Step 2: Commit**

```bash
git add web/src/main.ts
git commit -m "refactor: update router for source-first navigation"
```

---

## Task 3: Refactor App.vue sidebar — two-tier layout

**Files:**
- Modify: `web/src/App.vue:56-62`

- [ ] **Step 1: Update navItems and add sourceTabs**

Replace the `navItems` array and template section:

```vue
<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand-block">
        <router-link to="/" class="brand-mark">KB</router-link>
        <p>Control Center</p>
      </div>

      <nav class="nav-list">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="isNavActive(item.to) ? 'nav-active' : ''"
        >
          <span class="nav-token">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <hr class="nav-divider" />

      <nav class="nav-list">
        <router-link
          v-for="src in sourceTabs"
          :key="src.to"
          :to="src.to"
          class="nav-item"
          :class="isSourceActive(src.to) ? 'nav-active' : ''"
        >
          <span class="nav-token">{{ src.icon }}</span>
          <span>{{ src.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-status">
        <span class="status-dot"></span>
        <span>Local vault online</span>
      </div>
    </aside>

    <header v-if="tb.current" class="top-command">
      <div class="top-command-left">
        <router-link :to="tb.current.backTo" class="back-link">Back</router-link>
        <span v-if="tb.current.title" class="top-title">{{ tb.current.title }}</span>
      </div>
      <div class="top-command-actions">
        <button
          v-for="action in tb.current.actions"
          :key="action.label"
          @click="action.onClick"
          :class="action.btnClass"
        >{{ action.label }}</button>
      </div>
    </header>

    <main class="app-main" :class="tb.current ? 'has-top-command' : ''">
      <router-view />
    </main>
  </div>
</template>
```

```typescript
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTopBar } from './topBar'
import { api, type SourceItem } from './api'

const route = useRoute()
const tb = useTopBar()

const navItems = [
  { to: '/', label: 'Overview', icon: 'OV' },
  { to: '/search', label: 'Search', icon: 'SR' },
  { to: '/chat', label: 'Chat', icon: 'AI' },
]

const sourceTabs = ref<Array<{ to: string; label: string; icon: string }>>([])

function isNavActive(to: string) {
  return route.path === to
}

function isSourceActive(to: string) {
  return route.path.startsWith(to)
}

onMounted(async () => {
  try {
    const sources = await api.getSources()
    sourceTabs.value = sources.map((s: SourceItem) => ({
      to: `/source/${s.name}`,
      label: s.label,
      icon: s.icon,
    }))
  } catch {
    // Fallback: hardcoded sources
    sourceTabs.value = [
      { to: '/source/blog', label: '博客', icon: 'BK' },
      { to: '/source/agent', label: 'Agent 沉淀', icon: 'AG' },
      { to: '/source/manual', label: '手动录入', icon: 'MN' },
    ]
  }
})
</script>
```

- [ ] **Step 2: Add .nav-divider style**

Add to the `<style scoped>` block:

```css
.nav-divider {
  margin: 8px 20px;
  border: none;
  border-top: 1px solid var(--color-sidebar-border);
  opacity: 0.4;
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/App.vue
git commit -m "refactor: two-tier sidebar with function entries + source tabs"
```

---

## Task 4: Rename DashboardPage → OverviewPage, remove TypeDistribution

**Files:**
- Rename: `web/src/pages/DashboardPage.vue` → `web/src/pages/OverviewPage.vue`
- Modify: content of the renamed file

- [ ] **Step 1: Create OverviewPage.vue from DashboardPage.vue**

Copy `DashboardPage.vue` to `OverviewPage.vue`, then modify:

Remove `TypeDistribution` import (line 61):
```typescript
import StatCard from '../components/StatCard.vue'
import IndexHealth from '../components/IndexHealth.vue'
import SourceProjects from '../components/SourceProjects.vue'
import ContentFormatPie from '../components/ContentFormatPie.vue'
import QuickActions from '../components/QuickActions.vue'
import RecentNotes from '../components/RecentNotes.vue'
import DashboardActivity from '../components/DashboardActivity.vue'
```

Remove `typeDistribution` ref (line 72).

Keep `contentTypes` ref (used by ContentFormatPie).

Update `onMounted` — remove `getTypeDistribution()`, keep `getContentTypeStats()`:
```typescript
onMounted(async () => {
  try {
    const [
      indexData, attData, catData, tagData, notesData,
      srcData, ctData, healthData,
    ] = await Promise.all([
      api.getIndexStatus(),
      api.getAttachmentsStats(),
      api.getCategoriesWithCount(),
      api.getTags(),
      api.listNotes({ limit: 8 }),
      api.getSourceProjects(),
      api.getContentTypeStats(),
      api.getIndexHealth(),
    ])
    stats.value = {
      notesCount: indexData.notes_count,
      typesCount: srcData.projects.length,
      categoriesCount: catData.categories.length,
      tagsCount: tagData.tags.length,
      attachmentsCount: attData.count,
    }
    sourceProjects.value = srcData.projects
    contentTypes.value = ctData.content_types
    indexHealth.value = healthData
    recentNotes.value = notesData
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
  } finally {
    loading.value = false
  }

  try {
    activity.value = await api.getDashboardActivity({ limit: 8 })
  } catch (e) {
    activityError.value = true
  }
})
```

In the template, remove the TypeDistribution panel (lines 34-36). Keep ContentFormatPie (file format distribution is unrelated to entry_type). Replace TypeDistribution with SourceProjects prominently.

Updated template section for the overview grid:
```vue
      <div class="overview-grid">
        <SourceProjects :projects="sourceProjects" />
        <IndexHealth
          :notes-count="indexHealth.notes_count"
          :vectors-count="indexHealth.vectors_count"
          :coverage="indexHealth.coverage"
        />
        <DashboardActivity :items="activity" :error="activityError" />
      </div>

      <div class="widget-grid">
        <ContentFormatPie :content-types="contentTypes" />
        <QuickActions @reindex="handleReindex" />
        <RecentNotes :notes="recentNotes" />
      </div>
```

Update `typesCount` in stats to count source projects instead:
```typescript
typesCount: srcData.projects.length,
```

- [ ] **Step 2: Delete old DashboardPage.vue**

```bash
rm web/src/pages/DashboardPage.vue
```

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/OverviewPage.vue
git rm web/src/pages/DashboardPage.vue
git commit -m "refactor: rename DashboardPage to OverviewPage, remove TypeDistribution"
```

---

## Task 5: Create SourcePage (replace NoteList)

**Files:**
- Create: `web/src/pages/SourcePage.vue`
- Modify: (NoteList.vue stays until router is confirmed, then deleted)

- [ ] **Step 1: Create SourcePage.vue**

```vue
<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold" style="color: var(--color-text);">{{ sourceLabel }}</h2>
      <router-link
        to="/note/new"
        class="btn btn-primary"
      >New Note</router-link>
    </div>

    <div class="flex gap-8">
      <div class="w-52 flex-shrink-0">
        <div class="mb-6">
          <h3 class="section-heading">Categories</h3>
          <div class="space-y-0.5">
            <button
              @click="selectedCategory = ''"
              :class="['filter-chip', !selectedCategory ? 'filter-chip-active' : '']"
            >All</button>
            <button
              v-for="cat in categories" :key="cat"
              @click="selectedCategory = cat"
              :class="['filter-chip', selectedCategory === cat ? 'filter-chip-active' : '']"
            >{{ cat }}</button>
          </div>
        </div>

        <div>
          <h3 class="section-heading">Tags</h3>
          <div class="space-y-0.5">
            <button
              @click="selectedTag = ''"
              :class="['filter-chip', !selectedTag ? 'filter-chip-active' : '']"
            >All</button>
            <button
              v-for="tag in tags" :key="tag"
              @click="selectedTag = tag"
              :class="['filter-chip', selectedTag === tag ? 'filter-chip-active' : '']"
            >{{ tag }}</button>
          </div>
        </div>
      </div>

      <div class="flex-1">
        <div v-if="loading" class="empty-state">
          <div class="empty-state-icon">...</div>
          <p>Loading...</p>
        </div>

        <div v-else-if="notes.length === 0" class="empty-state">
          <div class="empty-state-icon">NT</div>
          <p>No notes in this source yet.</p>
        </div>

        <ul v-else class="space-y-2">
          <li v-for="note in notes" :key="note.file_id">
            <router-link
              :to="`/source/${props.name}/${encodeURIComponent(note.file_id)}`"
              class="card block"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                  <h3 class="font-semibold truncate" style="color: var(--color-text);">{{ note.title }}</h3>
                  <div class="flex flex-wrap gap-1.5 mt-1.5">
                    <span v-if="note.category" class="badge badge-primary">{{ note.category }}</span>
                    <span v-for="tag in note.tags" :key="tag" class="badge badge-muted">{{ tag }}</span>
                  </div>
                  <p v-if="note.description" class="text-sm mt-2 truncate" style="color: var(--color-text-secondary);">{{ note.description }}</p>
                </div>
                <span class="text-xs whitespace-nowrap flex-shrink-0 mt-0.5" style="color: var(--color-text-muted);">{{ note.updated_at || note.created_at }}</span>
              </div>
            </router-link>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { api, type Note } from '../api'

const props = defineProps<{ name: string }>()

const notes = ref<Note[]>([])
const categories = ref<string[]>([])
const tags = ref<string[]>([])
const selectedCategory = ref('')
const selectedTag = ref('')
const loading = ref(false)

const sourceLabel = computed(() => props.name.charAt(0).toUpperCase() + props.name.slice(1))

async function load() {
  loading.value = true
  try {
    const params: { source_project: string; category?: string; tag?: string } = {
      source_project: props.name,
    }
    if (selectedCategory.value) params.category = selectedCategory.value
    if (selectedTag.value) params.tag = selectedTag.value
    notes.value = await api.listNotes(params)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const [cats, tgs] = await Promise.all([api.getCategories(), api.getTags()])
  categories.value = cats.categories
  tags.value = tgs.tags
  load()
})

watch([selectedCategory, selectedTag], () => load())
</script>

<style scoped>
.filter-chip {
  display: block;
  width: 100%;
  text-align: left;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  transition: all var(--transition-fast);
}
.filter-chip:hover {
  background: var(--color-surface-tinted);
  color: var(--color-text);
}
.filter-chip-active {
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
  font-weight: 700;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/SourcePage.vue
git commit -m "feat: add SourcePage with source_project filtering"
```

---

## Task 6: Update NoteDetail for new route

**Files:**
- Modify: `web/src/pages/NoteDetail.vue`

- [ ] **Step 1: Update back-link and note links**

The `NoteDetail` now receives `name` and `fileId` as route props. Update the `syncTopBar` function to use `name` for back navigation. Update related note links.

Update props:
```typescript
const props = defineProps<{ name?: string; fileId?: string }>()
```

Update `syncTopBar` back-to:
```typescript
  if (isNew.value) {
    setTopBar({
      backTo: props.name ? `/source/${props.name}` : '/',
      // ...
    })
  } else if (isEditing.value) {
    setTopBar({
      backTo: props.name ? `/source/${props.name}` : '/',
      // ...
    })
  } else {
    setTopBar({
      backTo: props.name ? `/source/${props.name}` : '/',
      // ...
    })
  }
```

Update related note links in template:
```vue
<router-link
  v-for="note in relatedNotes"
  :key="note.file_id"
  :to="props.name ? `/source/${props.name}/${encodeURIComponent(note.file_id)}` : `/note/${encodeURIComponent(note.file_id)}`"
  class="card flex justify-between items-start"
>
```

Update save redirection (new note):
```typescript
    if (props.name) {
      router.push(`/source/${props.name}/${encodeURIComponent(note.file_id)}`)
    } else {
      router.push(`/note/${encodeURIComponent(note.file_id)}`)
    }
```

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/NoteDetail.vue
git commit -m "refactor: update NoteDetail back-links and routes for source context"
```

---

## Task 7: Update ManagePage — remove Type tab

**Files:**
- Modify: `web/src/pages/ManagePage.vue`

- [ ] **Step 1: Remove type-related template and script**

Remove the entire "Type Tab" template section (lines 29-59).
Remove `getTypeDistribution()` call and type-related state.
Remove tabs array entry for "type".
Remove `typeIcon`, `typeIconBg`, `typeColorHex` functions and maps.
Remove `typeTags` fetching logic.

Updated tabs:
```typescript
const tabs = [
  { key: 'category', label: 'By Category' },
  { key: 'tag', label: 'By Tag' },
  { key: 'source', label: 'By Source' },
  { key: 'index', label: 'Index' },
]
```

Set default active tab to `'source'` instead of `'type'`.

Remove `getTypeDistribution` import/usage. Remove `typeDistribution`, `typeTags` refs. Simplify `onMounted`:

```typescript
onMounted(async () => {
  try {
    const [catData, tagData, srcData, healthData] = await Promise.all([
      api.getCategoriesWithCount(),
      api.getTags(),
      api.getSourceProjects(),
      api.getIndexHealth(),
    ])
    categoriesWithCount.value = catData.categories
    tags.value = tagData.tags
    sourceProjects.value = srcData.projects
    indexHealth.value = healthData
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load'
  } finally {
    loading.value = false
  }
})
```

Update source tab links to point to `/source/:name`:
```vue
      <router-link
        v-for="p in sourceProjects"
        :key="p.name"
        :to="`/source/${encodeURIComponent(p.name)}`"
        class="card flex items-center justify-between no-underline hover:opacity-80"
      >
```

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/ManagePage.vue
git commit -m "refactor: remove Type tab from ManagePage, default to Source tab"
```

---

## Task 8: Update RecentNotes — remove entry_type badge

**Files:**
- Modify: `web/src/components/RecentNotes.vue:15-16,36-47`

- [ ] **Step 1: Remove entry_type badge display**

Remove the entry_type badge `<span>` from the template (lines 15-16).
Remove `typeColors` map and `typeBadgeStyle` function (lines 36-47).

Updated template:
```vue
          <div class="flex items-center gap-3 min-w-0">
            <span class="truncate font-medium" style="color: var(--color-text);">{{ note.title }}</span>
          </div>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/RecentNotes.vue
git commit -m "refactor: remove entry_type badge from RecentNotes"
```

---

## Task 9: Delete TypeDistribution.vue

**Files:**
- Delete: `web/src/components/TypeDistribution.vue`

- [ ] **Step 1: Delete the file**

```bash
git rm web/src/components/TypeDistribution.vue
```

- [ ] **Step 2: Commit**

```bash
git commit -m "refactor: delete TypeDistribution component"
```

---

## Task 10: Clean up NoteList.vue (old page)

**Files:**
- Delete: `web/src/pages/NoteList.vue`

- [ ] **Step 1: Delete the old NoteList page**

```bash
git rm web/src/pages/NoteList.vue
```

- [ ] **Step 2: Commit**

```bash
git commit -m "refactor: remove old NoteList page, replaced by SourcePage"
```

---

## Task 11: Verify frontend builds

**Files:**
- No changes

- [ ] **Step 1: Install and build**

```bash
cd web && npm install && npx vue-tsc --noEmit && npx vite build
```

Expected: no type errors, build succeeds.

- [ ] **Step 2: Start dev server and spot-check**

```bash
npm run dev
```

Manual verification checklist:
- [ ] Sidebar shows function entries (Overview, Search, Chat) above divider
- [ ] Sidebar shows source tabs (博客, Agent 沉淀, 手动录入) below divider
- [ ] Each source tab navigates to `/source/:name` showing filtered notes
- [ ] Clicking a note in a source tab opens `/source/:name/:fileId`
- [ ] NoteDetail back button returns to the correct source tab
- [ ] Overview page shows source distribution (no TypeDistribution)
- [ ] Manage page defaults to Source tab (no Type tab)
- [ ] RecentNotes no longer shows entry_type badges
- [ ] TypeScript compilation passes
- [ ] Vite build succeeds

- [ ] **Step 3: Commit any fixups**

```bash
git add -A && git commit -m "fix: frontend source-first verification fixes"
```
