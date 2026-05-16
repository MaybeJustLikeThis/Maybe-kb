<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold" style="color: var(--color-text);">{{ sourceLabel }}</h2>
      <router-link
        :to="`/note/new?source_project=${props.name}`"
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
              v-for="tag in typeTags" :key="tag"
              @click="selectedTag = tag"
              :class="['filter-chip type-chip', selectedTag === tag ? 'filter-chip-active' : '']"
            >{{ tag.replace('Type-', '') }}</button>
            <button
              v-for="tag in topicTags" :key="tag"
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
                    <span v-for="tag in note.tags" :key="tag" :class="['badge', tag.startsWith('Type-') ? 'badge-type' : 'badge-muted']">{{ tag.startsWith('Type-') ? tag.replace('Type-', '') : tag }}</span>
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
import { ref, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api, type Note } from '../api'

const props = defineProps<{ name: string }>()
const route = useRoute()

const notes = ref<Note[]>([])
const categories = ref<string[]>([])
const tags = ref<string[]>([])
const selectedCategory = ref((route.query.category as string) || '')
const selectedTag = ref((route.query.tag as string) || '')
const loading = ref(true)

const sourceLabel = computed(() => props.name.charAt(0).toUpperCase() + props.name.slice(1))

const typeTags = computed(() => tags.value.filter(t => t.startsWith('Type-')))
const topicTags = computed(() => tags.value.filter(t => !t.startsWith('Type-')))

function extractFilters(ns: Note[]) {
  const catSet = new Set<string>()
  const tagSet = new Set<string>()
  for (const n of ns) {
    if (n.category) catSet.add(n.category)
    for (const t of n.tags) tagSet.add(t)
  }
  categories.value = [...catSet].sort()
  tags.value = [...tagSet].sort()
}

async function load() {
  loading.value = true
  selectedCategory.value = (route.query.category as string) || ''
  selectedTag.value = (route.query.tag as string) || ''
  try {
    const params: { source_project: string; category?: string; tag?: string } = {
      source_project: props.name,
    }
    if (selectedCategory.value) params.category = selectedCategory.value
    if (selectedTag.value) params.tag = selectedTag.value
    const result = await api.listNotes(params)
    notes.value = result
    // Derive filters from unfiltered source notes
    if (!selectedCategory.value && !selectedTag.value) {
      extractFilters(result)
    }
  } finally {
    loading.value = false
  }
}

// Load on mount AND when source name changes
watch(() => props.name, () => load(), { immediate: true })

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

.type-chip {
  color: #2563eb;
  font-weight: 600;
}

.type-chip.filter-chip-active {
  background: #dbeafe;
  color: #1e40af;
}
</style>
