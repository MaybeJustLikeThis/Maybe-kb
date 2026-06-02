# Local Markdown Image Asset Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically collect local Markdown image assets during article sync, persist them as note attachments, and expose attachment/source metadata in the Web UI.

**Architecture:** Add a focused Markdown asset collector that rewrites local image links through the existing attachment store, then call it from external-source sync before notes are indexed. Frontend changes consume the new RAG source and note attachment metadata without changing backend note semantics.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, PyYAML, pytest, FastAPI, Vue 3, TypeScript, Vite.

---

## Scope Check

This plan implements only local Markdown image collection and UI metadata visibility.

In scope:

- Local relative Markdown image links.
- Hexo-style post asset directories.
- Existing `attachments/...` Markdown links.
- External-source sync integration.
- Chat source display.
- Note detail source/attachment display.
- Search mode switching.
- Editor manual upload helper.

Out of scope:

- Remote image download.
- Data URI conversion.
- HTML `<img>` parsing.
- OCR, captioning, or image understanding.
- Import API for PDF/DOCX/images.

## File Structure

- Create: `src/kb/core/markdown_assets.py`
  - Owns Markdown image scanning, local path resolution, attachment storage, and Markdown link rewriting.
- Create: `tests/test_markdown_assets.py`
  - Unit tests for image collection behavior.
- Modify: `src/kb/core/indexer.py`
  - Calls the collector for external-source Markdown sync and merges collected attachments into frontmatter.
- Modify: `tests/test_indexer.py`
  - Integration tests for external sync with local images and Hexo asset folders.
- Modify: `src/kb/api/schemas.py`
  - Corrects chat source schema shape from note summary to RAG source.
- Modify: `web/src/api.ts`
  - Adds `RAGSource`, `SearchMode`, attachment upload API, and correct chat source typing.
- Modify: `web/src/pages/ChatPage.vue`
  - Stores and renders answer sources.
- Modify: `web/src/pages/NoteDetail.vue`
  - Shows source metadata and attachments in read mode.
- Modify: `web/src/pages/SearchPage.vue`
  - Adds fulltext/hybrid/semantic mode selection.
- Modify: `web/src/components/MarkdownEditor.vue`
  - Adds manual upload-and-insert helper.

## Task 1: Add Markdown Image Asset Collector

**Files:**
- Create: `tests/test_markdown_assets.py`
- Create: `src/kb/core/markdown_assets.py`

- [ ] **Step 1: Write failing collector tests**

Create `tests/test_markdown_assets.py`:

```python
"""Tests for local Markdown image asset collection."""
from __future__ import annotations

from pathlib import Path

from kb.core.markdown_assets import collect_markdown_image_assets


def test_collect_relative_image_stores_attachment_and_rewrites_link(tmp_path: Path):
    """A relative Markdown image is copied to attachments and rewritten."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    post_dir = source_root / "posts"
    post_dir.mkdir(parents=True)
    image = post_dir / "diagram.png"
    image.write_bytes(b"png-bytes")
    post = post_dir / "post.md"
    post.write_text("![Diagram](./diagram.png)\n", encoding="utf-8")

    result = collect_markdown_image_assets(
        post.read_text(encoding="utf-8"),
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    assert result.attachments == [result.attachments[0]]
    rel = result.attachments[0]
    assert rel.startswith("attachments/")
    assert rel.endswith(".png")
    assert (vault / rel).read_bytes() == b"png-bytes"
    assert result.content == f"![Diagram]({rel})\n"
    assert result.warnings == []


def test_collect_hexo_bare_image_uses_post_asset_folder(tmp_path: Path):
    """A bare image filename can resolve through the Hexo same-stem asset folder."""
    vault = tmp_path / "vault"
    source_root = tmp_path / "blog"
    post_dir = source_root / "posts"
    asset_dir = post_dir / "my-post"
    asset_dir.mkdir(parents=True)
    (asset_dir / "cover.jpg").write_bytes(b"jpg-bytes")
    post = post_dir / "my-post.md"
    markdown = "![Cover](cover.jpg \"Hero\")\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=vault,
    )

    rel = result.attachments[0]
    assert rel.startswith("attachments/")
    assert rel.endswith(".jpg")
    assert result.content == f"![Cover]({rel} \"Hero\")\n"


def test_collect_existing_attachment_link_is_recorded_but_not_rewritten(tmp_path: Path):
    """Existing vault attachment links stay stable and are returned as attachments."""
    post = tmp_path / "post.md"
    markdown = "![Stored](attachments/2026/06/abc.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == ["attachments/2026/06/abc.png"]
    assert result.warnings == []


def test_collect_ignores_remote_data_and_root_relative_links(tmp_path: Path):
    """Non-local image targets are ignored by this phase."""
    post = tmp_path / "post.md"
    markdown = "\n".join([
        "![Remote](https://example.com/a.png)",
        "![Data](data:image/png;base64,abc)",
        "![Root](/images/a.png)",
        "",
    ])

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == []


def test_collect_missing_local_image_keeps_link_and_warns(tmp_path: Path):
    """Missing images do not break sync; they leave the original link in place."""
    post = tmp_path / "post.md"
    markdown = "![Missing](missing.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=tmp_path,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["missing image: missing.png"]


def test_collect_blocks_paths_outside_source_root(tmp_path: Path):
    """Image paths resolving outside source_root are left unchanged with a warning."""
    source_root = tmp_path / "blog"
    source_root.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    post = source_root / "post.md"
    markdown = "![Outside](../outside.png)\n"

    result = collect_markdown_image_assets(
        markdown,
        source_file=post,
        source_root=source_root,
        vault=tmp_path / "vault",
    )

    assert result.content == markdown
    assert result.attachments == []
    assert result.warnings == ["blocked image outside source root: ../outside.png"]
```

