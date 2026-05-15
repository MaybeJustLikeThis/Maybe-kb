# Modern Tech UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Bright Control Center refresh for the KB web UI, focused on Overview, Search, and Chat, with a lightweight dashboard activity API.

**Architecture:** Keep the existing Vue 3 + Tailwind frontend and FastAPI `/api/v1` backend. Add one backend read-model endpoint for activity, then restyle shared tokens and the three primary frontend pages around a bright workspace with a dark technical navigation rail.

**Tech Stack:** Python 3.11+, FastAPI, pytest, Vue 3, TypeScript, Vite, Tailwind CSS.

---

## File Structure

- Modify `src/kb/core/queries.py`: add `get_dashboard_activity(ctx, limit)` as a read-model helper derived from existing notes.
- Modify `src/kb/api/v1.py`: add `GET /dashboard/activity` using the v1 envelope.
- Modify `tests/test_api_v1.py`: add API coverage for empty and populated activity responses.
- Modify `web/src/api.ts`: add activity response interfaces and `getDashboardActivity()`.
- Modify `web/src/assets/base.css`: replace the old minimalist tokens with Bright Control Center tokens and shared controls.
- Modify `web/src/App.vue`: restyle the app shell, remove broken emoji nav labels, and improve the top command bar.
- Modify `web/src/components/StatCard.vue`: convert metric cards into polished control-center cards.
- Modify `web/src/components/IndexHealth.vue`: brighten progress and health display.
- Modify `web/src/components/TypeDistribution.vue`, `SourceProjects.vue`, `QuickActions.vue`, `RecentNotes.vue`: adapt dashboard widgets to the new tokens.
- Create `web/src/components/DashboardActivity.vue`: render the activity rail from the new endpoint.
- Modify `web/src/pages/DashboardPage.vue`: restructure Overview into the Bright Control Center layout and load activity without blocking the page.
- Modify `web/src/pages/SearchPage.vue`: restyle as a retrieval workbench using the existing search API.
- Modify `web/src/pages/ChatPage.vue`: restyle as an assistant panel and present provider configuration errors cleanly.
- Modify `web/src/pages/NoteList.vue`, `ManagePage.vue`, `NoteDetail.vue` only where needed for token compatibility and obvious broken text/icons.

Do not use a worktree for this implementation. Continue on the existing `codex/modern-tech-ui` branch as requested.

---

### Task 1: Add Dashboard Activity API

**Files:**
- Modify: `tests/test_api_v1.py`
- Modify: `src/kb/core/queries.py`
- Modify: `src/kb/api/v1.py`

- [ ] **Step 1: Write failing tests for empty and populated activity**

Add these tests near `test_v1_dashboard_returns_summary` in `tests/test_api_v1.py`:

```python
def test_v1_dashboard_activity_returns_empty_envelope(client: TestClient) -> None:
    """Dashboard activity returns an empty list for an empty knowledge base."""
    response = client.get("/api/v1/dashboard/activity")

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["data"] == []


def test_v1_dashboard_activity_returns_recent_notes(client: TestClient) -> None:
    """Dashboard activity is derived from recent note metadata."""
    first = client.post("/api/v1/notes", json={
        "title": "First Activity Note",
        "content": "First body",
        "category": "ops",
        "tags": ["alpha"],
        "source_project": "kb",
    }).json()["data"]
    second = client.post("/api/v1/notes", json={
        "title": "Second Activity Note",
        "content": "Second body",
        "category": "ops",
        "tags": ["beta"],
        "source_project": "kb",
    }).json()["data"]

    response = client.get("/api/v1/dashboard/activity", params={"limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["kind"] == "note_updated"
    assert item["title"] in {first["title"], second["title"]}
    assert item["description"]
    assert item["timestamp"]
    assert set(item["note"]) == {"file_id", "title"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_api_v1.py::test_v1_dashboard_activity_returns_empty_envelope tests/test_api_v1.py::test_v1_dashboard_activity_returns_recent_notes -v
```

Expected: both tests fail with `404 Not Found` for `/api/v1/dashboard/activity`.

- [ ] **Step 3: Implement the read-model helper**

Add this function to `src/kb/core/queries.py` after `get_dashboard_stats`:

