<template>
  <div class="card">
    <h3 class="section-heading">Tags</h3>
    <div v-if="tags.length === 0" class="text-sm" style="color: var(--color-text-muted);">
      No tags yet.
    </div>
    <div v-else class="flex flex-wrap gap-1.5">
      <router-link
        v-for="tag in tags"
        :key="tag"
        :to="`/source/blog?tag=${encodeURIComponent(tag)}`"
        class="badge badge-muted hover:bg-gray-200 cursor-pointer transition-colors"
      >
        {{ tag }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  tags: string[]
}>()
</script>