- [ ] **Step 2: Run collector tests to verify they fail**

Run:

```bash
$env:PYTHONPATH='src'; pytest tests/test_markdown_assets.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kb.core.markdown_assets'`.

- [ ] **Step 3: Implement collector**

Create `src/kb/core/markdown_assets.py`:

```python
"""Collect local Markdown image assets into the vault attachment store."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import unquote

from kb.data.attachments import ATTACHMENTS_DIR, store_attachment


@dataclass(frozen=True)
class CollectedMarkdownAssets:
    """Result of rewriting Markdown image references."""

    content: str
    attachments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
_IGNORED_TARGET_PREFIXES = ("http://", "https://", "data:", "/")


def collect_markdown_image_assets(
    markdown: str,
    *,
    source_file: Path,
    source_root: Path,
    vault: Path,
) -> CollectedMarkdownAssets:
    """Store local Markdown images as vault attachments and rewrite links."""
    attachments: list[str] = []
    warnings: list[str] = []
    source_root_resolved = source_root.resolve()

    def replace(match: re.Match[str]) -> str:
        alt = match.group(1)
        raw_target = match.group(2)
        target, title = _split_target_and_title(raw_target)

        if not target:
            return match.group(0)

        normalized = target.replace("\\", "/")
        if normalized.startswith(f"{ATTACHMENTS_DIR}/"):
            _append_unique(attachments, normalized)
            return match.group(0)

        if _is_ignored_target(normalized):
            return match.group(0)

        image_path = _resolve_local_image(
            target,
            source_file=source_file,
            source_root=source_root_resolved,
        )
        if image_path is None:
            warnings.append(f"missing image: {target}")
            return match.group(0)
        if not image_path.resolve().is_relative_to(source_root_resolved):
            warnings.append(f"blocked image outside source root: {target}")
            return match.group(0)

        try:
            rel_path = store_attachment(image_path, vault)
        except Exception as exc:
            warnings.append(f"failed to store image {target}: {exc}")
            return match.group(0)

        _append_unique(attachments, rel_path)
        title_suffix = f" {title}" if title else ""
        return f"![{alt}]({rel_path}{title_suffix})"

    content = _IMAGE_RE.sub(replace, markdown)
    return CollectedMarkdownAssets(
        content=content,
        attachments=attachments,
        warnings=warnings,
    )


def _split_target_and_title(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    if raw.startswith("<"):
        end = raw.find(">")
        if end != -1:
            return raw[1:end], raw[end + 1:].strip()

    parts = raw.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip()


def _is_ignored_target(target: str) -> bool:
    lower = target.lower()
    return lower.startswith(_IGNORED_TARGET_PREFIXES)


def _resolve_local_image(
    target: str,
    *,
    source_file: Path,
    source_root: Path,
) -> Path | None:
    decoded = unquote(target)
    direct = (source_file.parent / decoded).resolve()
    if direct.is_file():
        return direct

    hexo_asset = (source_file.parent / source_file.stem / decoded).resolve()
    if hexo_asset.is_file():
        return hexo_asset

    if not direct.is_relative_to(source_root):
        return direct

    return None


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
```

