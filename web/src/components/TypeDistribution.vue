<template>
  <div class="card">
    <h3 class="section-heading">Knowledge Types</h3>
    <div v-if="types.length === 0" class="empty-state">
      <p>No data</p>
    </div>
    <div v-else class="space-y-2.5">
      <router-link
        v-for="(t, i) in types"
        :key="t.name"
        :to="`/notes?entry_type=${encodeURIComponent(t.name)}`"
        class="flex items-center gap-3 text-sm no-underline group"
      >
        <span class="w-24 text-right flex-shrink-0 text-xs" style="color: var(--color-text-muted);">{{ t.label }}</span>
        <div class="flex-1 h-5 rounded overflow-hidden" style="background: #1e293b;">
          <div
            class="h-full rounded flex items-center pl-2 transition-all"
            :style="{
              width: max > 0 ? (t.count / max) * 100 + '%' : '0%',
              background: gradients[i % gradients.length],
            }"
          >
            <span class="text-xs text-white font-semibold" v-if="t.count > 0">{{ t.count }}</span>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  types: Array<{ name: string; count: number; label: string }>
}>()

const max = computed(() => props.types.reduce((m, t) => Math.max(m, t.count), 0))

const gradients = [
  'linear-gradient(90deg, #2563eb, #3b82f6)',
  'linear-gradient(90deg, #059669, #10b981)',
  'linear-gradient(90deg, #d97706, #f59e0b)',
  'linear-gradient(90deg, #be185d, #ec4899)',
  'linear-gradient(90deg, #7c3aed, #8b5cf6)',
]
</script>
