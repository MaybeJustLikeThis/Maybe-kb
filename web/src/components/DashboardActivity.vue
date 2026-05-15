<template>
  <section class="card activity-panel">
    <div class="activity-head">
      <div>
        <h3 class="section-heading">Activity Stream</h3>
        <p class="activity-subtitle">Recent knowledge updates</p>
      </div>
      <span class="activity-count">{{ items.length }}</span>
    </div>

    <div v-if="error" class="activity-empty">
      Activity is temporarily unavailable.
    </div>
    <div v-else-if="items.length === 0" class="activity-empty">
      No activity yet.
    </div>
    <ol v-else class="activity-list">
      <li v-for="item in items" :key="`${item.note.file_id}-${item.timestamp ?? item.title}`" class="activity-item">
        <span class="activity-dot" aria-hidden="true"></span>
        <router-link :to="`/note/${encodeURIComponent(item.note.file_id)}`" class="activity-link">
          <span class="activity-title">{{ item.title }}</span>
          <span class="activity-description">{{ item.description || item.note.title }}</span>
          <span class="activity-time">{{ formatTime(item.timestamp) }}</span>
        </router-link>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import type { DashboardActivityItem } from '../api'

defineProps<{
  items: DashboardActivityItem[]
  error?: boolean
}>()

function formatTime(value: string | null): string {
  if (!value) return 'Unknown time'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
</script>

<style scoped>
.activity-panel {
  min-height: 100%;
}

.activity-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.activity-subtitle {
  margin: -4px 0 0;
  color: var(--color-text);
  font-size: 0.95rem;
  font-weight: 750;
}

.activity-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 28px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
  font-size: 0.78rem;
  font-weight: 800;
}

.activity-empty {
  padding: 28px 8px;
  color: var(--color-text-muted);
  font-size: 0.9rem;
  text-align: center;
}

.activity-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.activity-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
}

.activity-dot {
  width: 8px;
  height: 8px;
  margin-top: 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.12);
}

.activity-link {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.activity-link:hover {
  background: var(--color-surface-tinted);
  border-color: var(--color-border);
}

.activity-title,
.activity-description {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-title {
  color: var(--color-text);
  font-size: 0.9rem;
  font-weight: 750;
}

.activity-description {
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.activity-time {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 650;
}
</style>
