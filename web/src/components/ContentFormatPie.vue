<template>
  <div class="card">
    <h3 class="section-heading">Content Format</h3>
    <div class="flex items-center gap-4">
      <div
        class="w-16 h-16 rounded-full flex-shrink-0"
        :style="{ background: pieGradient }"
      ></div>
      <div class="flex-1 space-y-1.5">
        <div v-for="(ct, i) in contentTypes" :key="ct.name" class="flex items-center gap-2 text-xs">
          <span class="w-2 h-2 rounded-sm flex-shrink-0" :style="{ background: sliceColors[i] }"></span>
          <span style="color: var(--color-text-muted);">{{ ct.name }}</span>
          <span class="ml-auto" style="color: var(--color-text);">{{ ct.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  contentTypes: Array<{ name: string; count: number }>
}>()

const sliceColors = ['#3b82f6', '#f59e0b', '#ec4899', '#10b981', '#8b5cf6']

const pieGradient = computed(() => {
  const total = props.contentTypes.reduce((s, ct) => s + ct.count, 0)
  if (total === 0) return '#334155'
  let cumulative = 0
  const parts: string[] = []
  props.contentTypes.forEach((ct, i) => {
    if (ct.count === 0) return
    const start = (cumulative / total) * 360
    cumulative += ct.count
    const end = (cumulative / total) * 360
    parts.push(`${sliceColors[i]} ${start}deg ${end}deg`)
  })
  return `conic-gradient(${parts.join(', ')})`
})
</script>
