# P1 Control Center Design

## Goal

Turn the existing `Manage` page into an actionable maintenance control center so users can move from "the system says something needs attention" to "I know what to do next" without leaving the Web UI.

## Background

The P0 Product Trust pass added `/api/v1/health` and a visible `System Health` panel on Overview. That solved first-use confidence: users can now see whether the vault, notes directory, attachments, index, Obsidian, embedding, LLM, and vector coverage are ready.

The next product gap is actionability. `Manage` still shows a narrow index summary, its rebuild action has no visible progress or result, and source management displays raw source keys instead of configured labels. The user can see health status on Overview, but there is no dedicated operational surface for fixing or verifying those issues.

## Scope

Included:

- Upgrade `Manage` into a maintenance control center.
- Add a health tab or default health section using the existing `/api/v1/health` response.
- Reuse the existing `SystemHealth.vue` component where practical.
- Make index rebuild actions visible, stateful, and refresh health/index data after completion.
- Display success and failure feedback for rebuild actions.
- Make source rows use configured labels and descriptions from `/api/v1/sources` where available, while preserving note counts from dashboard stats.
- Add focused tests for frontend API usage, Manage rendering expectations, and source label behavior.

Excluded:

- Full multi-step setup wizard.
- Automatic config rewriting or self-healing.
- External provider connectivity checks that call embedding or LLM services.
- PDF/DOCX/image import flow.
- Large Obsidian-first redesign of NoteDetail or SourcePage. Minor navigation/copy adjustments are allowed only if they support the Manage control center.

## Product Experience

When users open `Manage`, they should immediately understand:

- Overall system status: ready, warning, or setup issue.
- Which setup/index/provider checks need attention.
- Whether the local index has notes and vectors.
- Whether rebuilding the index is currently running.
- Whether the last rebuild succeeded or failed.
- Which source groups exist, using readable labels such as `博客`, `Agent 沉淀`, and `手动录入`.

The page should feel like an operational console, not a marketing page or a config editor. Copy should be direct:

- `System Health`
- `Ready`
- `Needs attention`
- `Setup issue`
- `Rebuild index`
- `Index rebuilt`
- `Index rebuild failed`
- `Refresh`

## Frontend Design

### Manage Layout

`ManagePage.vue` keeps the current tab structure but changes the default tab from `source` to `health`.

Tabs:

- `Health`: complete setup and index readiness.
- `Sources`: configured source groups with counts.
- `Categories`: existing category list.
- `Tags`: existing tag cloud.
- `Index`: compact index metrics and rebuild action.

The `Health` tab renders `SystemHealth.vue` with:

- `health` from `api.getHealth()`.
- `rebuilding` state from `ManagePage`.
- `@rebuild="handleReindex"`.

The `Index` tab remains useful for compact numeric metrics, but it shares the same `handleReindex()` flow and visible status feedback.

### Rebuild Feedback

`ManagePage.vue` owns:

- `reindexing: Ref<boolean>`
- `notice: Ref<{ type: 'success' | 'error'; message: string } | null>`
- `loadDashboardData()`
- `loadHealthData()`
- `refreshManageData()`
- `handleReindex()`

Behavior:

1. User clicks `Rebuild index`.
2. Button disables and shows a running state.
3. API calls `api.triggerIndex()`.
4. On success, show `Index rebuilt: X notes, Y vectors.`
5. Refresh dashboard-derived data and `/health`.
6. On failure, show `Index rebuild failed` with the error message.
7. Always clear `reindexing` when complete.

### Source Rows

`ManagePage.vue` should combine:

- counts from `api.getSourceProjects()` / dashboard data
- labels, descriptions, and icons from `api.getSources()`

If a source appears in config but has zero notes, it should still appear. If a source appears in counts but not config, it should fall back to the raw name.

Source rows should link to `/source/:name`.

## Backend Design

No new backend endpoint is required.

Existing endpoints are enough:

- `GET /api/v1/health`
- `GET /api/v1/dashboard`
- `GET /api/v1/sources`
- `POST /api/v1/index/rebuild`
- `GET /api/v1/taxonomy`

If implementation discovers that `/api/v1/sources` lacks fields needed by the frontend, extend the existing `SourceItem` schema and response in a backward-compatible way. Do not add a new source endpoint for this pass.

## Error Handling

The page should avoid silent failures for operational actions.

Initial load:

- If required page data fails, show the existing full-page error state.

Health load:

- If health load fails but taxonomy/dashboard data succeeds, show a health-specific inline error in the Health tab.

Rebuild:

- On success, show success notice.
- On API error, show error notice and keep existing health/index data visible.
- The rebuild button must re-enable after both success and failure.

Source labels:

- If `/api/v1/sources` fails, source counts still render with raw names.

## Testing

Focused tests should guard the product contract without relying on a browser runtime:

- `tests/test_manage_control_center.py`
  - `ManagePage.vue` imports `SystemHealth`.
  - `ManagePage.vue` calls `api.getHealth()`.
  - `ManagePage.vue` calls `api.getSources()`.
  - `ManagePage.vue` defaults to a health tab.
  - `ManagePage.vue` contains user-visible rebuild success and failure copy.
  - `ManagePage.vue` wires `SystemHealth` with `@rebuild`.

Existing tests should continue to pass:

- `tests/test_web_health.py`
- `tests/test_product_copy.py`
- backend health/API tests

Manual verification:

- `py -m pytest tests/test_manage_control_center.py tests/test_web_health.py tests/test_product_copy.py -q`
- `npm run build`
- `py -m pytest -q`

## Rollout

This is a local UI/product improvement. It does not require data migration and does not change the health API contract.

## Success Criteria

- A user can open Manage and immediately see system readiness.
- Rebuilding the index gives visible progress and result feedback.
- Health and index numbers refresh after rebuild.
- Source rows use readable configured labels and preserve navigation.
- The UI no longer hides rebuild failures behind silent catches.
