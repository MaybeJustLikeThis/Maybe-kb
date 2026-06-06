<template>
  <div class="manage-page">
    <section class="manage-header">
      <div>
        <p class="eyebrow">Operations</p>
        <h2>Manage Control Center</h2>
        <p class="header-copy">Monitor local health, sources, taxonomy, and search index maintenance.</p>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="btn btn-ghost"
          :disabled="loading"
          @click="refreshManageData"
        >
          Refresh
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="reindexing"
          @click="handleReindex"
        >
          {{ reindexing ? 'Rebuilding...' : 'Rebuild Index' }}
        </button>
      </div>
    </section>

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
        :class="['notice', notice.kind === 'success' ? 'notice-success' : 'notice-error']"
      >
        {{ notice.message }}
      </div>

      <div class="manage-tabs" role="tablist" aria-label="Manage sections">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.key"
          :class="['tab-button', { active: activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <section v-if="activeTab === 'health'" class="tab-panel health-panel">
        <div v-if="healthError" class="inline-error">
          {{ healthError }}
        </div>
        <SystemHealth
          v-if="health"
          :health="health"
          :rebuilding="reindexing"
          @rebuild="handleReindex"
        />
        <div v-else-if="!healthError" class="empty-state compact">
          <div class="empty-state-icon">...</div>
          <p>Loading health...</p>
        </div>
      </section>

      <section v-if="activeTab === 'source'" class="tab-panel">
        <div v-if="sourceConfigError" class="inline-error source-config-warning">
          Source config unavailable: {{ sourceConfigError }}
        </div>
        <div class="source-grid">
          <router-link
            v-for="source in sourceRows"
            :key="source.name"
            :to="`/source/${encodeURIComponent(source.name)}`"
            class="source-row"
          >
            <span class="source-icon">{{ source.icon }}</span>
            <span class="source-main">
              <span class="source-title">{{ source.label || source.name }}</span>
              <span class="source-description">{{ source.description }}</span>
            </span>
            <span class="source-count">
              <strong>{{ source.count }}</strong>
              <span>notes</span>
            </span>
          </router-link>
        </div>
      </section>

      <section v-if="activeTab === 'category'" class="tab-panel">
        <CategoryList :categories="categoriesWithCount" />
      </section>

      <section v-if="activeTab === 'tag'" class="tab-panel">
        <TagCloud :tags="tags" />
      </section>

      <section v-if="activeTab === 'index'" class="tab-panel">
        <div class="index-grid">
          <div class="index-metric">
            <strong :class="indexHealth.coverage > 0 ? 'metric-good' : 'metric-bad'">
              {{ Math.round(indexHealth.coverage * 100) }}%
            </strong>
            <span>Coverage</span>
          </div>
          <div class="index-metric">
            <strong>{{ indexHealth.notes_count }}</strong>
            <span>Files</span>
          </div>
          <div class="index-metric">
            <strong>{{ indexHealth.vectors_count }}</strong>
            <span>Vectors</span>
          </div>
        </div>
        <button
          type="button"
          class="btn btn-ghost index-action"
          :disabled="reindexing"
          @click="handleReindex"
        >
          {{ reindexing ? 'Rebuilding...' : 'Rebuild Full Index' }}
        </button>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type SourceItem, type SystemHealth as SystemHealthData } from '../api'
import CategoryList from '../components/CategoryList.vue'
import SystemHealth from '../components/SystemHealth.vue'
import TagCloud from '../components/TagCloud.vue'

type Notice = {
  kind: 'success' | 'error'
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
const activeTab = ref('health')
const categoriesWithCount = ref<Array<{ name: string; count: number }>>([])
const tags = ref<string[]>([])
const sourceProjects = ref<Array<{ name: string; count: number }>>([])
const sourceConfig = ref<SourceItem[]>([])
const sourceConfigError = ref<string | null>(null)
const indexHealth = ref({ notes_count: 0, vectors_count: 0, coverage: 0 })
const health = ref<SystemHealthData | null>(null)
const healthError = ref<string | null>(null)
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
  const byName = new Map<string, SourceItem>()
  for (const source of sourceConfig.value) {
    byName.set(source.name, source)
  }
  return byName
})

const sourceRows = computed<SourceRow[]>(() => {
  const counts = new Map(sourceProjects.value.map((source) => [source.name, source.count]))
  const names = new Set<string>([
    ...sourceConfig.value.map((source) => source.name),
    ...sourceProjects.value.map((source) => source.name),
  ])

  return Array.from(names)
    .map((name) => {
      const configured = sourceConfigByName.value.get(name)
      return {
        name,
        label: configured?.label || name,
        description: configured?.description || 'Unconfigured source project',
        icon: configured?.icon || 'SRC',
        count: counts.get(name) ?? 0,
      }
    })
    .sort((a, b) => (
      (b.count - a.count)
      || (a.label || a.name).localeCompare(b.label || b.name)
      || a.name.localeCompare(b.name)
    ))
})