```python
def get_dashboard_activity(ctx: AppContext, limit: int) -> list[dict]:
    """Return lightweight activity items derived from recent notes."""
    rows = ctx.db.list_notes(limit=limit, offset=0)
    items: list[dict] = []
    for row in rows:
        note = note_row_to_summary(ctx.db, row)
        timestamp = note.get("updated_at") or note.get("created_at")
        description_parts = []
        if note.get("source_project"):
            description_parts.append(f"Source: {note['source_project']}")
        if note.get("category"):
            description_parts.append(f"Category: {note['category']}")
        if note.get("entry_type"):
            description_parts.append(f"Type: {note['entry_type']}")
        description = " · ".join(description_parts) or "Knowledge note updated"
        items.append({
            "kind": "note_updated",
            "title": note["title"],
            "description": description,
            "timestamp": timestamp,
            "note": {
                "file_id": note["file_id"],
                "title": note["title"],
            },
        })
    return items
```

- [ ] **Step 4: Add the v1 route**

In `src/kb/api/v1.py`, add this route immediately after `get_dashboard`:

```python
    @router.get("/dashboard/activity")
    def get_dashboard_activity(limit: int = Query(8, ge=1, le=20)):
        return responses.ok(queries.get_dashboard_activity(ctx, limit))
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
pytest tests/test_api_v1.py::test_v1_dashboard_activity_returns_empty_envelope tests/test_api_v1.py::test_v1_dashboard_activity_returns_recent_notes -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_api_v1.py src/kb/core/queries.py src/kb/api/v1.py
git commit -m "feat: add dashboard activity API"
```

---

### Task 2: Add Frontend API Types And Shared Visual System

**Files:**
- Modify: `web/src/api.ts`
- Modify: `web/src/assets/base.css`
- Modify: `web/src/App.vue`

- [ ] **Step 1: Add activity API types**

In `web/src/api.ts`, add these interfaces after `DashboardStats`:

```ts
export interface DashboardActivityItem {
  kind: string
  title: string
  description: string
  timestamp: string | null
  note: {
    file_id: string
    title: string
  }
}
```

Then add this method inside `api` after `getIndexHealth()`:

```ts
  getDashboardActivity(params?: { limit?: number }) {
    const qs = new URLSearchParams()
    if (params?.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return request<DashboardActivityItem[]>(`/dashboard/activity${q ? '?' + q : ''}`)
  },
```

- [ ] **Step 2: Replace shared tokens and controls**

Replace `web/src/assets/base.css` with:

```css
/* Bright Control Center design tokens */
:root {
  --color-sidebar: #0d1726;
  --color-sidebar-hover: rgba(34, 211, 238, 0.1);
  --color-sidebar-active: rgba(34, 211, 238, 0.16);
  --color-sidebar-border: rgba(148, 163, 184, 0.18);
  --color-primary: #0891b2;
  --color-primary-hover: #0e7490;
  --color-primary-light: #cffafe;
  --color-secondary: #4f46e5;
  --color-accent: #14b8a6;
  --color-warning: #b45309;
  --color-danger: #dc2626;
  --color-success: #059669;
  --color-bg: #eef5ff;
  --color-bg-soft: #f8fbff;
  --color-surface: rgba(255, 255, 255, 0.92);
  --color-surface-solid: #ffffff;
  --color-surface-tinted: #f1f8ff;
  --color-border: #cbdff4;
  --color-border-hover: #93c5fd;
  --color-text: #0f172a;
  --color-text-secondary: #334155;
  --color-text-muted: #64748b;
  --color-text-sidebar: #dbeafe;
  --color-text-sidebar-muted: #8da2bd;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
  --shadow-md: 0 12px 28px rgba(15, 23, 42, 0.08);
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
}

body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.16), transparent 30rem),
    linear-gradient(135deg, var(--color-bg-soft), var(--color-bg));
  color: var(--color-text);
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}

a {
  color: inherit;
  text-decoration: none;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast);
}

.card:hover {
  border-color: var(--color-border-hover);
  box-shadow: var(--shadow-md);
}

.panel-title {
  color: var(--color-text);
  font-size: 0.95rem;
  font-weight: 700;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 36px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  font-weight: 650;
  transition: all var(--transition-fast);
  cursor: pointer;
  border: 1px solid transparent;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  color: #fff;
  box-shadow: 0 10px 22px rgba(8, 145, 178, 0.22);
}

.btn-primary:hover:not(:disabled) {
  filter: brightness(0.96);
}

.btn-ghost {
  background: rgba(8, 145, 178, 0.08);
  color: var(--color-primary-hover);
}

.btn-ghost:hover:not(:disabled) {
  background: rgba(8, 145, 178, 0.14);
}

.btn-outline {
  background: var(--color-surface-solid);
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}

.btn-outline:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary-hover);
}

.btn-danger {
  background: rgba(220, 38, 38, 0.08);
  color: var(--color-danger);
}

.btn-danger:hover:not(:disabled) {
  background: rgba(220, 38, 38, 0.14);
}

.input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast);
  background: rgba(255, 255, 255, 0.94);
  color: var(--color-text);
}

.input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.12);
}

.input::placeholder {
  color: var(--color-text-muted);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 650;
  line-height: 1.5;
}

.badge-primary {
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
}

.badge-muted {
  background: #e8f1fb;
  color: var(--color-text-secondary);
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-text-muted);
}

.empty-state-icon {
  font-size: 2rem;
  margin-bottom: 12px;
  opacity: 0.72;
}

.section-heading {
  font-size: 0.7rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
  margin-bottom: 10px;
}

.divider {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 24px 0;
}
```

