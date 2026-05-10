<template>
  <div>
    <!-- Sidebar -->
    <aside class="w-60 fixed top-0 left-0 h-screen flex flex-col overflow-y-auto z-20" style="background: var(--color-sidebar);">
      <!-- Brand -->
      <div class="px-5 pt-6 pb-4">
        <router-link to="/" class="text-xl font-bold tracking-tight" style="color: #f1f5f9;">
          KB
        </router-link>
        <p class="text-xs mt-0.5" style="color: var(--color-text-sidebar-muted);">Knowledge Base</p>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-3 space-y-0.5">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors"
          :class="route.path === item.to ? 'nav-active' : 'nav-link'"
        >
          <span class="text-base">{{ item.icon }}</span>
          {{ item.label }}
        </router-link>
      </nav>

      <!-- Footer -->
      <div class="px-5 pb-5 pt-3">
        <p class="text-xs" style="color: var(--color-text-sidebar-muted);">v2.0.0</p>
      </div>
    </aside>

    <!-- Top bar -->
    <header
      v-if="tb.current"
      class="fixed top-0 left-60 right-0 z-10 flex items-center justify-between px-6 py-2.5 border-b"
      style="background: var(--color-surface); border-color: var(--color-border); height: 48px;"
    >
      <div class="flex items-center gap-3 min-w-0">
        <router-link :to="tb.current.backTo" class="text-sm flex-shrink-0" style="color: var(--color-text-muted);">&larr; Back</router-link>
        <span v-if="tb.current.title" class="text-sm font-medium truncate" style="color: var(--color-text);">{{ tb.current.title }}</span>
      </div>
      <div class="flex gap-2 flex-shrink-0">
        <button
          v-for="action in tb.current.actions"
          :key="action.label"
          @click="action.onClick"
          :class="action.btnClass"
          class="text-sm"
        >{{ action.label }}</button>
      </div>
    </header>

    <!-- Main content -->
    <main
      class="p-8 ml-60 min-h-screen"
      :class="tb.current ? 'pt-12' : ''"
      style="background: var(--color-bg);"
    >
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useTopBar } from './topBar'

const route = useRoute()
const tb = useTopBar()

const navItems = [
  { to: '/', label: 'Overview', icon: '🏠' },
  { to: '/notes', label: 'Notes', icon: '📄' },
  { to: '/search', label: 'Search', icon: '🔍' },
  { to: '/chat', label: 'Chat', icon: '💬' },
]
</script>

<style scoped>
.nav-link {
  color: var(--color-text-sidebar);
}
.nav-link:hover {
  background: var(--color-sidebar-hover);
  color: #f1f5f9;
}
.nav-active {
  background: var(--color-sidebar-active);
  color: #f1f5f9;
}
</style>
