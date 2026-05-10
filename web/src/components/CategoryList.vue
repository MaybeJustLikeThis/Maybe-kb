<template>
  <div class="card">
    <h3 class="section-heading">Categories</h3>
    <div v-if="categories.length === 0" class="text-sm" style="color: var(--color-text-muted);">
      No categories yet.
    </div>
    <router-link
      v-for="cat in categories"
      :key="cat.name"
      :to="`/notes?category=${encodeURIComponent(cat.name)}`"
      class="flex items-center justify-between py-2 px-1 rounded-md text-sm transition-colors hover:bg-gray-50"
    >
      <span style="color: var(--color-text);">{{ cat.name }}</span>
      <span class="flex items-center gap-1" style="color: var(--color-text-muted);">
        {{ cat.count }} 篇
        <span class="text-xs">&rarr;</span>
      </span>
    </router-link>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  categories: Array<{ name: string; count: number }>
}>()
</script>