- [ ] **Step 3: Restyle the app shell**

In `web/src/App.vue`, replace the template and `navItems` with a shell that uses text symbols instead of emoji:

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
          :class="route.path === item.to ? 'nav-active' : ''"
        >
          <span class="nav-token">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
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

Use this `navItems` array:

```ts
const navItems = [
  { to: '/', label: 'Overview', icon: 'OV' },
  { to: '/notes', label: 'Notes', icon: 'NT' },
  { to: '/manage', label: 'Manage', icon: 'MG' },
  { to: '/search', label: 'Search', icon: 'SR' },
  { to: '/chat', label: 'Chat', icon: 'AI' },
]
```

Replace the scoped style with:

```css
.app-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: 240px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: linear-gradient(180deg, #0d1726, #101827);
  border-right: 1px solid var(--color-sidebar-border);
  color: var(--color-text-sidebar);
}

.brand-block {
  padding: 24px 20px 18px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 34px;
  border-radius: 8px;
  background: linear-gradient(135deg, #22d3ee, #6366f1);
  color: #fff;
  font-weight: 900;
  letter-spacing: 0.04em;
}

.brand-block p {
  margin-top: 8px;
  color: var(--color-text-sidebar-muted);
  font-size: 0.75rem;
}

.nav-list {
  flex: 1;
  padding: 0 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 8px;
  color: var(--color-text-sidebar);
  font-size: 0.9rem;
  font-weight: 650;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.nav-item:hover,
.nav-active {
  background: var(--color-sidebar-active);
  color: #f8fafc;
}

.nav-token {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.08);
  color: #a5f3fc;
  font-size: 0.68rem;
  letter-spacing: 0.04em;
}

.sidebar-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 16px 18px;
  padding: 12px;
  border: 1px solid var(--color-sidebar-border);
  border-radius: 8px;
  color: var(--color-text-sidebar-muted);
  font-size: 0.75rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.16);
}

.top-command {
  position: fixed;
  top: 0;
  left: 240px;
  right: 0;
  z-index: 10;
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 28px;
  background: rgba(248, 251, 255, 0.9);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--color-border);
}

.top-command-left,
.top-command-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.back-link {
  color: var(--color-primary-hover);
  font-size: 0.85rem;
  font-weight: 700;
}

.top-title {
  color: var(--color-text);
  font-size: 0.9rem;
  font-weight: 750;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  min-height: 100vh;
  margin-left: 240px;
  padding: 32px;
}

.app-main.has-top-command {
  padding-top: 78px;
}
```

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 5: Commit**

```powershell
git add web/src/api.ts web/src/assets/base.css web/src/App.vue
git commit -m "style: add bright control center shell"
```

---

### Task 3: Build Overview Control Center And Activity Rail

**Files:**
- Create: `web/src/components/DashboardActivity.vue`
- Modify: `web/src/components/StatCard.vue`
- Modify: `web/src/components/IndexHealth.vue`
- Modify: `web/src/components/TypeDistribution.vue`
- Modify: `web/src/components/SourceProjects.vue`
- Modify: `web/src/components/QuickActions.vue`
- Modify: `web/src/components/RecentNotes.vue`
- Modify: `web/src/pages/DashboardPage.vue`

