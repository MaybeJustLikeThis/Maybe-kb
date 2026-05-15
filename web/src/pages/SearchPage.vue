<template>
  <div>
    <h2 class="text-2xl font-bold mb-5" style="color: var(--color-text);">Search</h2>

    <!-- Search input with icon -->
    <div class="relative mb-6">
      <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-lg" style="color: var(--color-text-muted);">🔍</span>
      <input
        v-model="query"
        @keyup.enter="search"
        class="input pl-10 text-base"
        placeholder="Search notes..."
        autofocus
      />
    </div>

    <!-- Loading -->
    <div v-if="searching" class="empty-state">
      <div class="empty-state-icon">⏳</div>
      <p>Searching...</p>
    </div>

    <!-- Results -->
    <div v-else-if="results.length > 0">
      <p class="text-sm mb-4" style="color: var(--color-text-muted);">
        {{ results.length }} result{{ results.length !== 1 ? 's' : '' }} for "{{ lastQuery }}"
      </p>
      <ul class="space-y-2">
        <li v-for="result in results" :key="result.note.file_id">
          <router-link
            :to="`/note/${encodeURIComponent(result.note.file_id)}`"
            class="card block"
          >
            <h3 class="font-semibold" style="color: var(--color-text);">{{ result.note.title }}</h3>
            <div class="flex flex-wrap gap-1.5 mt-1.5">
              <span v-if="result.note.category" class="badge badge-primary">{{ result.note.category }}</span>
              <span v-for="tag in result.note.tags" :key="tag" class="badge badge-muted">{{ tag }}</span>
            </div>
            <p v-if="result.note.description" class="text-sm mt-2" style="color: var(--color-text-secondary);">{{ result.note.description }}</p>
          </router-link>
        </li>
      </ul>
    </div>

    <!-- No results -->
    <div v-else-if="lastQuery" class="empty-state">
      <div class="empty-state-icon">🔎</div>
      <p>No results found for "{{ lastQuery }}".</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api, type SearchResult } from '../api'

const query = ref('')
const lastQuery = ref('')
const results = ref<SearchResult[]>([])
const searching = ref(false)

async function search() {
  const q = query.value.trim()
  if (!q) return

  searching.value = true
  lastQuery.value = q
  try {
    results.value = await api.search(q)
  } finally {
    searching.value = false
  }
}
</script>