- [ ] **Step 4: Run collector tests to verify they pass**

Run:

```bash
$env:PYTHONPATH='src'; pytest tests/test_markdown_assets.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit collector**

Run:

```bash
git add src/kb/core/markdown_assets.py tests/test_markdown_assets.py
git commit -m "feat: collect local markdown image assets"
```

## Task 2: Integrate Asset Collection into External Source Sync

**Files:**
- Modify: `src/kb/core/indexer.py`
- Modify: `tests/test_indexer.py`

- [ ] **Step 1: Write failing external sync tests**

Append to `tests/test_indexer.py`:

```python
def test_index_files_external_sources_collects_relative_images(
    db: Database,
    tmp_path: Path,
):
    """External source sync stores local images and persists note attachments."""
    vault = tmp_path / "vault"
    external = tmp_path / "blog"
    posts = external / "posts"
    posts.mkdir(parents=True)
    (posts / "diagram.png").write_bytes(b"diagram")
    (posts / "post.md").write_text(
        "---\n"
        "title: External Images\n"
        "categories: docs\n"
        "---\n\n"
        "Body\n\n"
        "![Diagram](./diagram.png)\n",
        encoding="utf-8",
    )

    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    indexed, _ = index_files(
        vault,
        db,
        full=True,
        external_sources=[external],
        source_project="blog",
    )

    assert indexed == 1
    dest = vault / "notes" / "docs" / "post.md"
    text = dest.read_text(encoding="utf-8")
    assert "source_project: blog" in text
    assert "attachments:" in text
    assert "attachments/" in text
    assert "![Diagram](attachments/" in text

    row = db.get_note("notes/docs/post.md")
    assert row is not None
    attachments = db.get_attachments("notes/docs/post.md")
    assert len(attachments) == 1
    assert attachments[0].startswith("attachments/")
    assert (vault / attachments[0]).read_bytes() == b"diagram"


def test_index_files_external_sources_collects_hexo_asset_folder(
    tmp_path: Path,
):
    """Bare image links resolve from the Hexo same-stem asset folder."""
    vault = tmp_path / "vault"
    external = tmp_path / "blog"
    posts = external / "source" / "_posts"
    asset_dir = posts / "hexo-post"
    asset_dir.mkdir(parents=True)
    (asset_dir / "cover.png").write_bytes(b"cover")
    (posts / "hexo-post.md").write_text(
        "---\n"
        "title: Hexo Post\n"
        "categories: blog\n"
        "---\n\n"
        "![Cover](cover.png)\n",
        encoding="utf-8",
    )
    db = Database(vault / ".kb" / "kb.db")
    db.initialize()

    index_files(vault, db, full=True, external_sources=[external])

    dest = vault / "notes" / "blog" / "hexo-post.md"
    text = dest.read_text(encoding="utf-8")
    assert "![Cover](attachments/" in text
    assert not (vault / "notes" / "blog" / "hexo-post").exists()
    assert db.get_attachments("notes/blog/hexo-post.md")[0].startswith("attachments/")
```

- [ ] **Step 2: Run external sync tests to verify they fail**

Run:

```bash
$env:PYTHONPATH='src'; pytest tests/test_indexer.py::test_index_files_external_sources_collects_relative_images tests/test_indexer.py::test_index_files_external_sources_collects_hexo_asset_folder -v
```

Expected: FAIL because external sync does not store images through `attachments/` or persist `attachments` frontmatter.

- [ ] **Step 3: Update indexer imports**

In `src/kb/core/indexer.py`, replace the top imports:

```python
import logging
import re
import shutil
from pathlib import Path
```

with:

```python
import logging
from pathlib import Path
from typing import Any

import yaml
```

Then add:

```python
from kb.core.markdown_assets import collect_markdown_image_assets
from kb.data.storage import (
    chunk_text,
    discover_notes,
    parse_markdown_file,
    _compute_hash as compute_file_hash,
    _split_frontmatter,
)
```

Remove `_RELATIVE_IMAGE_BARE`.

- [ ] **Step 4: Add frontmatter merge helper**

In `src/kb/core/indexer.py`, after `logger = logging.getLogger(__name__)`, add:

```python
def _merge_external_frontmatter(
    markdown: str,
    *,
    source_project: str | None,
    attachments: list[str],
) -> str:
    frontmatter, body = _split_frontmatter(markdown)
    data: dict[str, Any] = dict(frontmatter)

    if source_project and not data.get("source_project"):
        data["source_project"] = source_project

    existing = data.get("attachments") or []
    if isinstance(existing, str):
        existing = [existing]
    merged_attachments = list(existing)
    for path in attachments:
        if path not in merged_attachments:
            merged_attachments.append(path)
    if merged_attachments:
        data["attachments"] = merged_attachments

    if not data:
        return body

    raw = yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()
    return f"---\n{raw}\n---\n\n{body.lstrip()}"
