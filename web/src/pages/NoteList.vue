<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">Notes</h2>
      <router-link
        to="/note/new"
        class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
      >New Note</router-link>
    </div>

    <div class="flex gap-6">
      <!-- Filters sidebar -->
      <div class="w-56 flex-shrink-0">
        <div class="mb-4">
          <h3 class="font-semibold mb-2 text-sm text-gray-500">CATEGORIES</h3>
          <ul class="space-y-1">
            <li>
              <button
                @click="selectedCategory = ''"
                :class="['text-sm w-full text-left py-1 px-2 rounded', !selectedCategory ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100']"
              >All</button>
            </li>
            <li v-for="cat in categories" :key="cat">
              <button
                @click="selectedCategory = cat"
                :class="['text-sm w-full text-left py-1 px-2 rounded', selectedCategory === cat ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100']"
              >{{ cat }}</button>
            </li>
          </ul>
        </div>

        <div>
          <h3 class="font-semibold mb-2 text-sm text-gray-500">TAGS</h3>
          <ul class="space-y-1">
            <li>
              <button
                @click="selectedTag = ''"
                :class="['text-sm w-full text-left py-1 px-2 rounded', !selectedTag ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100']"
              >All</button>
            </li>
            <li v-for="tag in tags" :key="tag">
              <button
                @click="selectedTag = tag"
                :class="['text-sm w-full text-left py-1 px-2 rounded', selectedTag === tag ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100']"
              >{{ tag }}</button>
            </li>
          </ul>
        </div>
      </div>

      <!-- Notes list -->
      <div class="flex-1">
        <div v-if="loading" class="text-gray-500">Loading...</div>
        <div v-else-if="notes.length === 0" class="text-gray-500">No notes found.</div>
        <ul v-else class="space-y-3">
          <li v-for="note in notes" :key="note.file_id">
            <router-link
              :to="`/note/${encodeURIComponent(note.file_id)}`"
              class="block bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow"
            >
              <h3 class="font-semibold text-lg">{{ note.title }}</h3>
              <div class="flex gap-2 mt-1">
                <span v-if="note.category" class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                  {{ note.category }}
                </span>
                <span v-for="tag in note.tags" :key="tag" class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {{ tag }}
                </span>
              </div>
              <p v-if="note.description" class="text-sm text-gray-500 mt-2">{{ note.description }}</p>
              <p class="text-xs text-gray-400 mt-2">{{ note.updated_at || note.created_at }}</p>
            </router-link>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { api, type Note } from '../api'

const notes = ref<Note[]>([])
const categories = ref<string[]>([])
const tags = ref<string[]>([])
const selectedCategory = ref('')
const selectedTag = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const params: any = {}
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

watch([selectedCategory, selectedTag], load)
</script>
