"""Read-model orchestration for API-facing data."""
from __future__ import annotations

from dataclasses import dataclass

from kb.core import services
from kb.core.context import AppContext
from kb.core.search import cosine_similarity, hybrid_search
from kb.core.serializers import count_item, note_row_to_summary, note_to_detail


@dataclass
class PageResult:
    items: list[dict]
    total: int
    limit: int
    offset: int


def list_notes(
    ctx: AppContext,
    *,
    category: str | None,
    tag: str | None,
    limit: int,
    offset: int,
) -> PageResult:
    """List note summaries with pagination metadata."""
    rows = ctx.db.list_notes(category=category, tag=tag, limit=limit, offset=offset)
    total = ctx.db.count_notes(category=category, tag=tag)
    return PageResult(
        items=[note_row_to_summary(ctx.db, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_note_detail(ctx: AppContext, file_id: str) -> dict:
    """Read a note from storage and return the detailed API shape."""
    _, note = services.resolve_note(ctx.vault, file_id)
    return note_to_detail(note)


def get_type_distribution(ctx: AppContext) -> list[dict]:
    """Return configured entry type distribution for published notes."""
    labels = {}
    if ctx.config and ctx.config.kb_types:
        labels = {name: item.label for name, item in ctx.config.kb_types.items()}
    return [
        count_item(
            row["entry_type"],
            row["count"],
            labels.get(row["entry_type"], row["entry_type"]),
        )
        for row in ctx.db.count_notes_by_entry_type()
    ]


def get_source_projects(ctx: AppContext) -> list[dict]:
    """Return source project distribution for published notes."""
    return [
        count_item(row["source_project"], row["count"])
        for row in ctx.db.list_source_projects()
    ]


def get_content_types(ctx: AppContext) -> list[dict]:
    """Return content type distribution for published notes."""
    return [
        count_item(row["content_type"], row["count"])
        for row in ctx.db.count_notes_by_content_type()
    ]


def get_index_health(ctx: AppContext) -> dict:
    """Return note/vector index health summary."""
    notes_count = len(ctx.db.get_all_hashes())
    vectors_count = 0
    if ctx.vector_store is not None:
        try:
            vectors_count = ctx.vector_store.count()
        except Exception:
            vectors_count = 0
    coverage = 1.0 if notes_count > 0 and vectors_count > 0 else 0.0
    return {
        "notes_count": notes_count,
        "vectors_count": vectors_count,
        "coverage": coverage,
    }


def get_attachments_count(ctx: AppContext) -> int:
    """Count files under the vault attachments directory."""
    attachments_dir = ctx.vault / "attachments"
    if not attachments_dir.is_dir():
        return 0
    return sum(1 for item in attachments_dir.rglob("*") if item.is_file())


def get_dashboard_stats(ctx: AppContext) -> dict:
    """Return the unified dashboard read model."""
    index_health = get_index_health(ctx)
    return {
        "notes_count": index_health["notes_count"],
        "attachments_count": get_attachments_count(ctx),
        "type_distribution": get_type_distribution(ctx),
        "source_projects": get_source_projects(ctx),
        "content_types": get_content_types(ctx),
        "index_health": index_health,
    }


def get_dashboard_activity(ctx: AppContext, limit: int) -> list[dict]:
    """Return lightweight activity items derived from recent notes."""
    rows = ctx.db.list_notes(limit=limit, offset=0)
    items: list[dict] = []
    for row in rows:
        note = note_row_to_summary(ctx.db, row)
        timestamp = note.get("updated_at") or note.get("created_at")
        description_parts = []
        if note.get("source_project"):
            description_parts.append(f"Source: {note['source_project']}")
        if note.get("category"):
            description_parts.append(f"Category: {note['category']}")
        if note.get("entry_type"):
            description_parts.append(f"Type: {note['entry_type']}")
        description = " / ".join(description_parts) or "Knowledge note updated"
        items.append({
            "kind": "note_updated",
            "title": note["title"],
            "description": description,
            "timestamp": timestamp,
            "note": {
                "file_id": note["file_id"],
                "title": note["title"],
            },
        })
    return items


def get_taxonomy(ctx: AppContext) -> dict:
    """Return tags and grouped taxonomy counts."""
    categories = [
        count_item(category, ctx.db.count_notes_by_category(category))
        for category in ctx.db.list_all_categories()
    ]
    return {
        "tags": ctx.db.list_all_tags(),
        "categories": categories,
        "entry_types": get_type_distribution(ctx),
        "source_projects": get_source_projects(ctx),
        "content_types": get_content_types(ctx),
    }


def search_notes(
    ctx: AppContext,
    *,
    query: str,
    mode: str,
    limit: int,
    offset: int,
) -> PageResult:
    """Search notes and normalize every mode to SearchResult-like dicts."""
    if mode == "hybrid" and ctx.embedding is not None:
        results = hybrid_search(query, ctx.db, ctx.embedding, ctx.vector_store, limit + offset)
        sliced = results[offset:offset + limit]
        items = []
        for result in sliced:
            row = ctx.db.get_note(result.file_id)
            if row is None:
                continue
            items.append({
                "note": note_row_to_summary(ctx.db, row),
                "score": result.score,
                "source": result.source,
                "chunk_text": None,
            })
        return PageResult(items=items, total=len(results), limit=limit, offset=offset)

    if mode == "semantic" and ctx.embedding is not None:
        embed_result = ctx.embedding.embed(query)
        records = ctx.vector_store.search(embed_result.vector, limit=limit + offset)
        sliced = records[offset:offset + limit]
        items = []
        for record in sliced:
            row = ctx.db.get_note(record.id)
            if row is None:
                continue
            items.append({
                "note": note_row_to_summary(ctx.db, row),
                "score": cosine_similarity(record.vector, embed_result.vector),
                "source": "semantic",
                "chunk_text": record.text,
            })
        return PageResult(items=items, total=len(records), limit=limit, offset=offset)

    rows = ctx.db.search_fulltext(query, limit=limit + offset)
    sliced = rows[offset:offset + limit]
    return PageResult(
        items=[
            {
                "note": note_row_to_summary(ctx.db, row),
                "score": None,
                "source": "fulltext",
                "chunk_text": None,
            }
            for row in sliced
        ],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


def get_related_notes(ctx: AppContext, file_id: str, limit: int) -> list[dict]:
    """Return semantically related note search results."""
    if ctx.embedding is None:
        return []

    _, note = services.resolve_note(ctx.vault, file_id)
    embed_result = ctx.embedding.embed(note.content)
    records = ctx.vector_store.search(embed_result.vector, limit=limit * 3 + 1)

    results = []
    seen_ids: set[str] = {file_id}
    for record in records:
        if record.id in seen_ids:
            continue
        seen_ids.add(record.id)
        row = ctx.db.get_note(record.id)
        if row is None:
            continue
        results.append({
            "note": note_row_to_summary(ctx.db, row),
            "score": round(cosine_similarity(record.vector, embed_result.vector), 4),
            "source": "semantic",
            "chunk_text": record.text,
        })
        if len(results) >= limit:
            break
    return results
