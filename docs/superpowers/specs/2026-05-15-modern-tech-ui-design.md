# Modern Tech UI Design

Date: 2026-05-15
Branch: codex/modern-tech-ui

## Goal

Refresh the knowledge base web UI into a modern, technical interface without making it visually heavy. The chosen direction is Bright Control Center: a bright primary workspace, a dark navigation rail as the technical anchor, and restrained cyan/indigo data accents.

The implementation focuses on the highest-use surfaces:

- Overview
- Search
- Chat

Notes, Manage, and Note Detail should inherit the refreshed shell and shared tokens, but their information architecture stays largely unchanged.

## Visual Direction

Use a light, breathable application canvas instead of a full dark dashboard. The side navigation remains dark navy to create a control-center feel, while the main workspace uses cool light backgrounds, white or translucent panels, fine blue-gray borders, and subtle depth.

The palette should avoid a single-color look. Recommended roles:

- Dark shell: navy and near-slate for the sidebar and compact status surfaces.
- Primary accent: cyan for system health, active navigation, and high-confidence status.
- Secondary accent: indigo for AI/search affordances and selected states.
- Supporting accents: teal and amber only for semantic states such as healthy/warning.
- Main surfaces: white, light blue-gray, and lightly tinted panels.

Typography should stay compact and product-focused. Headings should be confident but not hero-sized. Cards should use an 8px radius or less unless the existing control benefits from a slightly larger surface radius.

## Architecture

Keep the existing Vue 3 + Tailwind structure and FastAPI v1 API model.

Frontend changes should center on:

- `web/src/App.vue` for the global shell.
- `web/src/assets/base.css` for design tokens and shared component classes.
- `web/src/pages/DashboardPage.vue` for the Overview control center.
- `web/src/pages/SearchPage.vue` for the retrieval workbench.
- `web/src/pages/ChatPage.vue` for the assistant panel.
- Existing small dashboard components where they can be restyled without broad rewrites.
- `web/src/api.ts` for the new activity API client method and types.

Backend changes should follow the existing read-model pattern:

- Add `get_dashboard_activity(ctx, limit)` to `src/kb/core/queries.py`.
- Add `GET /api/v1/dashboard/activity` near the existing dashboard route in `src/kb/api/v1.py`.
- Continue wrapping responses with `responses.ok(...)`.
- Do not change note creation, indexing, or storage behavior.

## Frontend Design

### Global Shell

The sidebar becomes a dark technical rail with a stronger brand block, clear active item state, and concise nav items. It should avoid emoji icons and use simple text or CSS/icon-friendly symbols available in the project. The main content area becomes a cool light workspace with a subtle background treatment and constrained content width where useful.

The top bar used by detail/edit pages should become a slim command bar with a light translucent surface, a clear back affordance, and consistent button styles.

### Shared Tokens And Controls

`base.css` should provide the design language:

- App background, panel, elevated panel, border, sidebar, text, muted text, and accent variables.
- `.card`, `.btn`, `.input`, `.badge`, `.empty-state`, `.section-heading`, and `.divider` updated to the Bright Control Center style.
- Focus states should be visible and cyan/indigo tinted.
- Hover states should feel crisp without large shadows or heavy animation.

Inline color styles should be reduced where practical and replaced with token-backed classes.

### Overview

Overview should become the main control center. It should include:

- A compact page header with status context and a primary action to rebuild or refresh index state.
- Metric cards for notes, types, categories, tags, and attachments using the refreshed data-card treatment.
- Index health with clear coverage, note count, and vector count.
- Type/source/content distribution surfaces that feel like dashboard panels rather than plain lists.
- A recent activity rail fed by the new dashboard activity endpoint.
- Existing quick actions and recent notes can remain, but should visually integrate with the control-center layout.

If the new activity endpoint fails, the page should still render the existing dashboard data and show a quiet activity fallback.

### Search

Search should become a retrieval workbench:

- A prominent but not oversized search input.
- Result cards with title, category, tags, source, and optional chunk text if returned.
- Empty and loading states that match the new visual system.
- No backend search contract changes in this iteration.

### Chat

Chat should become an assistant panel:

- Light workspace with crisp message bubbles.
- User messages can use the primary accent; assistant messages should use elevated light panels.
- The input area should feel like a command bar.
- Provider-not-configured errors should be displayed as a friendly state rather than a raw-looking failure.

## Backend API

Add:

`GET /api/v1/dashboard/activity?limit=8`

Response data:

```json
[
  {
    "kind": "note_updated",
    "title": "Note title",
    "description": "Updated note metadata or source context",
    "timestamp": "2026-05-15T10:00:00",
    "note": {
      "file_id": "notes/example.md",
      "title": "Note title"
    }
  }
]
```

The exact timestamp format should match the existing note metadata strings. Empty databases return an empty array. The route uses the same v1 envelope:

```json
{ "data": [], "meta": {}, "error": null }
```

Activity ordering should be newest first, using `updated_at` when available and `created_at` as a fallback. The first implementation should derive activity from existing notes only, avoiding new persistence.

## Data Flow

Overview loads the existing dashboard/taxonomy/note data as it does today, plus `api.getDashboardActivity({ limit: 8 })`. The new endpoint reads from the existing database through `queries.py`, serializes lightweight activity items, and returns a normal v1 envelope.

Search continues to call `/api/v1/search`. Chat continues to call `/api/v1/chat/ask`.

## Error Handling

Frontend:

- Dashboard activity failure should not block the Overview.
- Search and Chat loading states should remain explicit.
- Chat provider configuration errors should map to a user-friendly assistant/system message.

Backend:

- The activity endpoint validates `limit` with a small bounded range.
- Empty results are successful.
- Unexpected failures should follow existing FastAPI behavior unless a local helper is already used for that class of failure.

## Testing

Backend:

- Add a v1 API test for `/api/v1/dashboard/activity`.
- Verify the envelope shape, empty state, bounded limit behavior if practical, and newest-first note activity when notes exist.

Frontend:

- Run `npm run build` in `web`.
- If visual verification is available during implementation, load the app and inspect Overview, Search, and Chat at desktop width. Check that text does not overlap and the interface is not overly dark.

## Out Of Scope

- Reworking note creation/editing flows.
- Changing search ranking or adding highlight generation.
- Streaming chat.
- Replacing the frontend framework or adding a component library.
- Adding persistent activity/event tables.

