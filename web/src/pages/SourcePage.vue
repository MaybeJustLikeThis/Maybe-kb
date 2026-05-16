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
import { useRoute } from 'vue-router'
import { api, type Note } from '../api'

const props = defineProps<{ name: string }>()
const route = useRoute()

const notes = ref<Note[]>([])
const categories = ref<string[]>([])
const tags = ref<string[]>([])
const selectedCategory = ref((route.query.category as string) || '')
const selectedTag = ref((route.query.tag as string) || '')
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