```

- [ ] **Step 5: Replace external source image handling**

In `index_files()`, replace this block:

```python
                src_content = f.read_text(encoding="utf-8")
                # Inject source_project into frontmatter if missing
                if source_project and "source_project:" not in src_content:
                    first_delim = src_content.find("---", 0)
                    second_delim = src_content.find("---", first_delim + 3) if first_delim != -1 else -1
                    if second_delim != -1:
                        fm = src_content[first_delim+3:second_delim].rstrip()
                        src_content = src_content[:first_delim+3] + "\n" + fm + f"\nsource_project: {source_project}\n" + src_content[second_delim:]
                # Rewrite bare image references (no directory prefix) to use Hexo asset folder convention
                stem = f.stem
                src_content = _RELATIVE_IMAGE_BARE.sub(
                    lambda m, s=stem: f"{m.group(1)}{s}/{m.group(2)}", src_content
                )
                if not dest.exists() or dest.read_text(encoding="utf-8") != src_content:
                    dest.write_text(src_content, encoding="utf-8")
                # Copy associated asset directory (Hexo asset folder convention)
                asset_dir = f.parent / stem
                if asset_dir.is_dir():
                    dest_asset = category_dir / stem
                    if dest_asset.exists():
                        shutil.rmtree(dest_asset)
                    shutil.copytree(asset_dir, dest_asset)
```

with:

```python
                src_content = f.read_text(encoding="utf-8")
                collected = collect_markdown_image_assets(
                    src_content,
                    source_file=f,
                    source_root=src_dir,
                    vault=vault,
                )
                src_content = _merge_external_frontmatter(
                    collected.content,
                    source_project=source_project,
                    attachments=collected.attachments,
                )
                for warning in collected.warnings:
                    logger.warning("Image asset warning for %s: %s", f, warning)
                if not dest.exists() or dest.read_text(encoding="utf-8") != src_content:
                    dest.write_text(src_content, encoding="utf-8")
```

- [ ] **Step 6: Run focused indexer tests**

Run:

```bash
$env:PYTHONPATH='src'; pytest tests/test_markdown_assets.py tests/test_indexer.py::test_index_files_external_sources tests/test_indexer.py::test_index_files_external_sources_collects_relative_images tests/test_indexer.py::test_index_files_external_sources_collects_hexo_asset_folder -v
```

Expected: PASS.

- [ ] **Step 7: Commit sync integration**

Run:

```bash
git add src/kb/core/indexer.py tests/test_indexer.py
git commit -m "feat: collect images during external sync"
```

## Task 3: Correct API and Frontend Types for RAG Sources and Search Modes

**Files:**
- Modify: `src/kb/api/schemas.py`
- Modify: `web/src/api.ts`

- [ ] **Step 1: Update backend chat schema**

In `src/kb/api/schemas.py`, add after `AttachmentUploadResult`:

```python
class RAGSource(BaseModel):
    file_id: str
    title: str
    snippet: str
    source_project: str | None = None
    source_path: str | None = None
    content_type: str = "markdown"
    attachments: list[str] = Field(default_factory=list)
```

Then replace:

```python
class ChatAnswer(BaseModel):
    answer: str
    model: str
    tokens_used: int | None = None
    sources: list[NoteSummary] = Field(default_factory=list)
```

with:

```python
class ChatAnswer(BaseModel):
    answer: str
    model: str
    tokens_used: int | None = None
    sources: list[RAGSource] = Field(default_factory=list)
```

- [ ] **Step 2: Update frontend API types**

In `web/src/api.ts`, add after `SearchResult`:

```ts
export type SearchMode = 'fulltext' | 'semantic' | 'hybrid'

