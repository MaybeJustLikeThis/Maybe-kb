# P1 Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `Manage` into an actionable maintenance control center with system health, visible index rebuild feedback, and readable source labels.

**Architecture:** Keep the current Vue single-page structure and reuse the existing `/api/v1/health`, dashboard, taxonomy, sources, and index rebuild API methods. `ManagePage.vue` becomes the state owner for health, taxonomy, source rows, index metrics, rebuild progress, and notices. Focused static tests guard the product contract without adding a browser test harness.

**Tech Stack:** Vue 3 Composition API, TypeScript, Vite, Python pytest static checks.

---

## File Structure

- Create `tests/test_manage_control_center.py`
  - Static product-contract tests for `ManagePage.vue`.
- Modify `web/src/pages/ManagePage.vue`
  - Add the Health tab, source-label composition, rebuild feedback, and reusable refresh functions.
- No backend changes are planned.

---

### Task 1: Add Manage Control Center Contract Tests

**Files:**
- Create: `tests/test_manage_control_center.py`

- [ ] **Step 1: Write failing static tests**

Create `tests/test_manage_control_center.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_manage_defaults_to_health_tab_and_renders_system_health() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "import SystemHealth from '../components/SystemHealth.vue'" in manage
    assert "const activeTab = ref('health')" in manage
    assert "{ key: 'health', label: 'Health' }" in manage
    assert 'v-if="activeTab === \'health\'"' in manage
    assert "<SystemHealth" in manage
    assert ':health="health"' in manage
    assert ':rebuilding="reindexing"' in manage
    assert '@rebuild="handleReindex"' in manage


def test_manage_loads_health_and_source_config() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "api.getHealth()" in manage
    assert "api.getSources()" in manage
    assert "loadHealthData" in manage
    assert "refreshManageData" in manage
    assert "sourceRows" in manage
    assert "sourceConfigByName" in manage


def test_manage_rebuild_feedback_is_visible_and_stateful() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "const reindexing = ref(false)" in manage
    assert "const notice = ref" in manage
    assert "Index rebuilt" in manage
    assert "Index rebuild failed" in manage
    assert "Rebuilding..." in manage
    assert "notice-success" in manage
    assert "notice-error" in manage
    assert "await api.triggerIndex()" in manage


def test_manage_sources_use_configured_labels_and_descriptions() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "source.label || source.name" in manage
    assert "source.description" in manage
    assert "source.icon" in manage
    assert "source.count" in manage
    assert "`/source/${encodeURIComponent(source.name)}`" in manage
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
py -m pytest tests/test_manage_control_center.py -q
```

Expected: FAIL because `ManagePage.vue` does not import `SystemHealth`, does not default to the health tab, does not call `api.getHealth()`/`api.getSources()`, and rebuild feedback copy is absent.

- [ ] **Step 3: Commit the failing tests**

Do not commit yet if your workflow prefers red/green in one commit. If committing red tests separately, use:

```powershell
git add tests/test_manage_control_center.py
git commit -m "test: specify manage control center behavior"
```

Expected: commit succeeds only if the project allows red-test commits on feature branches.

---

### Task 2: Upgrade ManagePage Data Model And Template

**Files:**
- Modify: `web/src/pages/ManagePage.vue`

- [ ] **Step 1: Replace the template with control-center structure**

In `web/src/pages/ManagePage.vue`, replace the current template with this structure:

