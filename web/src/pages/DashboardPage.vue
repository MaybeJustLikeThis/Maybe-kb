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
