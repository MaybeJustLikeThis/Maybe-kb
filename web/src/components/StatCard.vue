<template>
  <div class="card flex items-center gap-4 p-5">
    <span class="text-2xl">{{ icon }}</span>
    <div>
      <p class="text-2xl font-bold" style="color: var(--color-text);">{{ value }}</p>
      <p class="text-xs" style="color: var(--color-text-muted);">{{ label }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  value: number
  label: string
}>()
</script>
