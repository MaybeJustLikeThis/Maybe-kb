<template>
  <div class="card source-projects">
    <h3 class="section-heading">Source Projects</h3>
    <div v-if="projects.length === 0" class="empty-state">
      <p>No source projects</p>
    </div>
    <div v-else class="space-y-1">
      <router-link
        v-for="p in projects"
        :key="p.name"
        :to="`/notes?source_project=${encodeURIComponent(p.name)}`"
        class="source-link"
      >
        <span class="source-name">{{ p.name }}</span>
        <span class="source-count">{{ p.count }} notes</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  projects: Array<{ name: string; count: number }>
}>()
</script>

<style scoped>
.source-projects {
  min-height: 100%;
}

.source-link {
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

.source-link:hover {
  background: var(--color-surface-tinted);
  border-color: var(--color-border);
}

.source-name {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text);
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-count {
  flex-shrink: 0;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 650;
}
</style>
