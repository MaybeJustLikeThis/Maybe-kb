# P0 Product Trust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make first-use trust visible by repairing critical Chinese copy, adding a backend health/readiness API, and surfacing system health in the Overview UI.

**Architecture:** Add a pure read-model module `kb.core.health` that inspects configured paths, DB/vector counts, provider config presence, Obsidian config, and sources without calling external providers or mutating the filesystem. Expose it through the existing v1 envelope at `/api/v1/health`, consume it from `web/src/api.ts`, and render it with a compact `SystemHealth.vue` component on Overview. Guard critical copy and health semantics with focused tests.

**Tech Stack:** Python 3.11+, FastAPI, pytest, Vue 3, Vite, TypeScript.

---

### Task 1: Backend Health Read Model

**Files:**
- Create: `src/kb/core/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write failing health tests**

Create `tests/test_health.py`:

```python
from pathlib import Path

from kb.core.config import KBConfig, ObsidianConfig
from kb.core.context import AppContext
from kb.core.health import get_system_health
from kb.core.models import Note


def make_context(tmp_path: Path, *, create_dirs: bool = True) -> AppContext:
    if create_dirs:
        (tmp_path / "notes").mkdir()
        (tmp_path / "attachments").mkdir()
        (tmp_path / ".kb").mkdir()
    config = KBConfig(
        vault_path=tmp_path.resolve(),
        obsidian=ObsidianConfig(
            enabled=True,
            vault_name="TestVault",
            vault_path=tmp_path.resolve(),
        ),
    )
    return AppContext.from_config(
        config,
        with_embedding=False,
        with_llm=False,
        allow_lazy_embedding=True,
        allow_lazy_llm=True,
    )


def status_by_id(health: dict) -> dict[str, str]:
    return {check["id"]: check["status"] for check in health["checks"]}


