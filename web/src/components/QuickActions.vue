<template>
  <div class="card quick-actions">
    <h3 class="section-heading">Quick Actions</h3>
    <div class="action-grid">
      <button class="btn btn-primary text-sm" @click="$emit('reindex')">Rebuild Index</button>
      <router-link to="/notes" class="btn btn-outline text-sm no-underline">Browse Notes</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
defineEmits<{
  reindex: []
}>()
</script>

<style scoped>
.quick-actions {
  min-height: 100%;
}

.action-grid {
  display: grid;
  gap: 10px;
}

.action-grid .btn {
  width: 100%;
}
</style>
