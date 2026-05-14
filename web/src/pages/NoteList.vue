<template>
  <div>
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold" style="color: var(--color-text);">Notes</h2>
      <router-link
        to="/note/new"
        class="btn btn-primary"
      >New Note</router-link>
    </div>

    <div class="flex gap-8">
      <!-- Filters sidebar -->
      <div class="w-52 flex-shrink-0">
        <!-- Categories -->
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

        <!-- Tags -->
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

      <!-- Notes list -->
      <div class="flex-1">
        <div v-if="loading" class="empty-state">
          <div class="empty-state-icon">⏳</div>
          <p>Loading...</p>
        </div>

        <div v-else-if="notes.length === 0" class="empty-state">
          <div class="empty-state-icon">📝</div>
          <p>No notes yet.</p>
          <p>
            <router-link to="/note/new" style="color: var(--color-primary);" class="hover:underline text-sm">Create your first note</router-link>
          </p>
        </div>

        <ul v-else class="space-y-2">
          <li v-for="note in notes" :key="note.file_id">
            <router-link
              :to="`/note/${encodeURIComponent(note.file_id)}`"
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
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api, type Note } from '../api'

const route = useRoute()
const notes = ref<Note[]>([])
const categories = ref<string[]>([])
const tags = ref<string[]>([])
const selectedCategory = ref('')
const selectedTag = ref('')
const loading = ref(false)
let syncingFromRoute = false

function queryValue(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function syncFiltersFromRoute() {
  syncingFromRoute = true
  selectedCategory.value = queryValue(route.query.category)
  selectedTag.value = queryValue(route.query.tag)
  syncingFromRoute = false
}

async function load() {
  loading.value = true
  try {
    const params: { category?: string; tag?: string } = {}
    if (selectedCategory.value) params.category = selectedCategory.value
    if (selectedTag.value) params.tag = selectedTag.value
    notes.value = await api.listNotes(params)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  syncFiltersFromRoute()
  const [cats, tgs] = await Promise.all([api.getCategories(), api.getTags()])
  categories.value = cats.categories
  tags.value = tgs.tags
  load()
})

watch([selectedCategory, selectedTag], () => {
  if (!syncingFromRoute) load()
})
watch(() => route.query, () => {
  syncFiltersFromRoute()
  load()
})
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
  background: #f1f5f9;
  color: var(--color-text);
}
.filter-chip-active {
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: 500;
}
</style>
