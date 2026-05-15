<template>
  <div class="card stat-card">
    <span class="stat-icon">{{ icon }}</span>
    <div class="stat-copy">
      <p class="stat-value">{{ value }}</p>
      <p class="stat-label">{{ label }}</p>
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

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 94px;
  padding: 18px;
}

.stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary-light), rgba(79, 70, 229, 0.12));
  color: var(--color-primary-hover);
  font-size: 0.78rem;
  font-weight: 850;
  letter-spacing: 0.04em;
  box-shadow: inset 0 0 0 1px rgba(8, 145, 178, 0.14);
}

.stat-copy {
  min-width: 0;
}

.stat-value {
  margin: 0;
  color: var(--color-text);
  font-size: 1.55rem;
  font-weight: 850;
  line-height: 1.05;
}

.stat-label {
  margin: 4px 0 0;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 650;
}
</style>