- [ ] **Step 1: Create the activity component**

Create `web/src/components/DashboardActivity.vue`:

```vue
<template>
  <section class="card activity-panel">
    <div class="activity-head">
      <div>
        <h3 class="panel-title">Activity Stream</h3>
        <p>Recent knowledge base updates</p>
      </div>
      <span class="badge badge-primary">{{ items.length }}</span>
    </div>

    <div v-if="error" class="activity-empty">Activity unavailable.</div>
    <div v-else-if="items.length === 0" class="activity-empty">No recent activity.</div>
    <ol v-else class="activity-list">
      <li v-for="item in items" :key="item.note.file_id + item.timestamp" class="activity-item">
        <span class="activity-dot"></span>
        <router-link :to="`/note/${encodeURIComponent(item.note.file_id)}`">
          <strong>{{ item.title }}</strong>
          <span>{{ item.description }}</span>
          <time>{{ formatTime(item.timestamp) }}</time>
        </router-link>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import type { DashboardActivityItem } from '../api'

defineProps<{
  items: DashboardActivityItem[]
  error?: boolean
}>()

function formatTime(value: string | null): string {
  if (!value) return 'Unknown time'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
</script>

<style scoped>
.activity-panel {
  min-height: 100%;
}

.activity-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.activity-head p {
  margin-top: 3px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.activity-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.activity-item {
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 10px;
}

.activity-dot {
  width: 9px;
  height: 9px;
  margin-top: 6px;
  border-radius: 999px;
  background: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.13);
}

.activity-item a {
  display: grid;
  gap: 2px;
}

.activity-item strong {
  color: var(--color-text);
  font-size: 0.88rem;
}

.activity-item span,
.activity-item time,
.activity-empty {
  color: var(--color-text-muted);
  font-size: 0.78rem;
}
</style>
```

- [ ] **Step 2: Restyle metric and dashboard widgets**

Update `web/src/components/StatCard.vue`:

```vue
<template>
  <div class="card stat-card">
    <span class="stat-icon">{{ icon }}</span>
    <div>
      <p class="stat-value">{{ value }}</p>
      <p class="stat-label">{{ label }}</p>
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

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 94px;
}

.stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.14), rgba(79, 70, 229, 0.14));
  color: var(--color-primary-hover);
  font-weight: 900;
}

.stat-value {
  color: var(--color-text);
  font-size: 1.55rem;
  font-weight: 850;
  line-height: 1;
}

.stat-label {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 700;
}
</style>
```

Update the other widgets by replacing dark hardcoded backgrounds with token colors:

```css
/* In IndexHealth.vue progress track */
background: #dbeafe;

/* In TypeDistribution.vue bar track */
background: #e8f1fb;

/* In RecentNotes.vue hover */
hover:bg-sky-50
```

Also replace broken emoji text in `RecentNotes.vue` empty state with a simple ASCII icon label:

```vue
<div class="empty-state-icon">NT</div>
```

- [ ] **Step 3: Restructure DashboardPage**

In `web/src/pages/DashboardPage.vue`, import the new component:

```ts
import DashboardActivity from '../components/DashboardActivity.vue'
import type { DashboardActivityItem } from '../api'
```

Add state:

```ts
const activity = ref<DashboardActivityItem[]>([])
const activityError = ref(false)
```

Add `api.getDashboardActivity({ limit: 8 })` to the `Promise.all` call, but handle it separately so it cannot block dashboard rendering:

```ts
    const [
      indexData, attData, catData, tagData, notesData,
      typeData, srcData, ctData, healthData,
    ] = await Promise.all([
      api.getIndexStatus(),
      api.getAttachmentsStats(),
      api.getCategoriesWithCount(),
      api.getTags(),
      api.listNotes({ limit: 8 }),
      api.getTypeDistribution(),
      api.getSourceProjects(),
      api.getContentTypeStats(),
      api.getIndexHealth(),
    ])

    try {
      activity.value = await api.getDashboardActivity({ limit: 8 })
      activityError.value = false
    } catch {
      activity.value = []
      activityError.value = true
    }
```

Replace the top-level template content with a header plus grid:

```vue
<div class="dashboard-page">
  <div class="page-hero">
    <div>
      <p class="eyebrow">Knowledge system</p>
      <h2>Overview Control Center</h2>
      <p>Monitor index health, source coverage, and recent knowledge updates.</p>
    </div>
    <button class="btn btn-primary" @click="handleReindex">Rebuild Index</button>
  </div>

  <div v-if="loading" class="empty-state">
    <div class="empty-state-icon">...</div>
    <p>Loading...</p>
  </div>

  <div v-else-if="error" class="empty-state">
    <div class="empty-state-icon">!</div>
    <p style="color: var(--color-danger);">{{ error }}</p>
  </div>

  <template v-else>
    <div class="grid grid-cols-2 xl:grid-cols-5 gap-4 mb-5">
      <StatCard icon="NT" :value="stats.notesCount" label="Notes" />
      <StatCard icon="TP" :value="stats.typesCount" label="Types" />
      <StatCard icon="CT" :value="stats.categoriesCount" label="Categories" />
      <StatCard icon="TG" :value="stats.tagsCount" label="Tags" />
      <StatCard icon="AT" :value="stats.attachmentsCount" label="Attachments" />
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-5">
      <div class="xl:col-span-2">
        <TypeDistribution :types="typeDistribution" />
      </div>
      <IndexHealth
        :notes-count="indexHealth.notes_count"
        :vectors-count="indexHealth.vectors_count"
        :coverage="indexHealth.coverage"
      />
      <DashboardActivity :items="activity" :error="activityError" />
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <SourceProjects :projects="sourceProjects" />
      <ContentFormatPie :content-types="contentTypes" />
      <QuickActions @reindex="handleReindex" />
      <div class="xl:col-span-3">
        <RecentNotes :notes="recentNotes" />
      </div>
    </div>
  </template>
</div>
```

Add scoped styles:

```css
.dashboard-page {
  max-width: 1440px;
  margin: 0 auto;
}

.page-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.eyebrow {
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.page-hero h2 {
  margin-top: 5px;
  color: var(--color-text);
  font-size: 1.85rem;
  font-weight: 850;
}

.page-hero p:last-child {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 0.92rem;
}
```

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 5: Commit**

```powershell
git add web/src/components/DashboardActivity.vue web/src/components/StatCard.vue web/src/components/IndexHealth.vue web/src/components/TypeDistribution.vue web/src/components/SourceProjects.vue web/src/components/QuickActions.vue web/src/components/RecentNotes.vue web/src/pages/DashboardPage.vue
git commit -m "style: refresh overview control center"
```

---

### Task 4: Refresh Search And Chat Work Surfaces

**Files:**
- Modify: `web/src/pages/SearchPage.vue`
- Modify: `web/src/pages/ChatPage.vue`

- [ ] **Step 1: Restyle SearchPage as a retrieval workbench**

Replace the SearchPage template with:

```vue
<template>
  <div class="workbench-page">
    <header class="workbench-header">
      <p class="eyebrow">Retrieval</p>
      <h2>Search Workbench</h2>
      <p>Find notes, source context, and tagged knowledge across the local vault.</p>
    </header>

    <div class="search-command card">
      <span class="command-token">SR</span>
      <input
        v-model="query"
        @keyup.enter="search"
        class="input command-input"
        placeholder="Search notes..."
        autofocus
      />
      <button class="btn btn-primary" :disabled="searching || !query.trim()" @click="search">Run</button>
    </div>

    <div v-if="searching" class="empty-state">
      <div class="empty-state-icon">...</div>
      <p>Searching...</p>
    </div>

    <section v-else-if="results.length > 0" class="results-panel">
      <p class="result-count">{{ results.length }} result{{ results.length !== 1 ? 's' : '' }} for "{{ lastQuery }}"</p>
      <ul class="result-list">
        <li v-for="result in results" :key="result.note.file_id">
          <router-link :to="`/note/${encodeURIComponent(result.note.file_id)}`" class="card result-card">
            <div class="result-main">
              <h3>{{ result.note.title }}</h3>
              <p v-if="result.note.description">{{ result.note.description }}</p>
              <p v-if="result.chunk_text" class="chunk-text">{{ result.chunk_text }}</p>
              <div class="flex flex-wrap gap-1.5 mt-3">
                <span v-if="result.note.category" class="badge badge-primary">{{ result.note.category }}</span>
                <span v-for="tag in result.note.tags" :key="tag" class="badge badge-muted">{{ tag }}</span>
              </div>
            </div>
            <div class="result-meta">
              <span>{{ result.source }}</span>
              <strong v-if="result.score !== null">{{ Math.round(result.score * 100) }}%</strong>
            </div>
          </router-link>
        </li>
      </ul>
    </section>

    <div v-else-if="lastQuery" class="empty-state">
      <div class="empty-state-icon">0</div>
      <p>No results found for "{{ lastQuery }}".</p>
    </div>
  </div>
</template>
```

