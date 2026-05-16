# Source-First Architecture Design

Date: 2026-05-16
Branch: design/source-first

## Problem

The current architecture is designed around a **type-first** model — `entry_type` (tech-article, troubleshooting, design-decision, code-snippet, document) is a first-class dimension powering TypeDistribution on the dashboard and type-based navigation. However, the actual content comes from a Hexo blog where posts don't have a `type` field in frontmatter. All 24 published notes have `entry_type = NULL` and `source_project = NULL`. The design and the data have never been aligned.

## Goal

Replace the type-first model with a **source-first** architecture:

- Navigation is organized by content source (blog, agent, manual)
- `source_project` becomes the primary organizational dimension
- `entry_type` and related concepts are removed from code, API, and UI
- The sidebar reflects this with a two-tier structure: function entries + source tabs

## Design

### 1. Navigation Model

Two-tier sidebar in `App.vue`:

```
┌──────────────┐
│ [brand]      │
│              │
│ Overview     │  ← function entries (fixed)
│ Search       │
│ Chat         │
│              │
│ ──────────── │  ← divider
│              │
│ 博客         │  ← source tabs
│ Agent 沉淀   │
│ 手动录入      │
│              │
│ ──────────── │
│ Manage       │
└──────────────┘
```

- **Overview**: global aggregate across all sources
- **Search / Chat**: cross-source by default, filterable by source
- **Source tabs**: `SourcePage` driven by `source_project` from route param `:name`
- **Manage**: system configuration

### 2. Routes

```
/                           → OverviewPage
/search                     → SearchPage
/chat                       → ChatPage
/source/:name               → SourcePage
/source/:name/:fileId       → NoteDetail
/manage                     → ManagePage
```

### 3. Data Model Changes

**Database — no schema changes:**

- `source_project` promoted to primary dimension; backfill existing notes with `'blog'`
- `entry_type` column preserved but no longer read/written by application code
- No DDL migration (avoids SQLite column-drop complexity)

**config.toml — replace `[kb_types.*]` with `[sources.*]`:**

```toml
[sources.blog]
label = "博客"
description = "Hexo 博客文章"
icon = "BK"

[sources.agent]
label = "Agent 沉淀"
description = "Agent 自动沉淀的知识"
icon = "AG"

[sources.manual]
label = "手动录入"
description = "手动创建的知识笔记"
icon = "MN"
```

Remove all `[kb_types.*]` sections. Add `config.sources` to `KBConfig`.

### 4. Backend Changes

**New endpoint:**

```
GET  /api/v1/sources  →  return sources config from config.toml
```

**listNotes add source_project filter:**

```
GET  /api/v1/notes?source_project=blog
```

`queries.list_notes()` gains optional `source_project` parameter.

**Removed endpoint:**

```
GET  /api/v1/type-distribution
```

This route is deleted from the router. The corresponding query function (`get_type_distribution()`) is removed. `get_content_types()` (file format stats) is kept — it is unrelated to `entry_type`.

**Refactored endpoints:**

- `GET /api/v1/dashboard` — removes `type_distribution` field
- `GET /api/v1/taxonomy` — removes `entry_types` field

**Dashboard response:**

```json
{
  "notes_count": 24,
  "attachments_count": 5,
  "source_projects": [
    {"name": "blog", "count": 20, "label": "博客"},
    {"name": "agent", "count": 3, "label": "Agent 沉淀"},
    {"name": "manual", "count": 1, "label": "手动录入"}
  ],
  "index_health": {
    "notes_count": 24,
    "vectors_count": 18,
    "coverage": 0.75
  }
}
```

**Schemas to update (`schemas.py`):**

- `DashboardStats`: remove `type_distribution`
- `TaxonomyResponse`: remove `entry_types`
- `NoteBase`, `NoteCreateRequest`, `NoteUpdateRequest`: remove `entry_type` field

**Config (`config.py`):**

- Add `SourceConfig` dataclass with `label`, `description`, `icon`
- Add `sources: dict[str, SourceConfig]` to `KBConfig`
- Remove `kb_types` from `KBConfig`
- Update `load_config()` parsing

### 5. Frontend Changes

**App.vue sidebar:**

```ts
const navItems = [
  { to: '/', label: 'Overview', icon: 'OV' },
  { to: '/search', label: 'Search', icon: 'SR' },
  { to: '/chat', label: 'Chat', icon: 'AI' },
]

// Loaded from GET /api/v1/sources
const sourceTabs = [
  { to: '/source/blog', label: '博客', icon: 'BK' },
  { to: '/source/agent', label: 'Agent 沉淀', icon: 'AG' },
  { to: '/source/manual', label: '手动录入', icon: 'MN' },
]
```

Template renders navItems, then a `<hr>` divider, then sourceTabs.

**Page changes:**

| Old | New | Change |
|-----|-----|--------|
| `DashboardPage` | `OverviewPage` | Remove `TypeDistribution`; strengthen `SourceProjects` card; rename route `/` |
| `NoteList` | `SourcePage` | Filter notes by `source_project` from route `:name` param |
| `NoteDetail` | `NoteDetail` | Route changed to `/source/:name/:fileId`; back link points to source tab |
| `TypeDistribution.vue` | — | Delete |
| `ManagePage` | `ManagePage` | Source management replaces type management |

**api.ts changes:**

- Add `getSources()` calling `GET /api/v1/sources`
- Add `source_project` parameter to `listNotes()`
- Remove `getTypeDistribution()`
- Remove `DashboardStats.type_distribution`, `Taxonomy.entry_types`
- Add `SourceItem` and `SourcesConfig` types

### 6. Data Migration

One-time SQL backfill (run manually before deploying):

```sql
UPDATE notes SET source_project = 'blog'
WHERE source_project IS NULL AND status = 'published'
```

Ran once against `.kb/kb.db`. Safe and reversible — only touches rows where `source_project IS NULL`.

No DDL changes required. `entry_type` column stays but is unused.

## Implementation Plan

Split into two independent streams. The spec is the contract.

### Plan A: Backend First

1. Add `SourceConfig` to `config.py`, update `load_config()`
2. Update `config.toml` with `[sources.*]`
3. Add `GET /api/v1/sources` endpoint
4. Add `source_project` parameter to `listNotes`
5. Remove type-related endpoints and query functions
6. Update schemas: `DashboardStats`, `TaxonomyResponse`
7. Run data migration SQL
8. Tests

### Plan B: Frontend First

1. Update `api.ts` types and functions
2. Refactor `App.vue` sidebar to two-tier layout
3. Create `SourcePage` from `NoteList` template
4. Rename `DashboardPage` to `OverviewPage`, remove `TypeDistribution`
5. Delete `TypeDistribution.vue`
6. Update router
7. Restyle and verify

## Verification

- [ ] Sidebar shows function entries + source tabs with divider
- [ ] Each source tab navigates to `/source/:name` showing filtered notes
- [ ] Overview shows source distribution instead of type distribution
- [ ] Search filters by source
- [ ] All 24 existing notes visible under "博客" tab
- [ ] `GET /api/v1/dashboard` returns `source_projects` with correct counts
- [ ] `GET /api/v1/sources` returns sources config
- [ ] Type-related endpoints return 404
- [ ] Tests pass (`pytest --cov=src` with 80%+ coverage)
