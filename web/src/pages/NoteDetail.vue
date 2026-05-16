<template>
  <div>
    <div v-if="loading" class="empty-state">
      <div class="empty-state-icon">...</div>
      <p>Loading...</p>
    </div>

    <div v-else>
      <!-- Reading mode -->
      <template v-if="!isEditing">
        <h1 class="text-3xl font-bold mb-3" style="color: var(--color-text);">{{ title }}</h1>

        <!-- Metadata row with separators -->
        <div class="flex items-center gap-1.5 text-sm mb-8 flex-wrap" style="color: var(--color-text-muted);">
          <span v-if="category" class="badge badge-primary">{{ category }}</span>
          <span v-if="category && tags.length > 0" style="color: var(--color-border);">/</span>
          <template v-for="(tag, i) in tags" :key="tag">
            <span class="badge badge-muted">{{ tag }}</span>
            <span v-if="i < tags.length - 1" style="color: var(--color-border);">/</span>
          </template>
          <span v-if="(category || tags.length > 0) && noteUpdatedAt" style="color: var(--color-border);">/</span>
          <span v-if="noteUpdatedAt">{{ noteUpdatedAt }}</span>
        </div>

        <div v-html="renderedContent" class="prose prose-slate max-w-none"></div>
      </template>

      <!-- Editing mode -->
      <template v-else>
        <input
          v-model="title"
          class="input text-2xl font-bold mb-4"
          style="font-size: 1.5rem;"
          placeholder="Title"
        />
        <div class="flex gap-4 mb-4">
          <div class="flex-1">
            <label class="text-sm" style="color: var(--color-text-muted);">Category</label>
            <input v-model="category" class="input mt-1" placeholder="e.g. tech" />
          </div>
          <div class="flex-1">
            <label class="text-sm" style="color: var(--color-text-muted);">Tags (comma-separated)</label>
            <input v-model="tagsInput" class="input mt-1" placeholder="e.g. python, web" />
          </div>
        </div>
        <MarkdownEditor v-model="content" />
      </template>

      <!-- Related Notes -->
      <div v-if="!isNew" class="mt-12">
        <hr class="divider" />
        <h2 class="text-lg font-semibold mb-4" style="color: var(--color-text);">Related Notes</h2>
        <div v-if="relatedError" class="text-sm" style="color: var(--color-text-muted);">Failed to load related notes.</div>
        <div v-else-if="relatedNotes.length === 0" class="text-sm" style="color: var(--color-text-muted);">No related notes found.</div>
        <div v-else class="grid gap-2">
          <router-link
            v-for="note in relatedNotes"
            :key="note.file_id"
            :to="note.source_project ? `/source/${note.source_project}/${encodeURIComponent(note.file_id)}` : `/note/${encodeURIComponent(note.file_id)}`"
            class="card flex justify-between items-start"
          >
            <div>
              <span class="font-medium" style="color: var(--color-primary);">{{ note.title }}</span>
              <div v-if="note.category" class="text-xs mt-1" style="color: var(--color-text-muted);">
                {{ note.category }}
                <span v-if="note.tags.length"> / {{ note.tags.slice(0, 3).join(', ') }}</span>
              </div>
            </div>
            <span class="text-xs flex-shrink-0 ml-3" style="color: var(--color-text-muted);">{{ (note.score * 100).toFixed(0) }}%</span>
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.min.css'
import { api } from '../api'
import MarkdownEditor from '../components/MarkdownEditor.vue'
import { setTopBar } from '../topBar'

const props = defineProps<{ name?: string; fileId?: string }>()
const router = useRouter()

const isNew = computed(() => !props.fileId || props.fileId === 'new')

const title = ref('')
const content = ref('')
const category = ref('')
const tagsInput = ref('')
const loading = ref(false)
const isEditing = ref(isNew.value)
const noteUpdatedAt = ref('')
const tags = ref<string[]>([])
const relatedNotes = ref<Array<{ file_id: string; title: string; category: string | null; tags: string[]; source_project: string | null; score: number }>>([])
const relatedError = ref(false)

const marked = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code: string, lang: string) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    },
  }),
  { breaks: true, gfm: true },
)

const renderedContent = computed(() => {
  const raw = marked.parse(content.value || '', { async: false }) as string
  return DOMPurify.sanitize(raw)
})

function syncTopBar() {
  const backTo = props.name ? `/source/${props.name}` : '/'
  if (isNew.value) {
    setTopBar({
      backTo,
      title: 'New Note',
      actions: [
        { label: 'Cancel', onClick: cancelEdit, btnClass: 'btn btn-ghost' },
        { label: 'Save', onClick: save, btnClass: 'btn btn-primary' },
      ],
    })
  } else if (isEditing.value) {
    setTopBar({
      backTo,
      title: title.value || 'Untitled',
      actions: [
        { label: 'Cancel', onClick: cancelEdit, btnClass: 'btn btn-ghost' },
        { label: 'Save', onClick: save, btnClass: 'btn btn-primary' },
      ],
    })
  } else {
    setTopBar({
      backTo,
      title: title.value,
      actions: [
        { label: 'Edit', onClick: startEdit, btnClass: 'btn btn-outline' },
        { label: 'Delete', onClick: deleteNote, btnClass: 'btn btn-danger' },
      ],
    })
  }
}

watch([isEditing, title], syncTopBar, { immediate: true })

async function loadNote() {
  if (!isNew.value && props.fileId) {
    loading.value = true
    try {
      const note = await api.getNote(props.fileId)
      title.value = note.title
      content.value = note.content
      category.value = note.category || ''
      tags.value = note.tags
      tagsInput.value = note.tags.join(', ')
      noteUpdatedAt.value = note.updated_at || note.created_at || ''
      try {
        const related = await api.getRelatedNotes(props.fileId, 5)
        relatedNotes.value = related.map((result) => ({
          ...result.note,
          score: result.score ?? 0,
        }))
        relatedError.value = false
      } catch {
        relatedNotes.value = []
        relatedError.value = true
      }
    } catch {
      alert('Note not found')
      router.push('/')
    } finally {
      loading.value = false
    }
  }
}

watch(() => props.fileId, (newId) => {
  isEditing.value = !newId || newId === 'new'
  loadNote()
})

onMounted(() => { loadNote() })

onUnmounted(() => {
  setTopBar(null)
})

function startEdit() {
  isEditing.value = true
}

function cancelEdit() {
  if (isNew.value) {
    router.push('/')
    return
  }
  isEditing.value = false
  loadNote()
}

async function save() {
  const tagList = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean)

  if (isNew.value) {
    const note = await api.createNote({
      title: title.value || 'Untitled',
      content: content.value,
      category: category.value || undefined,
      tags: tagList,
    })
    if (props.name) {
      router.push(`/source/${props.name}/${encodeURIComponent(note.file_id)}`)
    } else {
      router.push(`/note/${encodeURIComponent(note.file_id)}`)
    }
  } else if (props.fileId) {
    await api.updateNote(props.fileId, {
      title: title.value,
      content: content.value,
      category: category.value || null,
      tags: tagList,
    })
    tags.value = tagList
    isEditing.value = false
  }
}

async function deleteNote() {
  if (!props.fileId) return
  if (!confirm('Delete this note?')) return
  await api.deleteNote(props.fileId)
  router.push('/')
}
</script>