def test_health_ready_for_empty_initialized_vault(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    try:
        health = get_system_health(ctx)
    finally:
        ctx.close()

    assert health["status"] == "ready"
    assert health["summary"] == {
        "notes_count": 0,
        "vectors_count": 0,
        "coverage": 1.0,
    }
    statuses = status_by_id(health)
    assert statuses["vault"] == "ready"
    assert statuses["notes_dir"] == "ready"
    assert statuses["attachments_dir"] == "ready"
    assert statuses["index_dir"] == "ready"
    assert statuses["obsidian"] == "ready"
    assert statuses["embedding_config"] == "ready"
    assert statuses["llm_config"] == "ready"


def test_health_errors_when_vault_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing-vault"
    config = KBConfig(vault_path=missing.resolve())
    ctx = AppContext.from_config(
        config,
        with_embedding=False,
        with_llm=False,
        allow_lazy_embedding=True,
        allow_lazy_llm=True,
    )
    try:
        health = get_system_health(ctx)
    finally:
        ctx.close()

    assert health["status"] == "error"
    assert status_by_id(health)["vault"] == "error"


def test_health_warns_when_notes_have_no_vectors(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    try:
        ctx.db.upsert_note(Note(file_id="notes/example.md", title="Example", content="Body"))
        health = get_system_health(ctx)
    finally:
        ctx.close()

    assert health["status"] == "warning"
    assert health["summary"]["notes_count"] == 1
    assert health["summary"]["vectors_count"] == 0
    assert health["summary"]["coverage"] == 0.0
    assert status_by_id(health)["vector_index"] == "warning"
```

- [ ] **Step 2: Run tests to verify RED**

Run: `py -m pytest tests/test_health.py -q`

Expected: FAIL because `kb.core.health` does not exist.

- [ ] **Step 3: Implement health read model**

Create `src/kb/core/health.py` with:

```python
from __future__ import annotations

from typing import Literal

from kb.core.context import AppContext

HealthStatus = Literal["ready", "warning", "error"]


def _check(
    check_id: str,
    label: str,
    status: HealthStatus,
    message: str,
    action: str | None = None,
) -> dict:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "message": message,
        "action": action,
    }


def _overall_status(checks: list[dict]) -> HealthStatus:
    if any(check["status"] == "error" for check in checks):
        return "error"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    return "ready"


def get_system_health(ctx: AppContext) -> dict:
    notes_count = len(ctx.db.get_all_hashes())
    vectors_count = 0
    if ctx.vector_store is not None:
        try:
            vectors_count = ctx.vector_store.count()
        except Exception:
            vectors_count = 0
    coverage = 1.0 if notes_count == 0 else (1.0 if vectors_count > 0 else 0.0)

    vault_exists = ctx.vault.is_dir()
    notes_path = ctx.vault / ctx.notes_dir
    attachments_path = ctx.vault / ctx.attachments_dir
    index_path = ctx.vault / ctx.index_dir

    checks = [
        _check(
            "vault",
            "Vault",
            "ready" if vault_exists else "error",
            "Vault path exists" if vault_exists else "Vault path is missing",
            None if vault_exists else "Check config.toml",
        ),
        _check(
            "notes_dir",
            "Notes directory",
            "ready" if notes_path.is_dir() else "error",
            "Notes directory exists" if notes_path.is_dir() else "Notes directory is missing",
            None if notes_path.is_dir() else "Create notes directory",
        ),
        _check(
            "attachments_dir",
            "Attachments directory",
            "ready" if attachments_path.is_dir() else "warning",
            "Attachments directory exists" if attachments_path.is_dir() else "Attachments directory is missing",
            None if attachments_path.is_dir() else "Create attachments directory",
        ),
        _check(
            "index_dir",
            "Index directory",
            "ready" if index_path.is_dir() else "warning",
            "Index directory exists" if index_path.is_dir() else "Index directory is missing",
            None if index_path.is_dir() else "Rebuild index",
        ),
        _check(
            "fulltext_index",
            "Full-text index",
            "ready",
            f"{notes_count} note records indexed",
        ),
        _check(
            "vector_index",
            "Vector index",
            "ready" if coverage > 0 else "warning",
            (
                f"{vectors_count} vectors indexed"
                if coverage > 0
                else "No vectors indexed yet"
            ),
            None if coverage > 0 else "Rebuild index",
        ),
    ]

    config = ctx.config
    obsidian = config.obsidian if config else None
    obsidian_ready = bool(obsidian and obsidian.enabled and (obsidian.vault_path or ctx.vault).is_dir())
    checks.append(_check(
        "obsidian",
        "Obsidian",
        "ready" if obsidian_ready else "warning",
        "Obsidian vault is configured" if obsidian_ready else "Obsidian integration is not ready",
        None if obsidian_ready else "Check Obsidian config",
    ))
    checks.append(_check(
        "embedding_config",
        "Embedding provider",
        "ready" if config and config.embedding else "warning",
        "Embedding provider is configured" if config and config.embedding else "Embedding provider is not configured",
        None if config and config.embedding else "Configure embedding",
    ))
    checks.append(_check(
        "llm_config",
        "LLM provider",
        "ready" if config and config.llm else "warning",
        "LLM provider is configured" if config and config.llm else "LLM provider is not configured",
        None if config and config.llm else "Configure LLM",
    ))

    if config and config.sources:
        for name, source in config.sources.items():
            checks.append(_check(
                f"source:{name}",
                source.label or name,
                "ready",
                source.description or "Source is configured",
            ))

    return {
        "status": _overall_status(checks),
        "checks": checks,
        "summary": {
            "notes_count": notes_count,
            "vectors_count": vectors_count,
            "coverage": coverage,
        },
    }
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `py -m pytest tests/test_health.py -q`

Expected: PASS.

### Task 2: V1 Health API

**Files:**
- Modify: `src/kb/api/schemas.py`
- Modify: `src/kb/api/v1.py`
- Modify: `tests/test_api_v1.py`

- [ ] **Step 1: Write failing API test**

Add to `tests/test_api_v1.py`:

```python
def test_v1_health_returns_system_readiness(client: TestClient) -> None:
    """GET /api/v1/health returns setup readiness in a standard envelope."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert_success_envelope(body)
    assert body["data"]["status"] in {"ready", "warning", "error"}
    assert isinstance(body["data"]["checks"], list)
    assert {
        "notes_count",
        "vectors_count",
        "coverage",
    }.issubset(body["data"]["summary"])
```

- [ ] **Step 2: Run test to verify RED**

Run: `py -m pytest tests/test_api_v1.py::test_v1_health_returns_system_readiness -q`

Expected: FAIL with 404 for `/api/v1/health`.

- [ ] **Step 3: Add schemas**

In `src/kb/api/schemas.py`, add:

```python
class HealthCheck(BaseModel):
    id: str
    label: str
    status: Literal["ready", "warning", "error"]
    message: str
    action: str | None = None


class HealthSummary(BaseModel):
    notes_count: int
    vectors_count: int
    coverage: float


class SystemHealth(BaseModel):
    status: Literal["ready", "warning", "error"]
    checks: list[HealthCheck] = Field(default_factory=list)
    summary: HealthSummary
```

- [ ] **Step 4: Add v1 route**

In `src/kb/api/v1.py`:

```python
from kb.core.health import get_system_health
```

Add:

```python
@router.get("/health", response_model=ApiResponse[SystemHealth])
def get_health():
    return responses.ok(get_system_health(ctx))
```

- [ ] **Step 5: Run API test**

Run: `py -m pytest tests/test_api_v1.py::test_v1_health_returns_system_readiness -q`

Expected: PASS.

### Task 3: Frontend API And System Health Component

**Files:**
- Modify: `web/src/api.ts`
- Create: `web/src/components/SystemHealth.vue`
- Modify: `web/src/pages/OverviewPage.vue`
- Create or modify: `tests/test_web_health.py`

- [ ] **Step 1: Write failing static frontend tests**

Create `tests/test_web_health.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_api_exposes_system_health_client() -> None:
    api_ts = read("web/src/api.ts")
    assert "export type HealthStatus" in api_ts
    assert "interface HealthCheck" in api_ts
    assert "interface SystemHealth" in api_ts
    assert "getHealth()" in api_ts
    assert "request<SystemHealth>('/health')" in api_ts


def test_overview_renders_system_health_panel() -> None:
    component = read("web/src/components/SystemHealth.vue")
    overview = read("web/src/pages/OverviewPage.vue")
    assert "System Health" in component
    assert "Needs attention" in component
    assert "Setup issue" in component
    assert "Rebuild index" in component
    assert "SystemHealth" in overview
    assert "api.getHealth()" in overview
```

- [ ] **Step 2: Run frontend tests to verify RED**

Run: `py -m pytest tests/test_web_health.py -q`

Expected: FAIL because API types/component do not exist.

- [ ] **Step 3: Add API types and method**

In `web/src/api.ts`, add:

```ts
export type HealthStatus = 'ready' | 'warning' | 'error'

export interface HealthCheck {
  id: string
  label: string
  status: HealthStatus
  message: string
  action: string | null
}

export interface SystemHealth {
  status: HealthStatus
  checks: HealthCheck[]
  summary: {
    notes_count: number
    vectors_count: number
    coverage: number
  }
}
```

Inside `api`:

```ts
getHealth() {
  return request<SystemHealth>('/health')
},
```

- [ ] **Step 4: Add SystemHealth component**

Create `web/src/components/SystemHealth.vue` with:

```vue
<template>
  <section class="card system-health">
    <div class="system-health-header">
      <div>
        <h3 class="section-heading">System Health</h3>
        <p>{{ subtitle }}</p>
      </div>
      <span :class="['health-pill', `health-${health.status}`]">{{ statusLabel }}</span>
    </div>

    <div class="health-summary">
      <div>
        <strong>{{ health.summary.notes_count }}</strong>
        <span>notes</span>
      </div>
      <div>
        <strong>{{ health.summary.vectors_count }}</strong>
        <span>vectors</span>
      </div>
      <div>
        <strong>{{ Math.round(health.summary.coverage * 100) }}%</strong>
        <span>coverage</span>
      </div>
    </div>

    <ul class="health-checks">
      <li v-for="check in visibleChecks" :key="check.id" :class="`check-${check.status}`">
        <div>
          <strong>{{ check.label }}</strong>
          <p>{{ check.message }}</p>
        </div>
        <span>{{ check.action || check.status }}</span>
      </li>
    </ul>

    <button
      v-if="showRebuild"
      type="button"
      class="btn btn-primary"
      :disabled="rebuilding"
      @click="$emit('rebuild')"
    >
      Rebuild index
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SystemHealth } from '../api'

const props = defineProps<{
  health: SystemHealth
  rebuilding?: boolean
}>()

defineEmits<{ rebuild: [] }>()

const statusLabel = computed(() => {
  if (props.health.status === 'ready') return 'Ready'
  if (props.health.status === 'warning') return 'Needs attention'
  return 'Setup issue'
})

const subtitle = computed(() => {
  if (props.health.status === 'ready') return 'Local knowledge is ready.'
  if (props.health.status === 'warning') return 'Some capabilities need attention.'
  return 'Setup issue blocks trustworthy results.'
})

const visibleChecks = computed(() => {
  const actionable = props.health.checks.filter((check) => check.status !== 'ready')
  return actionable.length ? actionable : props.health.checks.slice(0, 4)
})

const showRebuild = computed(() =>
  props.health.checks.some((check) =>
    check.action?.toLowerCase().includes('rebuild'),
  ),
)
</script>
```

Add scoped CSS using existing card/button conventions.

- [ ] **Step 5: Add SystemHealth to Overview**

In `web/src/pages/OverviewPage.vue`:
- Import `SystemHealth`.
- Add `const health = ref<SystemHealth | null>(null)`.
- Load `api.getHealth()` in the first `Promise.all`.
- Render `<SystemHealth v-if="health" :health="health" :rebuilding="reindexing" @rebuild="handleReindex" />` near `IndexHealth`.
- Add `const reindexing = ref(false)`, set it while rebuilding, and refresh dashboard/health after rebuild if practical.

- [ ] **Step 6: Run frontend static tests**

Run: `py -m pytest tests/test_web_health.py -q`

Expected: PASS.

### Task 4: Critical Copy And Mojibake Guards

**Files:**
- Modify: `README.md`
- Modify: `USER_GUIDE.md`
- Modify: `config.toml`
- Modify: `web/src/App.vue`
- Create: `tests/test_product_copy.py`

- [ ] **Step 1: Write failing copy tests**

Create `tests/test_product_copy.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_FILES = [
    "README.md",
    "USER_GUIDE.md",
    "config.toml",
    "web/src/App.vue",
]
MOJIBAKE_FRAGMENTS = [
    "鏈",
    "鍗",
    "鎵",
    "娌夋穩",
    "鐭",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_critical_user_facing_copy_has_no_known_mojibake() -> None:
    for path in CRITICAL_FILES:
        text = read(path)
        for fragment in MOJIBAKE_FRAGMENTS:
            assert fragment not in text, f"{path} contains mojibake fragment {fragment!r}"


def test_critical_chinese_labels_are_readable() -> None:
    config = read("config.toml")
    app_vue = read("web/src/App.vue")
    readme = read("README.md")
    guide = read("USER_GUIDE.md")

    for text in [config, app_vue]:
        assert "博客" in text
        assert "Agent 沉淀" in text
        assert "手动录入" in text
        assert "未分类" in text

    assert "本地优先" in readme
    assert "快速开始" in readme
    assert "系统健康" in guide
```

- [ ] **Step 2: Run copy tests to verify RED**

Run: `py -m pytest tests/test_product_copy.py -q`

Expected: FAIL because current committed copy contains mojibake.

- [ ] **Step 3: Repair README.md**

Replace current mojibake-heavy README with concise UTF-8 content:

```markdown
# kb - 本地优先知识库

`kb` 是一个本地优先的个人知识系统，用 Markdown 作为知识源，提供全文搜索、语义搜索、RAG 问答、Web 管理界面和 MCP Agent 接入。

## 快速开始

```bash
pip install -e .
kb init
kb index --full
kb serve
```

打开 `http://127.0.0.1:8420` 查看 Overview，并先检查 System Health。

## 核心能力

- Markdown + YAML frontmatter 笔记管理
- SQLite FTS5 + jieba 全文搜索
- LanceDB + embedding 语义搜索
- Hybrid Search 和 RAG Chat
- Obsidian 打开目标集成
- MCP 工具接入 Claude Code / Codex 等 Agent
- 本地索引可重建，知识源保持为普通文件

## 常用命令

```bash
kb add "标题"
kb search "关键词"
kb ask "根据我的知识库回答一个问题"
kb index --full
kb serve --skip-watch
```

## 配置

编辑 `config.toml` 设置 vault、embedding、LLM、Obsidian 和来源。

重要默认标签：

- 博客
- Agent 沉淀
- 手动录入
- 未分类
```

- [ ] **Step 4: Repair USER_GUIDE.md**

Replace with concise first-use guide including `系统健康`:

```markdown
# kb 使用手册

## 1. 安装

```bash
pip install -e .
kb --help
```

## 2. 初始化

```bash
kb init
kb index --full
kb serve
```

## 3. 系统健康

打开 Web UI 后先查看 Overview 的 System Health。它会显示 vault、notes、attachments、index、Obsidian、embedding、LLM 和向量覆盖率是否就绪。

如果看到 `Rebuild index`，先运行：

```bash
kb index --full
```

## 4. 搜索与问答

```bash
kb search "关键词"
kb ask "问题"
```

Web UI 中可以使用 Search Workbench 和 Knowledge Chat。

## 5. 常见来源

- 博客：Hexo 或其他 Markdown 博客内容
- Agent 沉淀：由 Agent 写入或整理的知识
- 手动录入：人工创建的笔记
- 未分类：缺少分类时的默认分类
```

- [ ] **Step 5: Repair config.toml and App.vue fallback labels**

In `config.toml`, set:

```toml
[sources.blog]
label = "博客"
description = "Hexo 博客文章"
icon = "BK"
default_category = "未分类"
auto_tags = []
```

Set agent/manual labels and descriptions similarly:
- `Agent 沉淀`
- `Agent 自动沉淀的知识`
- `手动录入`
- `手动创建的知识笔记`

In `web/src/App.vue` fallback labels:

```ts
sourceTabs.value = [
  { to: '/source/blog', label: '博客', icon: 'BK' },
  { to: '/source/agent', label: 'Agent 沉淀', icon: 'AG' },
  { to: '/source/manual', label: '手动录入', icon: 'MN' },
]
```

- [ ] **Step 6: Run copy tests**

Run: `py -m pytest tests/test_product_copy.py -q`

Expected: PASS.

### Task 5: Final Verification

**Files:**
- No new files unless verification reveals a regression.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
py -m pytest tests/test_health.py tests/test_api_v1.py::test_v1_health_returns_system_readiness tests/test_web_health.py tests/test_product_copy.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run from `web/`: `npm run build`

Expected: exit code 0.

- [ ] **Step 3: Run full test suite**

Run: `py -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Review diff**

Run: `git diff --stat`

Expected: diff is limited to health model/API/UI, copy repair, tests, and plan/spec files.

