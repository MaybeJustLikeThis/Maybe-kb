# P0 Product Trust Design

## Goal

Make `kb` feel trustworthy on first use by showing whether the local knowledge system is correctly configured, indexed, and ready for search/RAG, while fixing obvious Chinese encoding damage in user-facing project text.

## Problem

The product has strong local knowledge capabilities, but the first impression is weakened by three P0 issues:

1. User-facing Chinese text in docs/config/UI fallbacks can appear corrupted, which makes the project feel unreliable.
2. Users cannot quickly tell whether their vault, notes, attachments, index, Obsidian integration, embedding provider, and LLM provider are ready.
3. Index health exists as a metric, but it is not framed as an actionable setup/trust checklist.

This creates a product-level confidence gap: users may not know whether `kb` knows their content, whether missing answers are caused by configuration, or what to do next.

## Scope

This P0 pass implements a compact trust loop, not a full setup wizard.

Included:
- Repair obvious garbled Chinese labels/defaults in committed user-facing files.
- Add a backend health/readiness read model.
- Expose that read model through `/api/v1/health`.
- Add a visible System Health panel in the existing Web UI, preferably on Overview and/or Manage Index, without creating a new top-level flow.
- Add tests that guard health semantics and prevent regression of critical labels.

Excluded:
- Automatic config rewriting or self-healing.
- Multi-step onboarding wizard.
- Account/user management.
- Cloud sync.
- Deep provider connectivity checks that call external LLM/embedding services.

## Product Experience

The user should be able to answer these questions within one screen:

- Is my vault path valid?
- Are notes and attachments directories present?
- Does the local index exist?
- How many notes and vectors are indexed?
- Is vector coverage healthy enough to trust semantic search/RAG?
- Is Obsidian configured and pointing to a valid vault?
- Are embedding and LLM providers configured?
- What is the next action when something is missing?

The UI should use direct operational language:

- `Ready`
- `Needs setup`
- `Missing directory`
- `No vectors indexed`
- `Configure LLM`
- `Rebuild index`

Avoid marketing copy. This is an operational trust surface.

## Backend Design

Create a health read model in `src/kb/core/health.py`.

Responsibilities:
- Inspect configured paths without mutating the filesystem.
- Summarize provider configuration presence without calling providers.
- Reuse existing database/vector abstractions where possible.
- Return stable dictionaries suitable for API serialization and tests.

Suggested response shape:

```json
{
  "status": "ready",
  "checks": [
    {
      "id": "vault",
      "label": "Vault",
      "status": "ready",
      "message": "Vault path exists",
      "action": null
    },
    {
      "id": "vector_index",
      "label": "Vector index",
      "status": "warning",
      "message": "No vectors indexed yet",
      "action": "Rebuild index"
    }
  ],
  "summary": {
    "notes_count": 12,
    "vectors_count": 48,
    "coverage": 1.0
  }
}
```

Status rules:
- `ready`: all required checks are ready and vector coverage is nonzero when notes exist.
- `warning`: required paths exist, but optional capability or index coverage needs attention.
- `error`: vault path or configured subdirectories are missing or invalid.

Health checks:
- `vault`
- `notes_dir`
- `attachments_dir`
- `index_dir`
- `fulltext_index`
- `vector_index`
- `obsidian`
- `embedding_config`
- `llm_config`
- one check per configured source group when source metadata is present

Add `GET /api/v1/health` in `src/kb/api/v1.py`, returning the normal v1 response envelope.

## Frontend Design

Add health types and API client method to `web/src/api.ts`.

Add a compact component `web/src/components/SystemHealth.vue`.

Component behavior:
- Shows overall status: Ready / Needs attention / Setup issue.
- Lists checks grouped by severity.
- Shows notes count, vectors count, and coverage.
- Offers a `Rebuild index` action when vector/index checks are warning/error.
- Uses existing button, card, badge, and color conventions.

Placement:
- Add to `OverviewPage.vue`, near existing `IndexHealth`, because Overview is the default first screen.
- Avoid adding a new sidebar item in this P0 pass.

## Encoding And Copy Repair

Repair committed user-facing text that is visibly corrupted:

- `README.md`
- `USER_GUIDE.md`
- `config.toml`
- fallback source labels in `web/src/App.vue`

Minimum required labels:
- Blog source label: Chinese text for "blog".
- Agent source label: Chinese text for "agent-captured knowledge".
- Manual source label: Chinese text for "manual entry".
- Uncategorized default: Chinese text for "uncategorized".
- Product noun: Chinese text for "knowledge base".
- Positioning phrase: Chinese text for "local-first".

Documentation repair should focus on first-use trust:
- Keep quick start readable.
- Keep configuration examples readable.
- Remove obsolete phase-heavy noise if it obscures first-use instructions.

## Testing

Backend tests:
- Health returns `ready` for an initialized temp vault with required directories.
- Health returns `error` when the vault path is missing.
- Health returns `warning` when notes exist but vectors are missing.
- `/api/v1/health` returns the standard envelope.

Frontend/static tests:
- API client exposes `getHealth`.
- `SystemHealth.vue` renders status labels and rebuild action text.
- No critical committed labels contain known mojibake fragments.

Manual verification:
- `py -m pytest -q`
- `npm run build`

## Rollout

This feature is safe to ship as a local-only product improvement.

No migration is required. Existing config continues to work. If `config.toml` currently contains corrupted labels, this pass fixes the committed project config only; external user configs should be reported by health checks but not rewritten automatically.

## Success Criteria

- A first-time user can open Overview and see whether the system is ready.
- Missing vault/index/provider states produce clear messages and next actions.
- Critical Chinese user-facing copy in committed docs/config/fallback UI is readable.
- All tests and frontend build pass.
