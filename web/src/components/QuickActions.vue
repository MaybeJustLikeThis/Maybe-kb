<template>
  <div class="card">
    <h3 class="section-heading">Quick Actions</h3>
    <div class="flex flex-wrap gap-2">
      <button class="btn btn-ghost text-sm" @click="$emit('reindex')">Rebuild Index</button>
      <router-link to="/notes" class="btn btn-ghost text-sm no-underline">New Note</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
defineEmits<{
  reindex: []
}>()
</script>
