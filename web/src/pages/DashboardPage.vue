<template>
  <div>
    <h2 class="text-2xl font-bold mb-6" style="color: var(--color-text);">Overview</h2>

    <div v-if="loading" class="empty-state">
      <div class="empty-state-icon">⏳</div>
      <p>Loading...</p>
    </div>

    <div v-else-if="error" class="empty-state">
      <div class="empty-state-icon">⚠️</div>
      <p style="color: #ef4444;">{{ error }}</p>
    </div>

    <template v-else>
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <StatCard icon="📄" :value="stats.notesCount" label="Notes" />
        <StatCard icon="📊" :value="stats.typesCount" label="Types" />
        <StatCard icon="📁" :value="stats.categoriesCount" label="Categories" />
        <StatCard icon="🏷" :value="stats.tagsCount" label="Tags" />
        <StatCard icon="📎" :value="stats.attachmentsCount" label="Attachments" />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div class="lg:col-span-2">
          <TypeDistribution :types="typeDistribution" />
        </div>
        <div class="space-y-4">
          <IndexHealth
            :notes-count="indexHealth.notes_count"
            :vectors-count="indexHealth.vectors_count"
            :coverage="indexHealth.coverage"
          />
          <SourceProjects :projects="sourceProjects" />
          <ContentFormatPie :content-types="contentTypes" />
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div>
          <QuickActions @reindex="handleReindex" />
        </div>
        <div class="lg:col-span-2">
          <RecentNotes :notes="recentNotes" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type Note } from '../api'
import StatCard from '../components/StatCard.vue'
import TypeDistribution from '../components/TypeDistribution.vue'
import IndexHealth from '../components/IndexHealth.vue'
import SourceProjects from '../components/SourceProjects.vue'
import ContentFormatPie from '../components/ContentFormatPie.vue'
import QuickActions from '../components/QuickActions.vue'
import RecentNotes from '../components/RecentNotes.vue'

const loading = ref(true)
const error = ref<string | null>(null)
const stats = ref({ notesCount: 0, typesCount: 0, categoriesCount: 0, tagsCount: 0, attachmentsCount: 0 })
const typeDistribution = ref<Array<{ name: string; count: number; label: string }>>([])
const sourceProjects = ref<Array<{ name: string; count: number }>>([])
const contentTypes = ref<Array<{ name: string; count: number }>>([])
const indexHealth = ref({ notes_count: 0, vectors_count: 0, coverage: 0 })
const recentNotes = ref<Note[]>([])

onMounted(async () => {
  try {
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
    stats.value = {
      notesCount: indexData.notes_count,
      typesCount: typeData.types.length,
      categoriesCount: catData.categories.length,
      tagsCount: tagData.tags.length,
      attachmentsCount: attData.count,
    }
    typeDistribution.value = typeData.types
    sourceProjects.value = srcData.projects
    contentTypes.value = ctData.content_types
    indexHealth.value = healthData
    recentNotes.value = notesData
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
  } finally {
    loading.value = false
  }
})

async function handleReindex() {
  try {
    await api.triggerIndex()
  } catch (e) {
    // silent
  }
}
</script>