```vue
<template>
  <div class="manage-page">
    <div class="manage-header">
      <div>
        <p class="eyebrow">Operations</p>
        <h2>Manage</h2>
        <p>Check readiness, maintain the local index, and browse configured source groups.</p>
      </div>
      <button class="btn btn-outline" :disabled="loading" @click="refreshManageData">Refresh</button>
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
      <div
        v-if="notice"
        :class="['manage-notice', notice.type === 'success' ? 'notice-success' : 'notice-error']"
      >
        {{ notice.message }}
      </div>

      <div class="manage-tabs" role="tablist" aria-label="Manage sections">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="['manage-tab', activeTab === tab.key ? 'manage-tab-active' : '']"
          :aria-pressed="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <section v-if="activeTab === 'health'" class="manage-section">
        <SystemHealth
          v-if="health"
          :health="health"
          :rebuilding="reindexing"
          @rebuild="handleReindex"
        />
        <div v-else class="empty-state compact-empty">
          <div class="empty-state-icon">!</div>
          <p>{{ healthError || 'System Health is unavailable.' }}</p>
        </div>
      </section>

      <section v-if="activeTab === 'source'" class="manage-section">
        <div v-if="sourceRows.length === 0" class="empty-state compact-empty">
          <div class="empty-state-icon">SC</div>
          <p>No sources configured yet.</p>
        </div>
        <div v-else class="source-grid">
          <router-link
            v-for="source in sourceRows"
            :key="source.name"
            :to="`/source/${encodeURIComponent(source.name)}`"
            class="card source-row"
          >
            <span class="source-icon">{{ source.icon || source.name.slice(0, 2).toUpperCase() }}</span>
            <div>
              <strong>{{ source.label || source.name }}</strong>
              <p>{{ source.description || 'Configured knowledge source' }}</p>
            </div>
            <span class="source-count">{{ source.count }} notes</span>
          </router-link>
        </div>
      </section>

      <section v-if="activeTab === 'category'" class="manage-section">
        <CategoryList :categories="categoriesWithCount" />
      </section>

      <section v-if="activeTab === 'tag'" class="manage-section">
        <TagCloud :tags="tags" />
      </section>

      <section v-if="activeTab === 'index'" class="manage-section">
        <div class="index-grid">
          <div class="card metric-card">
            <strong :style="{ color: indexHealth.coverage > 0 ? '#047857' : '#b91c1c' }">
              {{ Math.round(indexHealth.coverage * 100) }}%
            </strong>
            <span>Coverage</span>
          </div>
          <div class="card metric-card">
            <strong>{{ indexHealth.notes_count }}</strong>
            <span>Notes</span>
          </div>
          <div class="card metric-card">
            <strong>{{ indexHealth.vectors_count }}</strong>
            <span>Vectors</span>
          </div>
        </div>
        <button
          class="btn btn-primary rebuild-action"
          :disabled="reindexing"
          @click="handleReindex"
        >
          {{ reindexing ? 'Rebuilding...' : 'Rebuild index' }}
        </button>
      </section>
    </template>
  </div>
</template>
```

- [ ] **Step 2: Replace script with explicit data loaders**

Replace the current `<script setup lang="ts">` block with:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type SourceItem, type SystemHealth as SystemHealthData } from '../api'
import CategoryList from '../components/CategoryList.vue'
import SystemHealth from '../components/SystemHealth.vue'
import TagCloud from '../components/TagCloud.vue'

type Notice = {
  type: 'success' | 'error'
  message: string
}

type SourceRow = {
  name: string
  label: string
  description: string
  icon: string
  count: number
}

const loading = ref(true)
const error = ref<string | null>(null)
const healthError = ref<string | null>(null)
const activeTab = ref('health')
const categoriesWithCount = ref<Array<{ name: string; count: number }>>([])
const tags = ref<string[]>([])
const sourceProjects = ref<Array<{ name: string; count: number; label?: string | null }>>([])
const sourceConfig = ref<SourceItem[]>([])
const indexHealth = ref({ notes_count: 0, vectors_count: 0, coverage: 0 })
const health = ref<SystemHealthData | null>(null)
const reindexing = ref(false)
const notice = ref<Notice | null>(null)

const tabs = [
  { key: 'health', label: 'Health' },
  { key: 'source', label: 'Sources' },
  { key: 'category', label: 'Categories' },
  { key: 'tag', label: 'Tags' },
  { key: 'index', label: 'Index' },
]

const sourceConfigByName = computed(() => {
  const lookup = new Map<string, SourceItem>()
  for (const source of sourceConfig.value) {
    lookup.set(source.name, source)
  }
  return lookup
})

const sourceRows = computed<SourceRow[]>(() => {
  const rows = new Map<string, SourceRow>()

  for (const source of sourceConfig.value) {
    rows.set(source.name, {
      name: source.name,
      label: source.label || source.name,
      description: source.description || '',
      icon: source.icon || '',
      count: 0,
    })
  }

  for (const project of sourceProjects.value) {
    const source = sourceConfigByName.value.get(project.name)
    rows.set(project.name, {
      name: project.name,
      label: source?.label || project.label || project.name,
      description: source?.description || '',
      icon: source?.icon || '',
      count: project.count,
    })
  }

  return Array.from(rows.values()).sort((a, b) => a.name.localeCompare(b.name))
})

async function loadDashboardData() {
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
}

async function loadHealthData() {
  try {
    health.value = await api.getHealth()
    healthError.value = null
  } catch (e) {
    health.value = null
    healthError.value = e instanceof Error ? e.message : 'Failed to load System Health'
  }
}

async function loadSourceConfig() {
  try {
    sourceConfig.value = await api.getSources()
  } catch {
    sourceConfig.value = []
  }
}

async function refreshManageData() {
  loading.value = true
  error.value = null
  try {
    await Promise.all([
      loadDashboardData(),
      loadHealthData(),
      loadSourceConfig(),
    ])
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load'
  } finally {
    loading.value = false
  }
}

