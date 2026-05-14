<template>
  <div class="card">
    <h3 class="section-heading">Source Projects</h3>
    <div v-if="projects.length === 0" class="empty-state">
      <p>No source projects</p>
    </div>
    <div v-else class="space-y-1">
      <router-link
        v-for="p in projects"
        :key="p.name"
        :to="`/notes?source_project=${encodeURIComponent(p.name)}`"
        class="flex items-center justify-between py-2 px-1 rounded text-sm no-underline hover:bg-opacity-10 hover:bg-gray-500 transition-colors"
      >
        <span style="color: var(--color-text);">{{ p.name }}</span>
        <span class="text-xs" style="color: var(--color-text-muted);">{{ p.count }} notes</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  projects: Array<{ name: string; count: number }>
}>()
</script>
