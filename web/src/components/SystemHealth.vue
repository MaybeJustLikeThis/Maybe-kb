<template>
  <section class="card system-health">
    <div class="system-health-header">
      <div>
        <h3 class="section-heading">System Health</h3>
        <p>{{ subtitle }}</p>
      </div>
      <span :class="['health-pill', `health-${health.status}`]">{{ statusLabel }}</span>
    </div>

    <div class="health-summary">
      <div>
        <strong>{{ health.summary.notes_count }}</strong>
        <span>notes</span>
      </div>
      <div>
        <strong>{{ health.summary.vectors_count }}</strong>
        <span>vectors</span>
      </div>
      <div>
        <strong>{{ Math.round(health.summary.coverage * 100) }}%</strong>
        <span>coverage</span>
      </div>
    </div>

    <ul class="health-checks">
      <li v-for="check in visibleChecks" :key="check.id" :class="`check-${check.status}`">
        <div>
          <strong>{{ check.label }}</strong>
          <p>{{ check.message }}</p>
        </div>
        <span>{{ check.action || check.status }}</span>
      </li>
    </ul>

    <button
      v-if="showRebuild"
      type="button"
      class="btn btn-primary rebuild-button"
      :disabled="rebuilding"
      @click="$emit('rebuild')"
    >
      Rebuild index
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SystemHealth } from '../api'

const props = defineProps<{
  health: SystemHealth
  rebuilding?: boolean
}>()

defineEmits<{
  rebuild: []
}>()

const statusLabel = computed(() => {
  if (props.health.status === 'ready') return 'Ready'
  if (props.health.status === 'warning') return 'Needs attention'
  return 'Setup issue'
})

const subtitle = computed(() => {
  if (props.health.status === 'ready') return 'Local knowledge is ready.'
  if (props.health.status === 'warning') return 'Some capabilities need attention.'
  return 'Setup issue blocks trustworthy results.'
})

const visibleChecks = computed(() => {
  const actionable = props.health.checks.filter((check) => check.status !== 'ready')
  return actionable.length ? actionable : props.health.checks.slice(0, 4)
})

const showRebuild = computed(() =>
  props.health.checks.some((check) =>
    check.action?.toLowerCase().includes('rebuild'),
  ),
)
</script>

<style scoped>
.system-health {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.system-health-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.system-health-header p {
  margin: -4px 0 0;
  color: var(--color-text-muted);
  font-size: 0.84rem;
  line-height: 1.45;
}

.health-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 82px;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 850;
  text-align: center;
  white-space: nowrap;
}

.health-ready {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.health-warning {
  background: rgba(245, 158, 11, 0.16);
  color: #92400e;
}

.health-error {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.health-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.health-summary div {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-tinted);
}

.health-summary strong,
.health-summary span {
  display: block;
}

.health-summary strong {
  overflow: hidden;
  color: var(--color-text);
  font-size: 1.1rem;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.health-summary span {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.health-checks {
  display: grid;
  flex: 1;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.health-checks li {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 10px;
  border: 1px solid var(--color-border);
  border-left-width: 4px;
  border-radius: var(--radius-sm);
  background: #fff;
}

.health-checks strong {
  color: var(--color-text);
  font-size: 0.86rem;
  font-weight: 800;
}

.health-checks p {
  margin: 2px 0 0;
  color: var(--color-text-muted);
  font-size: 0.76rem;
  line-height: 1.4;
}

.health-checks li > span {
  flex: 0 0 auto;
  max-width: 42%;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 760;
  text-align: right;
}

.check-ready {
  border-left-color: #10b981;
}

.check-warning {
  border-left-color: #f59e0b;
}

.check-error {
  border-left-color: #ef4444;
}

.rebuild-button {
  width: 100%;
  margin-top: 12px;
}

@media (max-width: 520px) {
  .system-health-header,
  .health-checks li {
    flex-direction: column;
  }

  .health-pill,
  .health-checks li > span {
    max-width: 100%;
    text-align: left;
  }
}
</style>