onMounted(() => {
  refreshManageData()
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

async function loadHealthData(options?: { throwOnError?: boolean }) {
  healthError.value = null
  try {
    health.value = await api.getHealth()
  } catch (e) {
    health.value = null
    healthError.value = e instanceof Error ? e.message : 'Failed to load health'
    if (options?.throwOnError) throw e
  }
}

async function loadSourceConfig() {
  sourceConfigError.value = null
  try {
    sourceConfig.value = await api.getSources()
  } catch (e) {
    sourceConfigError.value = e instanceof Error ? e.message : 'Failed to load source config'
  }
}

async function refreshManageData() {
  loading.value = true
  error.value = null
  try {
    await Promise.all([
      loadDashboardData(),
      loadSourceConfig(),
      loadHealthData(),
    ])
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load manage data'
  } finally {
    loading.value = false
  }
}

async function refreshOperationalData() {
  await Promise.all([
    loadDashboardData(),
    loadHealthData({ throwOnError: true }),
  ])
}

async function handleReindex() {
  if (reindexing.value) return

  reindexing.value = true
  notice.value = null
  const previousOperationalData = {
    categoriesWithCount: categoriesWithCount.value,
    tags: tags.value,
    sourceProjects: sourceProjects.value,
    indexHealth: indexHealth.value,
    health: health.value,
  }
  try {
    const result = await api.triggerIndex()
    try {
      await refreshOperationalData()
    } catch (e) {
      categoriesWithCount.value = previousOperationalData.categoriesWithCount
      tags.value = previousOperationalData.tags
      sourceProjects.value = previousOperationalData.sourceProjects
      indexHealth.value = previousOperationalData.indexHealth
      health.value = previousOperationalData.health
      notice.value = {
        kind: 'error',
        message: `Index rebuilt, but refresh failed: ${e instanceof Error ? e.message : 'Unknown error'}`,
      }
      return
    }
    notice.value = {
      kind: 'success',
      message: `Index rebuilt: ${result.indexed} notes, ${result.vectors} vectors.`,
    }
  } catch (e) {
    notice.value = {
      kind: 'error',
      message: `Index rebuild failed: ${e instanceof Error ? e.message : 'Unknown error'}`,
    }
    return
  } finally {
    reindexing.value = false
  }
}
</script>

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
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--color-border);
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.manage-header h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 2rem;
  font-weight: 850;
  line-height: 1.1;
}

.header-copy {
  max-width: 640px;
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.55;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.notice {
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid;
  border-radius: var(--radius-sm);
  font-size: 0.86rem;
  font-weight: 720;
}

.notice-success {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.notice-error {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.09);
  color: #b91c1c;
}

.manage-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 18px;
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
}

.tab-button {
  flex: 0 0 auto;
  min-height: 38px;
  padding: 8px 12px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 760;
}

.tab-button.active {
  border-bottom-color: var(--color-primary);
  color: var(--color-primary-hover);
}

.tab-panel {
  min-width: 0;
}

.health-panel {
  max-width: 760px;
}

.inline-error {
  padding: 12px 14px;
  border: 1px solid rgba(239, 68, 68, 0.35);
  border-radius: var(--radius-sm);
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
  font-size: 0.9rem;
  font-weight: 720;
}

.empty-state.compact {
  min-height: 180px;
}

.source-grid {
  display: grid;
  gap: 10px;
}

.source-config-warning {
  margin-bottom: 12px;
}

.source-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 74px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: inherit;
  text-decoration: none;
  box-shadow: var(--shadow-sm);
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.source-row:hover {
  border-color: var(--color-primary);
  transform: translateY(-1px);
}

.source-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--color-surface-tinted);
  color: var(--color-primary-hover);
  font-size: 0.78rem;
  font-weight: 850;
  text-align: center;
}

.source-main {
  min-width: 0;
}

.source-title,
.source-description {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-title {
  color: var(--color-text);
  font-size: 0.95rem;
  font-weight: 820;
}

.source-description {
  margin-top: 3px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.source-count {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 720;
}

.source-count strong {
  color: var(--color-text);
  font-size: 1.15rem;
  font-weight: 850;
}

.index-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.index-metric {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.index-metric strong,
.index-metric span {
  display: block;
}

.index-metric strong {
  overflow: hidden;
  color: var(--color-text);
  font-size: 1.85rem;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.index-metric span {
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 0.76rem;
  font-weight: 740;
}

.metric-good {
  color: #047857 !important;
}

.metric-bad {
  color: #b91c1c !important;
}

.index-action {
  min-width: 170px;
}

@media (max-width: 720px) {
  .manage-header {
    align-items: stretch;
    flex-direction: column;
  }

  .manage-header .btn,
  .index-action {
    width: 100%;
  }

  .header-actions {
    flex-direction: column;
  }

  .source-row {
    grid-template-columns: 40px minmax(0, 1fr);
  }

  .source-count {
    grid-column: 2;
    align-items: flex-start;
  }

  .index-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
