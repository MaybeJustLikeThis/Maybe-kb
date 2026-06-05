"""Index orchestration: file discovery, sync, chunking, embedding, vector upsert."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from kb.core.markdown_assets import collect_markdown_image_assets
from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.storage import (
    _compute_hash as compute_file_hash,
    chunk_text,
    discover_notes,
    parse_markdown_file,
)
from kb.data.vector import VectorRecord, VectorStore

logger = logging.getLogger(__name__)
UNCATEGORIZED_CATEGORY = "未分类"

_FRONTMATTER_BOUNDARY_RE = re.compile(
    r"^---[ \t]*\r?\n(?P<raw>.*?)\r?\n---[ \t]*(?:\r?\n|$)",
    re.DOTALL,
)


def _merge_external_frontmatter(
    markdown: str,
    *,
    source_project: str | None,
    attachments: list[str],
) -> str:
    frontmatter, body = _split_frontmatter_preserving_body(markdown)
    data: dict[str, Any] = dict(frontmatter)
    changed = False

    if source_project and not data.get("source_project"):
        data["source_project"] = source_project
        changed = True

    existing_value = data.get("attachments") or []
    if isinstance(existing_value, str):
        existing_attachments = [existing_value]
    else:
        existing_attachments = list(existing_value)
    merged_attachments = []
    for path in [*existing_attachments, *attachments]:
        if path not in merged_attachments:
            merged_attachments.append(path)
    if merged_attachments != existing_attachments:
        changed = True
    if merged_attachments:
        data["attachments"] = merged_attachments

    if not changed:
        return markdown

    raw = yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()
    return f"---\n{raw}\n---\n{body}"


def _split_frontmatter_preserving_body(markdown: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_BOUNDARY_RE.match(markdown)
    if match is None:
        return {}, markdown

    try:
        parsed = yaml.safe_load(match.group("raw")) or {}
    except yaml.YAMLError:
        parsed = {}

    data = parsed if isinstance(parsed, dict) else {}

    return data, markdown[match.end():]


def index_files(
    vault: Path,
    db: Database,
    *,
    full: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    external_sources: list[Path] | None = None,
    source_project: str | None = None,
    notes_dir: str = "notes",
    attachments_dir: str = "attachments",
    index_dir: str = ".kb",
) -> tuple[int, int]:
    """Index notes into database. Returns (fts5_count, vector_count).

    If external_sources is provided, .md files from those directories are
    synced into the configured notes directory before indexing.
    source_project is injected into synced files that lack it.
    """
    if external_sources:
        vault_root = vault.resolve()
        notes_root = vault / notes_dir
        resolved_notes_root = notes_root.resolve()
        if not resolved_notes_root.is_relative_to(vault_root):
            raise ValueError(f"Configured notes directory escapes the vault: {notes_dir}")
        notes_root.mkdir(parents=True, exist_ok=True)
        for src_dir in external_sources:
            if not src_dir.is_dir():
                continue
            for f in sorted(src_dir.rglob("*.md")):
                try:
                    note = parse_markdown_file(f, src_dir)
                    cat = note.category if note.category else UNCATEGORIZED_CATEGORY
                except Exception:
                    cat = UNCATEGORIZED_CATEGORY
                cat = cat.replace("/", "-").replace("\\", "-")
                if cat in {".", ".."}:
                    cat = UNCATEGORIZED_CATEGORY
                category_dir = notes_root / cat
                resolved_category_dir = category_dir.resolve()
                if not _is_within_roots(
                    resolved_category_dir,
                    resolved_notes_root,
                    vault_root,
                ):
                    raise ValueError(f"External source category escapes notes root: {cat}")
                category_dir.mkdir(exist_ok=True)
                dest = category_dir / f.name
                resolved_dest = dest.resolve()
                if not _is_within_roots(
                    resolved_dest,
                    resolved_notes_root,
                    vault_root,
                ):
                    raise ValueError(f"External source destination escapes notes root: {dest}")
                # Remove stale copies of this file that ended up in a different category
                for existing in notes_root.rglob(f.name):
                    resolved_existing = existing.resolve()
                    if not _is_within_roots(
                        resolved_existing,
                        resolved_notes_root,
                        vault_root,
                    ):
                        continue
                    if resolved_existing != resolved_dest:
                        existing.unlink()
                src_content = f.read_text(encoding="utf-8")
                collected = collect_markdown_image_assets(
                    src_content,
                    source_file=f,
                    source_root=src_dir,
                    vault=vault,
                    attachments_dir=attachments_dir,
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

    all_hashes = db.get_all_hashes()
    existing = {} if full else all_hashes
    files = discover_notes(vault, notes_dir=notes_dir)

    # Dedup: remove files with identical content but different paths
    seen_hashes: dict[str, Path] = {}
    for f in files:
        try:
            f_hash = compute_file_hash(f)
        except Exception:
            continue
        if f_hash in seen_hashes:
            f.unlink()
            logger.info("Removed duplicate: %s (same content as %s)", f, seen_hashes[f_hash])
        else:
            seen_hashes[f_hash] = f
    files = [f for f in files if f.exists()]

    changed_ids: set[str] = set()
    indexed = 0

    for f in files:
        try:
            note = parse_markdown_file(f, vault)
        except Exception:
            logger.warning("Failed to parse %s, skipping", f, exc_info=True)
            continue

        fid = note.file_id
        if not full and existing.get(fid) == note.file_hash:
            continue

        db.upsert_note(note)
        indexed += 1
        changed_ids.add(fid)

    current_ids = {f.relative_to(vault).as_posix() for f in files}
    for file_id in all_hashes:
        if file_id not in current_ids:
            db.delete_note(file_id)
            changed_ids.add(file_id)

    vector_count = 0
    if embedding_provider is not None:
        vector_count = index_vectors(
            vault,
            db,
            embedding_provider,
            changed_ids,
            index_dir=index_dir,
        )

    return indexed, vector_count


def _is_within_roots(path: Path, *roots: Path) -> bool:
    return all(path.is_relative_to(root) for root in roots)


def index_note_vectors(
    vault: Path,
    db: Database,
    provider: EmbeddingProvider,
    file_id: str,
    *,
    vector_store: VectorStore | None = None,
    index_dir: str = ".kb",
) -> int:
    """Generate embeddings for one note and upsert LanceDB chunks.

    If the note no longer exists or has empty content, stale vector chunks
    are deleted and 0 is returned.
    """
    owns_store = vector_store is None
    store = vector_store or VectorStore(vault / index_dir / "vectors.lance")

    try:
        row = db.get_note(file_id)
        if row is None:
            store.delete_note(file_id)
            return 0

        content = row["content"] or ""
        chunks = chunk_text(content)
        if not chunks:
            store.delete_note(file_id)
            return 0

        embed_results = provider.embed_batch(chunks)
        records = [
            VectorRecord(
                id=file_id,
                chunk_id=i,
                vector=result.vector,
                text=chunks[i],
            )
            for i, result in enumerate(embed_results)
        ]
        store.upsert_chunks(file_id, records)
        return len(records)
    finally:
        if owns_store:
            store.close()


def index_vectors(
    vault: Path,
    db: Database,
    provider: EmbeddingProvider,
    changed_ids: set[str],
    *,
    index_dir: str = ".kb",
) -> int:
    """Generate embeddings for changed notes and update LanceDB.

    Only processes notes whose file_hash changed.
    Returns number of vector records indexed.
    """
    store = VectorStore(vault / index_dir / "vectors.lance")
    indexed = 0

    try:
        for file_id in changed_ids:
            indexed += index_note_vectors(
                vault,
                db,
                provider,
                file_id,
                vector_store=store,
            )
    finally:
        store.close()

    return indexed
