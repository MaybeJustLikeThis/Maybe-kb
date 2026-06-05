<template>
  <div class="dashboard-page">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Knowledge system</p>
        <h2>Overview Control Center</h2>
        <p class="hero-description">
          Monitor notes, taxonomy coverage, index health, and recent activity from one bright operations surface.
        </p>
      </div>
      <button class="btn btn-primary" :disabled="loading" @click="handleReindex">Rebuild Index</button>
    </section>

    <div v-if="loading" class="empty-state">
      <div class="empty-state-icon">...</div>
      <p>Loading...</p>
    </div>

    <div v-else-if="error" class="empty-state">
      <div class="empty-state-icon">!</div>
      <p style="color: var(--color-danger);">{{ error }}</p>
    </div>

    <template v-else>
      <div class="metric-grid">
        <StatCard icon="NT" :value="stats.notesCount" label="Notes" />
        <StatCard icon="TP" :value="stats.typesCount" label="Types" />
        <StatCard icon="CT" :value="stats.categoriesCount" label="Categories" />
        <StatCard icon="TG" :value="stats.tagsCount" label="Tags" />
        <StatCard icon="AT" :value="stats.attachmentsCount" label="Attachments" />
      </div>

      <div class="overview-grid">
        <SourceProjects :projects="sourceProjects" />
        <IndexHealth
          :notes-count="indexHealth.notes_count"
          :vectors-count="indexHealth.vectors_count"
          :coverage="indexHealth.coverage"
        />
        <SystemHealth
          v-if="health"
          :health="health"
          :rebuilding="reindexing"
          @rebuild="handleReindex"
        />
        <DashboardActivity :items="activity" :error="activityError" />
      </div>

      <div class="widget-grid">
        <SourceProjects :projects="sourceProjects" />
        <ContentFormatPie :content-types="contentTypes" />
        <QuickActions @reindex="handleReindex" />
        <div class="recent-panel">
          <RecentNotes :notes="recentNotes" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type DashboardActivityItem, type Note, type SystemHealth as SystemHealthData } from '../api'
import StatCard from '../components/StatCard.vue'
import IndexHealth from '../components/IndexHealth.vue'
import SystemHealth from '../components/SystemHealth.vue'
import SourceProjects from '../components/SourceProjects.vue'
import ContentFormatPie from '../components/ContentFormatPie.vue'
import QuickActions from '../components/QuickActions.vue'
import RecentNotes from '../components/RecentNotes.vue'
import DashboardActivity from '../components/DashboardActivity.vue'

const loading = ref(true)
const error = ref<string | null>(null)
const stats = ref({ notesCount: 0, typesCount: 0, categoriesCount: 0, tagsCount: 0, attachmentsCount: 0 })
const sourceProjects = ref<Array<{ name: string; count: number; label?: string | null }>>([])
const contentTypes = ref<Array<{ name: string; count: number }>>([])
const indexHealth = ref({ notes_count: 0, vectors_count: 0, coverage: 0 })
const health = ref<SystemHealthData | null>(null)
const recentNotes = ref<Note[]>([])
const activity = ref<DashboardActivityItem[]>([])
const activityError = ref(false)
const reindexing = ref(false)

onMounted(async () => {
  try {
    const [
      indexData, attData, catData, tagData, notesData,
      srcData, ctData, indexHealthData, systemHealthData,
    ] = await Promise.all([
      api.getIndexStatus(),
      api.getAttachmentsStats(),
      api.getCategoriesWithCount(),
      api.getTags(),
      api.listNotes({ limit: 8 }),
      api.getSourceProjects(),
      api.getContentTypeStats(),
      api.getIndexHealth(),
      api.getHealth(),
    ])
    stats.value = {
      notesCount: indexData.notes_count,
      typesCount: srcData.projects.length,
      categoriesCount: catData.categories.length,
      tagsCount: tagData.tags.length,
      attachmentsCount: attData.count,
    }
    sourceProjects.value = srcData.projects
    contentTypes.value = ctData.content_types
    indexHealth.value = indexHealthData
    health.value = systemHealthData
    recentNotes.value = notesData
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
  } finally {
    loading.value = false
  }

  try {
    activity.value = await api.getDashboardActivity({ limit: 8 })
  } catch (e) {
    activityError.value = true
  }
})

async function handleReindex() {
  reindexing.value = true
  try {
    await api.triggerIndex()
    const [indexHealthData, systemHealthData] = await Promise.all([
      api.getIndexHealth(),
      api.getHealth(),
    ])
    indexHealth.value = indexHealthData
    health.value = systemHealthData
  } catch (e) {
    // silent
  } finally {
    reindexing.value = false
  }
}
</script>

<style scoped>
.dashboard-page {
  max-width: 1440px;
  margin: 0 auto;
}

.page-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
  padding: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(241, 248, 255, 0.92)),
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.18), transparent 26rem);
  box-shadow: var(--shadow-sm);
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-hero h2 {
  margin: 0;
  color: var(--color-text);
  font-size: clamp(1.9rem, 3vw, 3rem);
  font-weight: 850;
  line-height: 1.05;
}

.hero-description {
  max-width: 680px;
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: 0.98rem;
  line-height: 1.65;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.overview-grid,
.widget-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.type-panel,
.recent-panel {
  min-width: 0;
}

@media (min-width: 900px) {
  .metric-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }

  .overview-grid {
    grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.75fr) minmax(300px, 0.8fr);
    align-items: stretch;
  }

  .widget-grid {
    grid-template-columns: minmax(240px, 0.9fr) minmax(240px, 0.8fr) minmax(220px, 0.7fr) minmax(0, 1.4fr);
    align-items: stretch;
  }
}

@media (max-width: 720px) {
  .page-hero {
    align-items: stretch;
    flex-direction: column;
    padding: 20px;
  }

  .page-hero .btn {
    width: 100%;
  }
}
</style>