async function refreshOperationalData() {
  await Promise.all([
    loadDashboardData(),
    loadHealthData(),
    loadSourceConfig(),
  ])
}

async function handleReindex() {
  if (reindexing.value) return

  reindexing.value = true
  notice.value = null
  try {
    const result = await api.triggerIndex()
    notice.value = {
      type: 'success',
      message: `Index rebuilt: ${result.indexed} notes, ${result.vectors} vectors.`,
    }
    await refreshOperationalData()
  } catch (e) {
    notice.value = {
      type: 'error',
      message: `Index rebuild failed: ${e instanceof Error ? e.message : 'Unknown error'}`,
    }
  } finally {
    reindexing.value = false
  }
}

onMounted(() => {
  refreshManageData()
})
</script>
```

- [ ] **Step 3: Add scoped styles**

Add this `<style scoped>` block at the end of `ManagePage.vue`:

```vue
<style scoped>
.manage-page {
  max-width: 1180px;
  margin: 0 auto;
}

.manage-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
  padding: 22px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.manage-header h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 2rem;
  font-weight: 850;
}

.manage-header p {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  line-height: 1.55;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.manage-notice {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  font-size: 0.88rem;
  font-weight: 760;
}

.notice-success {
  border: 1px solid rgba(16, 185, 129, 0.24);
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.notice-error {
  border: 1px solid rgba(239, 68, 68, 0.24);
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}

.manage-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
}

.manage-tab {
  min-height: 34px;
  padding: 7px 12px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 800;
}

.manage-tab-active {
  border-color: rgba(8, 145, 178, 0.2);
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
}

.manage-section {
  min-width: 0;
}

.compact-empty {
  min-height: 220px;
}

.source-grid {
  display: grid;
  gap: 12px;
}

.source-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  color: inherit;
  text-decoration: none;
}

.source-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
  font-size: 0.76rem;
  font-weight: 900;
}

.source-row strong {
  color: var(--color-text);
  font-size: 0.94rem;
}

.source-row p {
  margin: 3px 0 0;
  color: var(--color-text-muted);
  font-size: 0.82rem;
  line-height: 1.45;
}

.source-count {
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 760;
  white-space: nowrap;
}

.index-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.metric-card {
  text-align: center;
}

.metric-card strong,
.metric-card span {
  display: block;
}

.metric-card strong {
  color: var(--color-text);
  font-size: 2rem;
  font-weight: 850;
}

.metric-card span {
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 760;
}

.rebuild-action {
  min-width: 150px;
}

@media (max-width: 720px) {
  .manage-header {
    align-items: stretch;
    flex-direction: column;
  }

  .source-row,
  .index-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .source-count {
    white-space: normal;
  }
}
</style>
```

- [ ] **Step 4: Run Manage contract tests**

Run:

```powershell
py -m pytest tests/test_manage_control_center.py -q
```

Expected: PASS.

- [ ] **Step 5: Run adjacent static tests**

Run:

```powershell
py -m pytest tests/test_web_health.py tests/test_product_copy.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the implementation**

Run:

```powershell
git add web/src/pages/ManagePage.vue tests/test_manage_control_center.py
git commit -m "feat: make manage an actionable control center"
```

Expected: commit succeeds.

---

### Task 3: Build And Regression Verification

**Files:**
- No planned file edits.

- [ ] **Step 1: Run focused verification**

Run:

```powershell
py -m pytest tests/test_manage_control_center.py tests/test_web_health.py tests/test_product_copy.py tests/test_health.py tests/test_api_v1.py::test_v1_health_returns_system_readiness -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run from `web/`:

```powershell
npm run build
```

Expected: exit code 0.

- [ ] **Step 3: Run full Python test suite**

Run:

```powershell
py -m pytest -q --durations=20
```

Expected: PASS. On this machine, the full suite may take about 4 minutes.

- [ ] **Step 4: Review final diff**

Run:

```powershell
git status --short
git log -3 --oneline
```

Expected:

- Working tree is clean after commits.
- Recent commits include `docs: design p1 control center` and `feat: make manage an actionable control center`.

---

## Self-Review Checklist

- Spec coverage:
  - Health tab and `SystemHealth` reuse: Task 2.
  - Rebuild feedback and refresh: Task 2.
  - Source labels/descriptions/icons with counts: Task 2.
  - Static tests: Task 1.
  - Build/full regression: Task 3.
- No backend endpoint added.
- Import flow and large Obsidian-first redesign remain out of scope.
- No placeholders or deferred implementation steps.