export interface RAGSource {
  file_id: string
  title: string
  snippet: string
  source_project: string | null
  source_path: string | null
  content_type: string
  attachments: string[]
}
```

Replace:

```ts
  search(q: string, limit?: number) {
    const qs = new URLSearchParams({ q, mode: 'fulltext' })
    if (limit) qs.set('limit', String(limit))
    return request<SearchResult[]>(`/search?${qs}`)
  },
```

with:

```ts
  search(q: string, mode: SearchMode = 'fulltext', limit?: number) {
    const qs = new URLSearchParams({ q, mode })
    if (limit) qs.set('limit', String(limit))
    return request<SearchResult[]>(`/search?${qs}`)
  },
```

Add before `chatAsk`:

```ts
  uploadAttachment(file: File) {
    const body = new FormData()
    body.append('file', file)
    return request<{ path: string }>('/attachments', {
      method: 'POST',
      body,
    })
  },
```

Replace the `chatAsk()` return type:

```ts
      sources: NoteSummary[]
```

with:

```ts
      sources: RAGSource[]
```

- [ ] **Step 3: Build frontend to verify type shape**

Run:

```bash
npm run build
```

from `web/`.

Expected: PASS.

- [ ] **Step 4: Commit API type updates**

Run:

```bash
git add src/kb/api/schemas.py web/src/api.ts
git commit -m "feat: expose rag source frontend types"
```

## Task 4: Render Chat Answer Sources

**Files:**
- Modify: `web/src/pages/ChatPage.vue`

- [ ] **Step 1: Update ChatMessage shape and API import**

In `web/src/pages/ChatPage.vue`, replace:

```ts
import { api, ApiError } from '../api'
```

with:

```ts
import { api, ApiError, type RAGSource } from '../api'
```

Replace:

```ts
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}
```

with:

```ts
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources?: RAGSource[]
}
```

- [ ] **Step 2: Store sources when asking**

Replace:

```ts
    messages.value.push({ id: ++nextId, role: 'assistant', content: res.answer })
```

with:

```ts
    messages.value.push({
      id: ++nextId,
      role: 'assistant',
      content: res.answer,
      sources: res.sources,
    })
```

- [ ] **Step 3: Render source cards**

In the assistant message bubble template, after:

```vue
            <div class="message-content">{{ msg.content }}</div>
```

add:

```vue
            <div v-if="msg.sources?.length" class="source-list">
              <router-link
                v-for="source in msg.sources"
                :key="source.file_id"
                :to="source.source_project ? `/source/${source.source_project}/${encodeURIComponent(source.file_id)}` : `/note/${encodeURIComponent(source.file_id)}`"
                class="source-card"
              >
                <div class="source-card-main">
                  <strong>{{ source.title }}</strong>
                  <p>{{ source.snippet }}</p>
                </div>
                <div class="source-card-meta">
                  <span>{{ source.content_type }}</span>
                  <span v-if="source.attachments.length">{{ source.attachments.length }} attachment{{ source.attachments.length > 1 ? 's' : '' }}</span>
                  <span v-if="source.source_path">{{ source.source_path }}</span>
                </div>
              </router-link>
            </div>
```

- [ ] **Step 4: Add ChatPage source styles**

In `web/src/pages/ChatPage.vue`, before `.command-bar`, add:

```css
.source-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.source-card {
  display: grid;
  gap: 6px;
  padding: 10px;
  border: 1px solid rgba(8, 145, 178, 0.16);
  border-radius: var(--radius-md);
  background: var(--color-surface-tinted);
}

.source-card:hover {
  border-color: var(--color-primary);
}

.source-card-main strong {
  display: block;
  color: var(--color-primary-hover);
  font-size: 0.84rem;
  line-height: 1.35;
}

.source-card-main p {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.source-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--color-text-muted);
  font-size: 0.72rem;
}
```

- [ ] **Step 5: Build frontend**

Run:

```bash
npm run build
```

from `web/`.

Expected: PASS.

- [ ] **Step 6: Commit chat source UI**

Run:

```bash
git add web/src/pages/ChatPage.vue
git commit -m "feat: show chat answer sources"
```

## Task 5: Show Note Source Metadata and Attachments

**Files:**
- Modify: `web/src/pages/NoteDetail.vue`

- [ ] **Step 1: Add note metadata refs**

In `web/src/pages/NoteDetail.vue`, after:

```ts
const tags = ref<string[]>([])
```

add:

```ts
const sourceProject = ref<string | null>(null)
const sourcePath = ref<string | null>(null)
const sourceContext = ref<string | null>(null)
const contentType = ref('markdown')
const attachments = ref<string[]>([])
```

- [ ] **Step 2: Populate metadata on load**

In `loadNote()`, after:

```ts
      noteUpdatedAt.value = note.updated_at || note.created_at || ''
