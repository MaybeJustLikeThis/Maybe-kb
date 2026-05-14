<template>
  <div>
    <h2 class="text-2xl font-bold mb-6" style="color: var(--color-text);">Manage</h2>

    <div v-if="loading" class="empty-state">
      <div class="empty-state-icon">⏳</div>
      <p>Loading...</p>
    </div>

    <div v-else-if="error" class="empty-state">
      <div class="empty-state-icon">⚠️</div>
      <p style="color: #ef4444;">{{ error }}</p>
    </div>

    <template v-else>
      <div class="flex gap-1 mb-6 border-b" style="border-color: var(--color-border);">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          class="px-4 py-2 text-sm font-medium rounded-t transition-colors border-0 cursor-pointer"
          :style="activeTab === tab.key
            ? { background: '#2563eb', color: '#fff' }
            : { background: 'transparent', color: 'var(--color-text-muted)' }"
        >{{ tab.label }}</button>
      </div>

      <!-- Type Tab -->
      <div v-if="activeTab === 'type'">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="lg:col-span-2 space-y-3">
            <router-link
              v-for="t in typeDistribution"
              :key="t.name"
              :to="`/notes?entry_type=${encodeURIComponent(t.name)}`"
              class="card flex items-center gap-4 no-underline hover:opacity-80 transition-opacity"
            >
              <div class="w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0"
                :style="{ background: typeIconBg(t.name) }">{{ typeIcon(t.name) }}</div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-semibold" style="color: var(--color-text);">{{ t.label }}</div>
                <div class="text-xs" style="color: var(--color-text-muted);">{{ t.name }}</div>
                <div class="text-xs mt-1" style="color: var(--color-text-muted);">
                  tags: {{ typeTags[t.name]?.join(', ') || '-' }}
                </div>
              </div>
              <div class="text-right flex-shrink-0">
                <div class="text-xl font-bold" :style="{ color: typeColorHex(t.name) }">{{ t.count }}</div>
                <div class="text-xs" style="color: var(--color-text-muted);">notes</div>
              </div>
            </router-link>
          </div>
          <div class="space-y-4">
            <div class="card">
              <h3 class="section-heading">Quick Create</h3>
              <router-link to="/notes" class="btn btn-ghost text-sm no-underline text-center block w-full">New Note</router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- Category Tab -->
      <div v-if="activeTab === 'category'">
        <CategoryList :categories="categoriesWithCount" />
      </div>

      <!-- Tag Tab -->
      <div v-if="activeTab === 'tag'">
        <TagCloud :tags="tags" />
      </div>

      <!-- Source Tab -->
      <div v-if="activeTab === 'source'">
        <div class="space-y-3">
          <router-link
            v-for="p in sourceProjects"
            :key="p.name"
            :to="`/notes?source_project=${encodeURIComponent(p.name)}`"
            class="card flex items-center justify-between no-underline hover:opacity-80"
          >
            <div>
              <div class="text-sm font-semibold" style="color: var(--color-text);">{{ p.name }}</div>
              <div class="text-xs" style="color: var(--color-text-muted);">{{ p.count }} notes</div>
            </div>
            <span class="text-sm" style="color: var(--color-text-muted);">&rarr;</span>
          </router-link>
        </div>
      </div>

      <!-- Index Tab -->
      <div v-if="activeTab === 'index'">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div class="card text-center">
            <div class="text-3xl font-bold" :style="{ color: indexHealth.coverage > 0 ? '#10b981' : '#ef4444' }">
              {{ Math.round(indexHealth.coverage * 100) }}%
            </div>
            <div class="text-xs mt-1" style="color: var(--color-text-muted);">Coverage</div>
          </div>
          <div class="card text-center">
            <div class="text-3xl font-bold" style="color: var(--color-text);">{{ indexHealth.notes_count }}</div>
            <div class="text-xs mt-1" style="color: var(--color-text-muted);">Files</div>
          </div>
          <div class="card text-center">
            <div class="text-3xl font-bold" style="color: var(--color-text);">{{ indexHealth.vectors_count }}</div>
            <div class="text-xs mt-1" style="color: var(--color-text-muted);">Vectors</div>
          </div>
        </div>
        <button class="btn btn-ghost text-sm" @click="handleReindex">Rebuild Full Index</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import CategoryList from '../components/CategoryList.vue'
import TagCloud from '../components/TagCloud.vue'

const loading = ref(true)
const error = ref<string | null>(null)
const activeTab = ref('type')
const typeDistribution = ref<Array<{ name: string; count: number; label: string }>>([])
const typeTags = ref<Record<string, string[]>>({})
const categoriesWithCount = ref<Array<{ name: string; count: number }>>([])
const tags = ref<string[]>([])
const sourceProjects = ref<Array<{ name: string; count: number }>>([])
const indexHealth = ref({ notes_count: 0, vectors_count: 0, coverage: 0 })

const tabs = [
  { key: 'type', label: 'By Type' },
  { key: 'category', label: 'By Category' },
  { key: 'tag', label: 'By Tag' },
  { key: 'source', label: 'By Source' },
  { key: 'index', label: 'Index' },
]

const typeIconMap: Record<string, string> = {
  'tech-article': 'T', document: 'D', troubleshooting: 'B', 'design-decision': 'A', 'code-snippet': 'C',
}
const typeBgMap: Record<string, string> = {
  'tech-article': 'rgba(59,130,246,0.2)', document: 'rgba(16,185,129,0.2)',
  troubleshooting: 'rgba(245,158,11,0.2)', 'design-decision': 'rgba(236,72,153,0.2)',
  'code-snippet': 'rgba(139,92,246,0.2)',
}
const typeHexMap: Record<string, string> = {
  'tech-article': '#3b82f6', document: '#10b981', troubleshooting: '#f59e0b',
  'design-decision': '#ec4899', 'code-snippet': '#8b5cf6',
}

function typeIcon(name: string) { return typeIconMap[name] || '?' }
function typeIconBg(name: string) { return typeBgMap[name] || 'rgba(100,116,139,0.2)' }
function typeColorHex(name: string) { return typeHexMap[name] || '#94a3b8' }

onMounted(async () => {
  try {
    const [typeData, catData, tagData, srcData, healthData] = await Promise.all([
      api.getTypeDistribution(),
      api.getCategoriesWithCount(),
      api.getTags(),
      api.getSourceProjects(),
      api.getIndexHealth(),
    ])
    typeDistribution.value = typeData.types
    categoriesWithCount.value = catData.categories
    tags.value = tagData.tags
    sourceProjects.value = srcData.projects
    indexHealth.value = healthData

    const tagMap: Record<string, Set<string>> = {}
    for (const t of typeData.types) {
      tagMap[t.name] = new Set()
      try {
        const notes = await api.listNotes({ limit: 30 })
        for (const n of notes) {
          if (n.entry_type === t.name) {
            for (const tg of n.tags) tagMap[t.name].add(tg)
          }
        }
      } catch (_) { /* skip */ }
    }
    for (const [k, v] of Object.entries(tagMap)) {
      typeTags.value[k] = [...v].slice(0, 8)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load'
  } finally {
    loading.value = false
  }
})

async function handleReindex() {
  try { await api.triggerIndex() } catch (_) { /* silent */ }
}
</script>
