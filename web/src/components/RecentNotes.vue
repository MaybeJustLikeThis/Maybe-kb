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
            <span v-if="note.entry_type" class="text-xs px-1.5 py-0.5 rounded flex-shrink-0" :style="typeBadgeStyle(note.entry_type)">
              {{ note.entry_type }}
            </span>
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

const typeColors: Record<string, { bg: string; text: string }> = {
  'tech-article': { bg: 'rgba(59,130,246,0.15)', text: '#3b82f6' },
  'document': { bg: 'rgba(16,185,129,0.15)', text: '#10b981' },
  'troubleshooting': { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b' },
  'design-decision': { bg: 'rgba(236,72,153,0.15)', text: '#ec4899' },
  'code-snippet': { bg: 'rgba(139,92,246,0.15)', text: '#8b5cf6' },
}

function typeBadgeStyle(entryType: string) {
  const c = typeColors[entryType] || { bg: 'rgba(100,116,139,0.15)', text: '#94a3b8' }
  return { background: c.bg, color: c.text }
}

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
