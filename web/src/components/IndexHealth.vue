<template>
  <div class="card">
    <h3 class="section-heading">Index Health</h3>
    <div class="flex items-baseline gap-4 mb-2">
      <div>
        <span class="text-2xl font-bold" :style="{ color: coverage > 0 ? '#10b981' : '#ef4444' }">
          {{ Math.round(coverage * 100) }}%
        </span>
        <p class="text-xs" style="color: var(--color-text-muted);">coverage</p>
      </div>
      <div>
        <span class="text-lg font-semibold" style="color: var(--color-text);">{{ vectorsCount }}</span>
        <p class="text-xs" style="color: var(--color-text-muted);">vectors</p>
      </div>
      <div>
        <span class="text-lg font-semibold" style="color: var(--color-text);">{{ notesCount }}</span>
        <p class="text-xs" style="color: var(--color-text-muted);">files</p>
      </div>
    </div>
    <div class="h-1.5 rounded overflow-hidden" style="background: #1e293b;">
      <div
        class="h-full rounded transition-all"
        :style="{ width: Math.round(coverage * 100) + '%', background: coverage > 0 ? '#10b981' : '#ef4444' }"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  notesCount: number
  vectorsCount: number
  coverage: number
}>()
</script>
