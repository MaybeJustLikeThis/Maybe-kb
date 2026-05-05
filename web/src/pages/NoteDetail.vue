<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <router-link to="/" class="text-blue-600 hover:underline">&larr; Back</router-link>
      <div class="flex gap-2">
        <button
          v-if="!isNew"
          @click="deleteNote"
          class="text-red-600 hover:text-red-800 text-sm"
        >Delete</button>
        <button
          @click="save"
          class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >Save</button>
      </div>
    </div>

    <div v-if="loading" class="text-gray-500">Loading...</div>

    <div v-else>
      <input
        v-model="title"
        class="w-full text-2xl font-bold mb-2 p-2 border rounded outline-none focus:ring-2 focus:ring-blue-300"
        placeholder="Title"
      />

      <div class="flex gap-4 mb-4">
        <div class="flex-1">
          <label class="text-sm text-gray-500">Category</label>
          <input v-model="category" class="w-full p-2 border rounded outline-none focus:ring-2 focus:ring-blue-300" placeholder="e.g. tech" />
        </div>
        <div class="flex-1">
          <label class="text-sm text-gray-500">Tags (comma-separated)</label>
          <input v-model="tagsInput" class="w-full p-2 border rounded outline-none focus:ring-2 focus:ring-blue-300" placeholder="e.g. python, web" />
        </div>
      </div>

      <MarkdownEditor v-model="content" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import MarkdownEditor from '../components/MarkdownEditor.vue'

const props = defineProps<{ fileId?: string }>()
const router = useRouter()

const isNew = computed(() => !props.fileId || props.fileId === 'new')

const title = ref('')
const content = ref('')
const category = ref('')
const tagsInput = ref('')
const loading = ref(false)

onMounted(async () => {
  if (!isNew.value && props.fileId) {
    loading.value = true
    try {
      const note = await api.getNote(props.fileId)
      title.value = note.title
      content.value = note.content
      category.value = note.category || ''
      tagsInput.value = note.tags.join(', ')
    } catch {
      alert('Note not found')
      router.push('/')
    } finally {
      loading.value = false
    }
  }
})

async function save() {
  const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean)

  if (isNew.value) {
    const note = await api.createNote({
      title: title.value || 'Untitled',
      content: content.value,
      category: category.value || undefined,
      tags,
    })
    router.push(`/note/${encodeURIComponent(note.file_id)}`)
  } else if (props.fileId) {
    await api.updateNote(props.fileId, {
      title: title.value,
      content: content.value,
      category: category.value || null,
      tags,
    })
  }
}

async function deleteNote() {
  if (!props.fileId) return
  if (!confirm('Delete this note?')) return
  await api.deleteNote(props.fileId)
  router.push('/')
}
</script>
