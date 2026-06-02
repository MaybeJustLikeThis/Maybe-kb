# Local Markdown Image Asset Ingest Design

## Goal

When a Markdown article is synced or imported from a local source, `kb` should collect its local image assets into the vault attachment store, rewrite Markdown image links to stable vault paths, persist the attachment list on the note, and make those attachments visible from search, chat sources, and note detail views.

This is the next step after the Phase 1 ingest/indexing foundation. It keeps the project centered on personal knowledge base management: notes should remain readable Markdown, original/local images should not become dangling references, and RAG answers should point back to traceable notes and supporting assets.

## Scope

This phase handles local image references only:

- Relative Markdown images such as `![](./img/a.png)` and `![alt](../assets/a.jpg)`.
- Hexo-style post asset folders such as `my-post.md` referencing `my-post/a.png` or bare `a.png` when `my-post/a.png` exists.
- Existing vault-relative attachment links such as `attachments/2026/06/x.png` are preserved and recorded.

This phase does not handle:

- Remote image download from `http://` or `https://`.
- Data URI images.
- Absolute filesystem paths outside the source directory.
- HTML `<img>` parsing.
- OCR, image captioning, or visual understanding.

Image understanding is a later extension point. The pipeline should keep enough metadata to add OCR/caption results later, but no OCR or caption model should run in this phase.

## Architecture

Add a focused Markdown asset module that is independent from parsing, indexing, and UI:

```text
Markdown content + source markdown path
-> collect local image references
-> store files via AttachmentStore
-> rewrite Markdown links
-> return rewritten content + attachment paths + warnings
-> ingest/index as normal
```

The module should live near data/core boundaries, for example `kb.core.markdown_assets` or `kb.data.markdown_assets`. It should expose one high-level function:

```python
collect_markdown_image_assets(
    markdown: str,
    source_file: Path,
    vault: Path,
) -> CollectedMarkdownAssets
```

Suggested result shape:

```python
@dataclass(frozen=True)
class CollectedMarkdownAssets:
    content: str
    attachments: list[str]
    warnings: list[str]
```

The function should:

- Parse Markdown image syntax `![alt](target "optional title")`.
- Ignore remote URLs, absolute URLs, root-relative URLs, and data URIs.
- Resolve local targets relative to `source_file.parent`.
- If a bare filename cannot be found beside the Markdown file, try `source_file.with_suffix("").name / target` for Hexo assets.
- Reject paths that resolve outside the local source root implied by the article location.
- Store found files through the existing `store_attachment()` deduplication logic.
- Rewrite the image target to the returned attachment path.
- Preserve alt text and optional title.
- Return warnings for missing or blocked local files.

## Sync Integration

The first integration point is external-source sync in `index_files()`.

When copying a Markdown file from an external source into the vault:

1. Parse enough frontmatter to preserve existing metadata.
2. Run local image collection against the source Markdown file before writing the copied note.
3. Merge collected attachment paths into frontmatter `attachments`.
4. Write the rewritten Markdown into the vault.
5. Continue normal indexing.

This keeps existing `ingest()` behavior intact and avoids duplicating note creation logic. Later import APIs can call the same asset collector before `ingest()`.

## Frontend Adaptation

The UI should surface the metadata that Phase 1 and this phase make available.

### Chat Sources

`/api/v1/chat/ask` already returns traceable sources. The frontend should:

- Define a `RAGSource` type matching backend output.
- Store sources on assistant chat messages.
- Render source cards under the answer with title, snippet, content type, source path, and attachment count.
- Link source cards to note detail using `file_id`.

### Note Detail

`NoteDetail.vue` should show a compact metadata panel in read mode:

- `source_project`
- `source_path`
- `content_type`
- `attachments`

Attachment rows should link to `/vault/<attachment-path>` so stored images/files can be opened directly.

### Search

`SearchPage.vue` should let users choose search mode:

- Fulltext
- Hybrid
- Semantic

The API client should pass the selected mode to `/api/v1/search`. If semantic providers are unavailable, the existing backend fallback/error behavior should be displayed gracefully.

### Editor

The editor can provide a manual attachment upload helper as a companion feature:

- Choose or drop an image/file.
- Upload via `/api/v1/attachments`.
- Insert Markdown image or link text into the editor.

This helper is useful for manual notes, but it is not the primary mechanism for synced article image collection.

## Data Model

Collected images should be persisted as normal note attachments:

```yaml
attachments:
  - attachments/2026/06/hash.png
```

The note content should reference the stored attachment path:

```markdown
![diagram](attachments/2026/06/hash.png)
```

Existing note fields remain unchanged:

- `source_project`
- `source_path`
- `source_context`
- `content_type`
- `extra_frontmatter`

No OCR/caption fields are required yet. Future image understanding can add parser metadata such as:

```yaml
image_analysis:
  status: pending
  caption: null
  ocr_text: null
```

That metadata is explicitly out of scope for this phase.

## Error Handling

Local image collection should be best-effort:

- Missing image: leave the original Markdown link unchanged and add a warning.
- Path traversal/outside source root: leave unchanged and add a warning.
- Attachment store failure: leave unchanged and add a warning.
- Duplicate image: rely on `store_attachment()` hash deduplication.

Sync should not fail only because one image is missing. The article is still valuable text, and the warning can be surfaced later in import status UI.

## Testing Strategy

Backend tests should cover:

- Relative image is stored and Markdown link rewritten.
- Hexo asset folder image is resolved and rewritten.
- Existing `attachments/...` links are preserved and included in returned attachments.
- Remote/data/root-relative links are ignored.
- Missing local image leaves content unchanged and returns a warning.
- External source sync writes rewritten Markdown and persists DB attachments.

Frontend tests/build should cover:

- API type shape for chat sources.
- Chat page can render answer sources.
- Note detail can render source metadata and attachments.
- Search mode selection sends `fulltext`, `hybrid`, or `semantic`.
- Editor upload inserts a Markdown image/link after `/attachments` succeeds.

## Rollout

Implement in this order:

1. Backend asset collector and tests.
2. External-source sync integration and tests.
3. API/frontend type updates.
4. Chat sources UI.
5. Note detail metadata/attachments UI.
6. Search mode control.
7. Editor upload helper.
8. Backend and frontend verification.
