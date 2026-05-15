<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand-block">
        <router-link to="/" class="brand-mark">KB</router-link>
        <p>Control Center</p>
      </div>

      <nav class="nav-list">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="route.path === item.to ? 'nav-active' : ''"
        >
          <span class="nav-token">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-status">
        <span class="status-dot"></span>
        <span>Local vault online</span>
      </div>
    </aside>

    <header v-if="tb.current" class="top-command">
      <div class="top-command-left">
        <router-link :to="tb.current.backTo" class="back-link">Back</router-link>
        <span v-if="tb.current.title" class="top-title">{{ tb.current.title }}</span>
      </div>
      <div class="top-command-actions">
        <button
          v-for="action in tb.current.actions"
          :key="action.label"
          @click="action.onClick"
          :class="action.btnClass"
        >{{ action.label }}</button>
      </div>
    </header>

    <main class="app-main" :class="tb.current ? 'has-top-command' : ''">
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
  { to: '/', label: 'Overview', icon: 'OV' },
  { to: '/notes', label: 'Notes', icon: 'NT' },
  { to: '/manage', label: 'Manage', icon: 'MG' },
  { to: '/search', label: 'Search', icon: 'SR' },
  { to: '/chat', label: 'Chat', icon: 'AI' },
]
</script>

<style scoped>
.app-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: 240px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: linear-gradient(180deg, #0d1726, #101827);
  border-right: 1px solid var(--color-sidebar-border);
  color: var(--color-text-sidebar);
}

.brand-block {
  padding: 24px 20px 18px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 34px;
  border-radius: 8px;
  background: linear-gradient(135deg, #22d3ee, #6366f1);
  color: #fff;
  font-weight: 900;
  letter-spacing: 0.04em;
}

.brand-block p {
  margin-top: 8px;
  color: var(--color-text-sidebar-muted);
  font-size: 0.75rem;
}

.nav-list {
  flex: 1;
  padding: 0 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 8px;
  color: var(--color-text-sidebar);
  font-size: 0.9rem;
  font-weight: 650;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.nav-item:hover,
.nav-active {
  background: var(--color-sidebar-active);
  color: #f8fafc;
}

.nav-token {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.08);
  color: #a5f3fc;
  font-size: 0.68rem;
  letter-spacing: 0.04em;
}

.sidebar-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 16px 18px;
  padding: 12px;
  border: 1px solid var(--color-sidebar-border);
  border-radius: 8px;
  color: var(--color-text-sidebar-muted);
  font-size: 0.75rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.16);
}

.top-command {
  position: fixed;
  top: 0;
  left: 240px;
  right: 0;
  z-index: 10;
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 28px;
  background: rgba(248, 251, 255, 0.9);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--color-border);
}

.top-command-left,
.top-command-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.back-link {
  color: var(--color-primary-hover);
  font-size: 0.85rem;
  font-weight: 700;
}

.top-title {
  color: var(--color-text);
  font-size: 0.9rem;
  font-weight: 750;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  min-height: 100vh;
  margin-left: 240px;
  padding: 32px;
}

.app-main.has-top-command {
  padding-top: 78px;
}
</style>
