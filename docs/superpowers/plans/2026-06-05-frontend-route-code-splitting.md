# Frontend Route Code Splitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the initial Vite JavaScript chunk by lazy-loading Vue page components at route navigation time.

**Architecture:** Keep the router in `web/src/main.ts`, but replace static page imports with Vue Router dynamic import component loaders. Add a lightweight Python regression test that prevents page components from being imported eagerly again. Verify with `npm run build` and inspect emitted chunk sizes.

**Tech Stack:** Vue 3, Vue Router 4, Vite 5, pytest.

---

### Task 1: Guard Against Eager Page Imports

**Files:**
- Create: `tests/test_web_routes.py`
- Read: `web/src/main.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_routes.py`:

```python
from pathlib import Path


def test_page_routes_are_lazy_loaded() -> None:
    """Vue page components should be loaded with dynamic imports."""
    main_ts = Path("web/src/main.ts").read_text(encoding="utf-8")

    pages = [
        "OverviewPage",
        "SourcePage",
        "NoteDetail",
        "SearchPage",
        "ChatPage",
        "ManagePage",
    ]

    for page in pages:
        assert f"import {page} from './pages/" not in main_ts

    for path in [
        "./pages/OverviewPage.vue",
        "./pages/SourcePage.vue",
        "./pages/NoteDetail.vue",
        "./pages/SearchPage.vue",
        "./pages/ChatPage.vue",
        "./pages/ManagePage.vue",
    ]:
        assert f"() => import('{path}')" in main_ts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_web_routes.py -q`

Expected: FAIL because `web/src/main.ts` currently statically imports page components.

### Task 2: Convert Routes To Dynamic Imports

**Files:**
- Modify: `web/src/main.ts`
- Test: `tests/test_web_routes.py`

- [ ] **Step 1: Replace static imports with route loaders**

Change `web/src/main.ts` to:

```ts
import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './assets/base.css'

const routes = [
  { path: '/', component: () => import('./pages/OverviewPage.vue') },
  { path: '/source/:name', component: () => import('./pages/SourcePage.vue'), props: true },
  { path: '/source/:name/:fileId', component: () => import('./pages/NoteDetail.vue'), props: true },
  { path: '/note/:fileId', component: () => import('./pages/NoteDetail.vue'), props: true },
  { path: '/manage', component: () => import('./pages/ManagePage.vue') },
  { path: '/search', component: () => import('./pages/SearchPage.vue') },
  { path: '/chat', component: () => import('./pages/ChatPage.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
```

- [ ] **Step 2: Run route test**

Run: `py -m pytest tests/test_web_routes.py -q`

Expected: PASS.

### Task 3: Shrink Markdown Highlighting Imports

**Files:**
- Create: `web/src/markdown.ts`
- Modify: `web/src/pages/NoteDetail.vue`
- Modify: `web/src/components/MarkdownEditor.vue`
- Test: `tests/test_web_routes.py`

- [ ] **Step 1: Extend the failing test**

Add this test to `tests/test_web_routes.py`:

```python
def test_markdown_rendering_uses_highlight_core() -> None:
    """Markdown rendering should not import the full highlight.js bundle."""
    note_detail = Path("web/src/pages/NoteDetail.vue").read_text(encoding="utf-8")
    editor = Path("web/src/components/MarkdownEditor.vue").read_text(encoding="utf-8")
    markdown = Path("web/src/markdown.ts").read_text(encoding="utf-8")

    assert "from 'highlight.js'" not in note_detail
    assert "from 'highlight.js'" not in editor
    assert "highlight.js/lib/core" in markdown
```

Expected before implementation: FAIL because `web/src/markdown.ts` does not exist and both Vue files import full `highlight.js`.

- [ ] **Step 2: Create shared markdown renderer**

Create `web/src/markdown.ts` with a `renderMarkdown()` function that imports `highlight.js/lib/core`, registers `javascript`, `typescript`, `python`, `bash`, `json`, `xml`, `css`, `markdown`, and sanitizes marked output with DOMPurify.

- [ ] **Step 3: Use shared renderer in both Vue files**

In `web/src/pages/NoteDetail.vue` and `web/src/components/MarkdownEditor.vue`, remove `Marked`, `marked-highlight`, `DOMPurify`, and full `highlight.js` imports. Import `renderMarkdown` from `../markdown` or `./markdown` as appropriate, then keep each component's existing relative image rewrite logic.

- [ ] **Step 4: Run markdown import test**

Run: `py -m pytest tests/test_web_routes.py::test_markdown_rendering_uses_highlight_core -q`

Expected: PASS.

### Task 4: Verify Build Output

**Files:**
- No further modifications unless build fails.

- [ ] **Step 1: Run frontend build**

Run from `web/`: `npm run build`

Expected: exit code 0. The initial `index-*.js` chunk should be substantially smaller than the previous `1,134.23 kB`.

- [ ] **Step 2: Run focused backend/frontend guard tests**

Run: `py -m pytest tests/test_web_routes.py tests/test_server.py::test_create_app_does_not_initialize_ai_providers tests/test_server.py::test_v1_create_note_does_not_initialize_ai_providers -q`

Expected: PASS.

- [ ] **Step 3: Review diff**

Run: `git diff -- web/src/main.ts tests/test_web_routes.py docs/superpowers/plans/2026-06-05-frontend-route-code-splitting.md`

Expected: diff contains only route lazy loading, its regression test, and the plan.
