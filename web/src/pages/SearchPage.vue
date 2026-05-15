<template>
  <div class="search-page">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Retrieval</p>
        <h2>Search Workbench</h2>
        <p class="hero-description">
          Find notes, source context, and tagged knowledge across the local vault.
        </p>
      </div>
    </section>

    <section class="command-card">
      <span class="command-token">SR</span>
      <input
        v-model="query"
        @keyup.enter="search"
        class="input command-input"
        placeholder="Search notes..."
        autofocus
      />
      <button
        class="btn btn-primary command-button"
        :disabled="searching || !query.trim()"
        @click="search"
      >
        Run
      </button>
    </section>

    <div v-if="searching" class="empty-state">
      <div class="empty-state-icon">...</div>
      <p>Searching...</p>
    </div>

    <section v-else-if="results.length > 0" class="results-section">
      <div class="results-header">
        <p>
          {{ results.length }} result{{ results.length !== 1 ? 's' : '' }} for "{{ lastQuery }}"
        </p>
      </div>

      <ul class="results-list">
        <li v-for="result in results" :key="result.note.file_id" class="result-item">
          <router-link
            :to="`/note/${encodeURIComponent(result.note.file_id)}`"
            class="result-card"
          >
            <div class="result-main">
              <div class="result-title-row">
                <h3>{{ result.note.title }}</h3>
                <span v-if="result.score !== null" class="score-badge">
                  {{ Math.round(result.score * 100) }}%
                </span>
              </div>

              <p v-if="result.note.description" class="result-description">
                {{ result.note.description }}
              </p>

              <div v-if="result.chunk_text" class="chunk-preview">
                {{ result.chunk_text }}
              </div>

              <div class="result-badges">
                <span v-if="result.note.category" class="badge badge-primary">{{ result.note.category }}</span>
                <span v-for="tag in result.note.tags" :key="tag" class="badge badge-muted">{{ tag }}</span>
              </div>
            </div>

            <div class="result-source">
              <span>Source</span>
              <strong>{{ result.source }}</strong>
            </div>
          </router-link>
        </li>
      </ul>
    </section>

    <div v-else-if="lastQuery" class="empty-state">
      <div class="empty-state-icon">SR</div>
      <p>No results found for "{{ lastQuery }}".</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api, type SearchResult } from '../api'

const query = ref('')
const lastQuery = ref('')
const results = ref<SearchResult[]>([])
const searching = ref(false)

async function search() {
  const q = query.value.trim()
  if (!q) return

  searching.value = true
  lastQuery.value = q
  try {
    results.value = await api.search(q)
  } finally {
    searching.value = false
  }
}
</script>

<style scoped>
.search-page {
  max-width: 1120px;
  margin: 0 auto;
}

.page-hero {
  margin-bottom: 18px;
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
  max-width: 620px;
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: 0.98rem;
  line-height: 1.65;
}

.command-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  margin-bottom: 22px;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.command-token {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 38px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  color: #fff;
  font-size: 0.75rem;
  font-weight: 900;
  letter-spacing: 0.06em;
}

.command-input {
  min-height: 42px;
  font-size: 0.95rem;
}

.command-button {
  min-width: 82px;
  min-height: 42px;
}

.results-section {
  display: grid;
  gap: 12px;
}

.results-header p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.86rem;
  font-weight: 700;
}

.results-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.result-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(160px, 0.24fr);
  gap: 18px;
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast);
}

.result-card:hover {
  border-color: var(--color-border-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.result-main {
  min-width: 0;
}

.result-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.result-title-row h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 1rem;
  font-weight: 800;
  line-height: 1.35;
}

.score-badge {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.12);
  color: var(--color-success);
  font-size: 0.76rem;
  font-weight: 850;
}

.result-description {
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  font-size: 0.9rem;
  line-height: 1.55;
}

.chunk-preview {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid rgba(8, 145, 178, 0.14);
  border-radius: var(--radius-md);
  background: var(--color-surface-tinted);
  color: var(--color-text-secondary);
  font-size: 0.86rem;
  line-height: 1.55;
}

.result-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.result-source {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  color: var(--color-text-muted);
  text-align: right;
  font-size: 0.75rem;
}

.result-source span {
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.result-source strong {
  max-width: 100%;
  overflow-wrap: anywhere;
  color: var(--color-text-secondary);
  font-weight: 750;
}

@media (max-width: 720px) {
  .command-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .command-button {
    grid-column: 1 / -1;
    width: 100%;
  }

  .result-card {
    grid-template-columns: minmax(0, 1fr);
  }

  .result-source {
    align-items: flex-start;
    text-align: left;
  }
}
</style>
