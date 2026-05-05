<template>
  <div>
    <h2 class="text-2xl font-bold mb-4">Search</h2>

    <div class="mb-6">
      <input
        v-model="query"
        @keyup.enter="search"
        class="w-full p-3 border rounded-lg text-lg outline-none focus:ring-2 focus:ring-blue-300"
        placeholder="Search notes..."
        autofocus
      />
    </div>

    <div v-if="searching" class="text-gray-500">Searching...</div>

    <div v-else-if="results.length > 0">
      <p class="text-sm text-gray-500 mb-4">{{ results.length }} results for "{{ lastQuery }}"</p>
      <ul class="space-y-3">
        <li v-for="note in results" :key="note.file_id">
          <router-link
            :to="`/note/${encodeURIComponent(note.file_id)}`"
            class="block bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow"
          >
            <h3 class="font-semibold text-lg">{{ note.title }}</h3>
            <div class="flex gap-2 mt-1">
              <span v-if="note.category" class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{{ note.category }}</span>
              <span v-for="tag in note.tags" :key="tag" class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{{ tag }}</span>
            </div>
            <p v-if="note.description" class="text-sm text-gray-500 mt-2">{{ note.description }}</p>
          </router-link>
        </li>
      </ul>
    </div>

    <div v-else-if="lastQuery" class="text-gray-500">No results found for "{{ lastQuery }}".</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api, type Note } from '../api'

const query = ref('')
const lastQuery = ref('')
const results = ref<Note[]>([])
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
