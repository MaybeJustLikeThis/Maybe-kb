<template>
  <div class="card">
    <h3 class="section-heading">Recent Updates</h3>
    <div v-if="notes.length === 0" class="empty-state">
      <div class="empty-state-icon">📝</div>
      <p>No notes yet.</p>
    </div>
    <ul v-else class="space-y-1">
      <li v-for="note in notes" :key="note.file_id">
        <router-link
          :to="`/note/${encodeURIComponent(note.file_id)}`"
          class="flex items-center justify-between py-2 px-1 rounded-md text-sm transition-colors hover:bg-gray-50"
        >
          <div class="flex items-center gap-3 min-w-0">
            <span class="truncate font-medium" style="color: var(--color-text);">{{ note.title }}</span>
            <span v-if="note.category" class="badge badge-primary flex-shrink-0">{{ note.category }}</span>
          </div>
          <span class="text-xs flex-shrink-0 ml-3" style="color: var(--color-text-muted);">
            {{ formatTime(note.updated_at || note.created_at) }}
          </span>
        </router-link>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { type Note } from '../api'

defineProps<{
  notes: Note[]
}>()

function formatTime(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}
</script>