Add scoped styles:

```css
.workbench-page {
  max-width: 1120px;
  margin: 0 auto;
}

.workbench-header {
  margin-bottom: 20px;
}

.eyebrow {
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.workbench-header h2 {
  margin-top: 5px;
  color: var(--color-text);
  font-size: 1.8rem;
  font-weight: 850;
}

.workbench-header p:last-child {
  margin-top: 6px;
  color: var(--color-text-muted);
}

.search-command {
  display: grid;
  grid-template-columns: 42px 1fr auto;
  gap: 12px;
  align-items: center;
  margin-bottom: 22px;
}

.command-token {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  border-radius: 8px;
  background: #0d1726;
  color: #a5f3fc;
  font-size: 0.72rem;
  font-weight: 900;
}

.command-input {
  min-height: 42px;
}

.result-count {
  margin-bottom: 12px;
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

.result-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.result-card {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.result-main h3 {
  color: var(--color-text);
  font-size: 1rem;
  font-weight: 800;
}

.result-main p {
  margin-top: 7px;
  color: var(--color-text-secondary);
  font-size: 0.88rem;
}

.chunk-text {
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-surface-tinted);
  border: 1px solid var(--color-border);
}

.result-meta {
  min-width: 88px;
  text-align: right;
  color: var(--color-text-muted);
  font-size: 0.76rem;
  text-transform: uppercase;
}

.result-meta strong {
  display: block;
  margin-top: 6px;
  color: var(--color-primary-hover);
  font-size: 1rem;
}
```

- [ ] **Step 2: Restyle ChatPage as an assistant panel**

In `web/src/pages/ChatPage.vue`, keep the script structure but change the catch block in `ask()` to friendly provider copy:

```ts
  } catch (e) {
    const message = e instanceof Error && e.message.includes('config required')
      ? 'Chat providers are not configured yet. Configure LLM and embedding providers, then ask again.'
      : `Error: ${e instanceof Error ? e.message : 'Unknown error'}`
    messages.value.push({ id: ++nextId, role: 'assistant', content: message })
  } finally {
```

Replace the ChatPage template with:

```vue
<template>
  <div class="chat-page">
    <header class="chat-header">
      <div>
        <p class="eyebrow">Assistant</p>
        <h2>Knowledge Chat</h2>
        <p>Ask questions against indexed local notes.</p>
      </div>
      <span class="badge badge-primary">RAG</span>
    </header>

    <section class="card chat-surface">
      <div class="messages-area" ref="chatContainer">
        <div v-if="messages.length === 0 && !loading" class="empty-state">
          <div class="empty-state-icon">AI</div>
          <p>Ask a question about your knowledge base.</p>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message-row', msg.role === 'user' ? 'message-row-user' : '']"
        >
          <div :class="['msg-bubble', msg.role === 'user' ? 'msg-user' : 'msg-assistant']">
            <div class="whitespace-pre-wrap text-sm">{{ msg.content }}</div>
          </div>
        </div>

        <div v-if="loading" class="message-row">
          <div class="msg-assistant msg-bubble">
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-command">
        <input
          v-model="query"
          @keyup.enter="ask"
          class="input"
          placeholder="Ask about your notes..."
          :disabled="loading"
        />
        <button @click="ask" :disabled="loading || !query.trim()" class="btn btn-primary">Send</button>
      </div>
    </section>
  </div>
</template>
```

Replace scoped styles with:

```css
.chat-page {
  max-width: 1120px;
  height: calc(100vh - 64px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.eyebrow {
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.chat-header h2 {
  margin-top: 5px;
  color: var(--color-text);
  font-size: 1.8rem;
  font-weight: 850;
}

.chat-header p:last-child {
  margin-top: 6px;
  color: var(--color-text-muted);
}

.chat-surface {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.message-row {
  display: flex;
  justify-content: flex-start;
}

.message-row-user {
  justify-content: flex-end;
}

.msg-bubble {
  max-width: min(760px, 82%);
  padding: 12px 15px;
  border-radius: 10px;
  line-height: 1.65;
}

.msg-user {
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  color: #fff;
}

.msg-assistant {
  background: var(--color-surface-tinted);
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.chat-command {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid var(--color-border);
  background: rgba(248, 251, 255, 0.88);
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: typing-bounce 1.4s ease-in-out infinite both;
}

.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.16s; }
.typing-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
```

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 4: Commit**

```powershell
git add web/src/pages/SearchPage.vue web/src/pages/ChatPage.vue
git commit -m "style: refresh search and chat workspaces"
```

---

### Task 5: Compatibility Pass And Full Verification

**Files:**
- Modify: `web/src/pages/NoteList.vue`
- Modify: `web/src/pages/ManagePage.vue`
- Modify: `web/src/pages/NoteDetail.vue`
- Modify: any dashboard component with broken encoding or hardcoded dark colors found during verification.

- [ ] **Step 1: Replace obvious broken icons/text**

Search for replacement-character style mojibake in frontend source:

```powershell
Select-String -Path web\src\**\*.vue -Pattern '馃|鈴|鈿|路|鍓|灏|澶'
```

For each hit, replace the broken icon or separator with simple ASCII labels:

```vue
<div class="empty-state-icon">...</div>
<span class="badge badge-muted">AI</span>
<span style="color: var(--color-border);">/</span>
```

In `RecentNotes.vue`, replace the broken `formatTime` return strings with:

```ts
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} days ago`
```

- [ ] **Step 2: Adjust remaining pages to shared tokens**

In `NoteList.vue`, ensure filter hover and active states use tokens:

```css
.filter-chip:hover {
  background: var(--color-surface-tinted);
  color: var(--color-text);
}

.filter-chip-active {
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
  font-weight: 700;
}
```

In `ManagePage.vue`, replace the active tab inline color with token colors:

```vue
:style="activeTab === tab.key
  ? { background: 'var(--color-primary)', color: '#fff' }
  : { background: 'transparent', color: 'var(--color-text-muted)' }"
```

In `NoteDetail.vue`, replace broken dot separators with `/` and keep related note cards on `.card`.

- [ ] **Step 3: Run backend tests**

Run:

```powershell
pytest tests/test_api_v1.py -v
```

Expected: all API v1 tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd web
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 5: Run the app for visual verification**

Start the app using the project script:

```powershell
.\scripts\start.ps1
```

Expected: backend and Vite dev server start, with the frontend available at the configured local URL. If this script fails because the user's local uncommitted startup-script changes are in progress, do not revert them; use `cd web; npm run dev` for frontend-only visual verification.

- [ ] **Step 6: Inspect core pages**

Open these routes:

```text
/
/search
/chat
/notes
/manage
```

Check:

- Main workspace is bright, not heavy.
- Sidebar is dark but not the dominant visual area.
- No text overlaps or spills out of buttons/cards.
- Search and Chat loading/empty states look intentional.
- Overview activity failure, if present, does not break the page.

- [ ] **Step 7: Commit**

```powershell
git add web/src/pages/NoteList.vue web/src/pages/ManagePage.vue web/src/pages/NoteDetail.vue web/src/components
git commit -m "style: align secondary pages with control center theme"
```

---

### Task 6: Final Review And Handoff

**Files:**
- Review all changed files.

- [ ] **Step 1: Review git diff**

Run:

```powershell
git status --short
git diff --stat
git diff
```

Expected: only intentional files from this plan are modified. Existing unrelated user changes such as startup scripts remain untouched unless the implementation explicitly needed them.

- [ ] **Step 2: Run final verification**

Run:

```powershell
pytest tests/test_api_v1.py -v
cd web
npm run build
```

Expected: tests pass and frontend build succeeds.

- [ ] **Step 3: Final commit if verification changes were made**

If Step 1 or Step 2 required fixes, commit them:

```powershell
git add <fixed-files>
git commit -m "fix: polish modern tech UI verification issues"
```

If no fixes were needed, do not create an empty commit.

- [ ] **Step 4: Summarize outcome**

Prepare a short handoff that includes:

- The new API route.
- The refreshed pages.
- The verification commands and results.
- Any known local constraints, such as existing unrelated uncommitted files.