```

add:

```ts
      sourceProject.value = note.source_project
      sourcePath.value = note.source_path
      sourceContext.value = note.source_context
      contentType.value = note.content_type
      attachments.value = note.attachments
```

- [ ] **Step 3: Render metadata panel in read mode**

In the read mode template, after the metadata row and before:

```vue
        <div v-html="renderedContent" class="prose prose-slate max-w-none"></div>
```

add:

```vue
        <section
          v-if="sourceProject || sourcePath || sourceContext || contentType !== 'markdown' || attachments.length"
          class="note-meta-panel"
        >
          <div v-if="sourceProject" class="note-meta-item">
            <span>Source</span>
            <strong>{{ sourceProject }}</strong>
          </div>
          <div v-if="contentType" class="note-meta-item">
            <span>Type</span>
            <strong>{{ contentType }}</strong>
          </div>
          <div v-if="sourcePath" class="note-meta-item note-meta-wide">
            <span>Source path</span>
            <strong>{{ sourcePath }}</strong>
          </div>
          <div v-if="sourceContext" class="note-meta-item note-meta-wide">
            <span>Context</span>
            <strong>{{ sourceContext }}</strong>
          </div>
          <div v-if="attachments.length" class="note-meta-item note-meta-wide">
            <span>Attachments</span>
            <div class="attachment-list">
              <a
                v-for="path in attachments"
                :key="path"
                :href="`/vault/${path}`"
                target="_blank"
                rel="noreferrer"
              >{{ path }}</a>
            </div>
          </div>
        </section>
```

- [ ] **Step 4: Add NoteDetail styles**

At the end of `web/src/pages/NoteDetail.vue`, add:

```vue
<style scoped>
.note-meta-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: -12px 0 24px;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.note-meta-item {
  min-width: 0;
}

.note-meta-wide {
  grid-column: 1 / -1;
}

