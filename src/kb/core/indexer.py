"""Index orchestration: file discovery, sync, chunking, embedding, vector upsert."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.local_repository import LocalMarkdownRepository
from kb.data.repository import NoteRepository
from kb.data.storage import chunk_text
from kb.data.vector import VectorRecord, VectorStore

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from kb.core.context import AppContext


def index_files(
    repo: NoteRepository,
    db: Database,
    *,
    full: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    external_sources: list[Path] | None = None,
    source_project: str | None = None,
    index_dir: str = ".kb",
    vault: Path | None = None,
) -> tuple[int, int]:
    """Index notes via repo. Returns (fts5_count, vector_count).

    Dedup happens inside repo.discover(). External-source sync is delegated
    to the repository (only LocalMarkdownRepository implements it). Vector
    indexing is skipped unless both embedding_provider and vault are given,
    since vectors need the vault-relative .kb path.
    """
    if external_sources and isinstance(repo, LocalMarkdownRepository):
        repo.sync_external_sources(external_sources, source_project)

    all_hashes = db.get_all_hashes()
    existing = {} if full else all_hashes
    file_ids = repo.discover()  # discover() already dedupes internally
    file_id_set = set(file_ids)

    changed_ids: set[str] = set()
    indexed = 0
    for fid in file_ids:
        try:
            note = repo.read(fid)
        except Exception:
            logger.warning("Failed to parse %s, skipping", fid, exc_info=True)
            continue
        if not full and existing.get(fid) == note.file_hash:
            continue
        db.upsert_note(note)
        indexed += 1
        changed_ids.add(fid)

    for fid in all_hashes:
        if fid not in file_id_set:
            db.delete_note(fid)
            changed_ids.add(fid)

    vector_count = 0
    if embedding_provider is not None and vault is not None:
        vector_count = index_vectors(
            vault,
            db,
            embedding_provider,
            changed_ids,
            index_dir=index_dir,
        )
    return indexed, vector_count


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
        chunks = chunk_text(content, file_id=file_id)
        if not chunks:
            store.delete_note(file_id)
            return 0

        texts = [c.text for c in chunks]
        embed_results = provider.embed_batch(texts)
        records = [
            VectorRecord(
                id=file_id,
                chunk_id=i,
                vector=result.vector,
                text=chunks[i].text,
                section_path=chunks[i].section_path,
                content_type=chunks[i].content_type,
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


def index_note_if_possible(
    ctx: AppContext,
    file_id: str,
) -> tuple[int, str | None]:
    """Index note vectors if embedding is available. Safe to call always.

    Returns (vector_count, error_message). error_message is None on success.
    """
    try:
        provider = ctx.ensure_embedding()
        if provider is None:
            return 0, "embedding provider is not configured"
        count = index_note_vectors(
            ctx.vault,
            ctx.db,
            provider,
            file_id,
            vector_store=ctx.vector_store,
            index_dir=ctx.index_dir,
        )
        return count, None
    except Exception as exc:
        return 0, str(exc)
