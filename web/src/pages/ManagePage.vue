<template>
  <div>
    <h2 class="text-2xl font-bold mb-6" style="color: var(--color-text);">Manage</h2>

    <div v-if="loading" class="empty-state">
      <div class="empty-state-icon">...</div>
      <p>Loading...</p>
    </div>

    <div v-else-if="error" class="empty-state">
      <div class="empty-state-icon">!</div>
      <p style="color: var(--color-danger);">{{ error }}</p>
    </div>

    <template v-else>
      <div class="flex gap-1 mb-6 border-b" style="border-color: var(--color-border);">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          class="px-4 py-2 text-sm font-medium rounded-t transition-colors border-0 cursor-pointer"
          :style="activeTab === tab.key
            ? { background: 'var(--color-primary)', color: '#fff' }
            : { background: 'transparent', color: 'var(--color-text-muted)' }"
        >{{ tab.label }}</button>
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
            :to="`/source/${encodeURIComponent(p.name)}`"
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
const activeTab = ref('source')
const categoriesWithCount = ref<Array<{ name: string; count: number }>>([])
const tags = ref<string[]>([])
const sourceProjects = ref<Array<{ name: string; count: number }>>([])
const indexHealth = ref({ notes_count: 0, vectors_count: 0, coverage: 0 })

const tabs = [
  { key: 'category', label: 'By Category' },
  { key: 'tag', label: 'By Tag' },
  { key: 'source', label: 'By Source' },
  { key: 'index', label: 'Index' },
]

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

async function handleReindex() {
  try { await api.triggerIndex() } catch (_) { /* silent */ }
}
</script>