.note-meta-item span {
  display: block;
  color: var(--color-text-muted);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.note-meta-item strong {
  display: block;
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 0.84rem;
  overflow-wrap: anywhere;
}

.attachment-list {
  display: grid;
  gap: 4px;
  margin-top: 4px;
}

.attachment-list a {
  color: var(--color-primary-hover);
  font-size: 0.84rem;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .note-meta-panel {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
```

- [ ] **Step 5: Build frontend**

Run:

```bash
npm run build
```

from `web/`.

Expected: PASS.

- [ ] **Step 6: Commit note metadata UI**

Run:

```bash
git add web/src/pages/NoteDetail.vue
git commit -m "feat: show note source metadata"
```

## Task 6: Add Search Mode Selector

**Files:**
- Modify: `web/src/pages/SearchPage.vue`

- [ ] **Step 1: Import search mode type**

In `web/src/pages/SearchPage.vue`, replace:

```ts
import { api, type SearchResult } from '../api'
```

with:

```ts
import { api, type SearchMode, type SearchResult } from '../api'
```

Add after `const query = ref('')`:

```ts
const mode = ref<SearchMode>('fulltext')
```

- [ ] **Step 2: Pass mode to API**

Replace:

```ts
    results.value = await api.search(q)
```

with:

```ts
    results.value = await api.search(q, mode.value)
```

- [ ] **Step 3: Add mode controls**

In the command card template, after the input and before the button, add:

```vue
      <div class="mode-toggle" aria-label="Search mode">
        <button
          v-for="item in searchModes"
          :key="item.value"
          type="button"
          :class="['mode-button', mode === item.value ? 'mode-button-active' : '']"
          @click="mode = item.value"
        >{{ item.label }}</button>
      </div>
```

Add to the script:

```ts
const searchModes: Array<{ value: SearchMode; label: string }> = [
  { value: 'fulltext', label: 'Fulltext' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'semantic', label: 'Semantic' },
]
```

- [ ] **Step 4: Show active mode in results header**

Replace:

```vue
          {{ results.length }} result{{ results.length !== 1 ? 's' : '' }} for "{{ lastQuery }}"
```

with:

```vue
          {{ results.length }} result{{ results.length !== 1 ? 's' : '' }} for "{{ lastQuery }}" via {{ mode }}
```

- [ ] **Step 5: Add search mode styles**

In `web/src/pages/SearchPage.vue`, add after `.command-input`:

```css
.mode-toggle {
  display: inline-flex;
  min-height: 36px;
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-solid);
}

.mode-button {
  min-width: 72px;
  padding: 5px 9px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 750;
}

.mode-button-active {
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
}
```

In the mobile media query, replace:

```css
  .command-card {
    grid-template-columns: auto minmax(0, 1fr);
  }
```

with:

```css
  .command-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .mode-toggle {
    grid-column: 1 / -1;
    width: 100%;
  }

  .mode-button {
    flex: 1;
  }
```

- [ ] **Step 6: Build frontend**

Run:

```bash
npm run build
```

from `web/`.

Expected: PASS.

- [ ] **Step 7: Commit search mode UI**

Run:

```bash
git add web/src/pages/SearchPage.vue
git commit -m "feat: add search mode selector"
```

## Task 7: Add Editor Attachment Upload Helper

**Files:**
- Modify: `web/src/components/MarkdownEditor.vue`

- [ ] **Step 1: Import API helper and add upload ref**

In `web/src/components/MarkdownEditor.vue`, add:

```ts
import { api } from '../api'
```

after the existing imports.

Replace:

```ts
const preview = ref(true)
```

with:

```ts
const preview = ref(true)
const uploading = ref(false)
```

Replace:

```ts
defineEmits<{
  'update:modelValue': [value: string]
}>()
```

with:

```ts
const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
```

- [ ] **Step 2: Add file input and upload button**

In the editor toolbar, after the preview button, add:

```vue
        <label class="text-xs text-blue-600 hover:underline cursor-pointer">
          {{ uploading ? 'Uploading...' : 'Upload Asset' }}
          <input
            type="file"
            class="hidden"
            :disabled="uploading"
            @change="uploadAsset"
          />
        </label>
```

- [ ] **Step 3: Implement upload insertion**

In the script, before `const marked = new Marked(`, add:

```ts
async function uploadAsset(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || uploading.value) return

  uploading.value = true
  try {
    const result = await api.uploadAttachment(file)
    const isImage = file.type.startsWith('image/')
    const markdown = isImage
      ? `![${file.name}](${result.path})`
      : `[${file.name}](${result.path})`
    const nextValue = props.modelValue
      ? `${props.modelValue.replace(/\s*$/, '')}\n\n${markdown}\n`
      : `${markdown}\n`
    emit('update:modelValue', nextValue)
  } finally {
    uploading.value = false
    input.value = ''
  }
}
```

- [ ] **Step 4: Build frontend**

Run:

```bash
npm run build
```

from `web/`.

Expected: PASS.

- [ ] **Step 5: Commit editor upload helper**

Run:

```bash
git add web/src/components/MarkdownEditor.vue
git commit -m "feat: add editor attachment upload"
```

## Task 8: Final Verification

**Files:**
- No code changes unless verification finds a defect.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
$env:PYTHONPATH='src'; pytest tests/test_markdown_assets.py tests/test_indexer.py tests/test_api_v1.py tests/test_rag.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full backend suite**

Run:

```bash
$env:PYTHONPATH='src'; pytest -v
```

Expected: PASS.

- [ ] **Step 3: Build frontend**

Run:

```bash
npm run build
```

from `web/`.

Expected: PASS.

- [ ] **Step 4: Run rendered UI smoke check**

Start the backend or frontend preview according to the current repo workflow:

```bash
python -m kb.cli serve
```

or, for frontend-only validation:

```bash
npm run dev
```

from `web/`.

Use Playwright if the Browser plugin is unavailable. Verify these flows:

- Chat page loads and can render a mocked or real answer with sources.
- Note detail page shows metadata and attachment links when note data contains them.
- Search page mode buttons switch selected mode without layout overlap.
- Editor upload button inserts Markdown after `/api/v1/attachments` returns a path.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only known unrelated untracked local files remain.

## Completion Criteria

This feature is complete when:

- Local relative Markdown images are collected into `attachments/`.
- Hexo same-stem asset folder images are collected into `attachments/`.
- External source synced Markdown is rewritten to stable attachment paths.
- Synced notes persist attachment metadata in frontmatter and SQLite.
- Chat UI displays RAG source cards.
- Note detail displays source metadata and attachment links.
- Search UI can request fulltext, hybrid, and semantic modes.
- Editor can upload an attachment and insert Markdown.
- Backend tests pass.
- Frontend build passes.
