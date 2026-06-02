"""Index orchestration: file discovery, sync, chunking, embedding, vector upsert."""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.storage import chunk_text, discover_notes, parse_markdown_file, _compute_hash as compute_file_hash
from kb.data.vector import VectorRecord, VectorStore

_RELATIVE_IMAGE_BARE = re.compile(r'(!\[[^\]]*\]\()(?!https?://|/|data:)([^/)]+\))')

logger = logging.getLogger(__name__)


def index_files(
    vault: Path,
    db: Database,
    *,
    full: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    external_sources: list[Path] | None = None,
    source_project: str | None = None,
) -> tuple[int, int]:
    """Index notes into database. Returns (fts5_count, vector_count).

    If external_sources is provided, .md files from those directories are
    synced into vault/notes/ before indexing (new files only, no overwrite).
    source_project is injected into synced files that lack it.
    """
    if external_sources:
        notes_dir = vault / "notes"
        notes_dir.mkdir(exist_ok=True)
        for src_dir in external_sources:
            if not src_dir.is_dir():
                continue
            for f in sorted(src_dir.rglob("*.md")):
                try:
                    note = parse_markdown_file(f, src_dir)
                    cat = note.category if note.category else "未分类"
                except Exception:
                    cat = "未分类"
                cat = cat.replace("/", "-").replace("\\", "-")
                category_dir = notes_dir / cat
                category_dir.mkdir(exist_ok=True)
                dest = category_dir / f.name
                # Remove stale copies of this file that ended up in a different category
                for existing in notes_dir.rglob(f.name):
                    if existing.resolve() != dest.resolve():
                        existing.unlink()
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

    all_hashes = db.get_all_hashes()
    existing = {} if full else all_hashes
    files = discover_notes(vault)

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
        vector_count = index_vectors(vault, db, embedding_provider, changed_ids)

    return indexed, vector_count


def index_note_vectors(
    vault: Path,
    db: Database,
    provider: EmbeddingProvider,
    file_id: str,
    *,
    vector_store: VectorStore | None = None,
) -> int:
    """Generate embeddings for one note and upsert LanceDB chunks.

    If the note no longer exists or has empty content, stale vector chunks
    are deleted and 0 is returned.
    """
    owns_store = vector_store is None
    store = vector_store or VectorStore(vault / ".kb" / "vectors.lance")

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
) -> int:
    """Generate embeddings for changed notes and update LanceDB.

    Only processes notes whose file_hash changed.
    Returns number of vector records indexed.
    """
    store = VectorStore(vault / ".kb" / "vectors.lance")
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
