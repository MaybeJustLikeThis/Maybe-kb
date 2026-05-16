<template>
  <div class="card recent-notes">
    <h3 class="section-heading">Recent Updates</h3>
    <div v-if="notes.length === 0" class="empty-state">
      <div class="empty-state-icon">NT</div>
      <p>No notes yet.</p>
    </div>
    <ul v-else class="space-y-1">
      <li v-for="note in notes" :key="note.file_id">
        <router-link
          :to="`/note/${encodeURIComponent(note.file_id)}`"
          class="recent-link"
        >
          <div class="flex items-center gap-3 min-w-0">
            <span class="truncate font-medium" style="color: var(--color-text);">{{ note.title }}</span>
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
  if (Number.isNaN(d.getTime())) return ts
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.max(0, Math.floor(diff / 60000))
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString()
}
</script>

<style scoped>
.recent-notes {
  min-height: 100%;
}

.recent-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.recent-link:hover {
  background: var(--color-surface-tinted);
  border-color: var(--color-border);
}
</style>
