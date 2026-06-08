"""Hybrid search with Reciprocal Rank Fusion (FTS5 + semantic), chunk-level."""
from __future__ import annotations

from dataclasses import dataclass, field

from kb.data.database import Database
from kb.data.embedding import EmbeddingProvider
from kb.data.vector import VectorStore


@dataclass(frozen=True)
class ChunkSearchResult:
    """A single chunk result from search."""
    file_id: str
    chunk_id: int
    text: str
    section_path: list[str] = field(default_factory=list)
    score: float = 0.0
    source: str = "hybrid"  # "fts5" | "semantic" | "hybrid"
    title: str = ""


@dataclass(frozen=True)
class SearchResult:
    """Legacy note-level search result (used by eval module)."""
    file_id: str
    title: str
    score: float = 0.0
    source: str = "hybrid"


def hybrid_search(
    query: str,
    db: Database,
    provider: EmbeddingProvider,
    store: VectorStore,
    limit: int = 20,
    rrf_k: int = 60,
) -> list[ChunkSearchResult]:
    """FTS5 + semantic search with Reciprocal Rank Fusion at chunk level.

    1. FTS5 returns note IDs -> look up all chunks for those notes
    2. Semantic search returns chunk-level results directly
    3. RRF fuses at chunk level using composite key (file_id, chunk_id)
    4. Score-based re-rank with cosine similarity
    """
    fts5_rows = db.search_fulltext(query, limit=limit * 2)
    embed_result = provider.embed(query)
    semantic_records = store.search(embed_result.vector, limit=limit * 2)

    # Build FTS5 chunk results: note ID -> all chunks
    fts5_chunks: list[ChunkSearchResult] = []
    for row in fts5_rows:
        fid = row["id"]
        title = row["title"]
        note_chunks = store.get_chunks_by_file_id(fid)
        if note_chunks:
            for rec in note_chunks:
                fts5_chunks.append(ChunkSearchResult(
                    file_id=fid,
                    chunk_id=rec.chunk_id,
                    text=rec.text,
                    section_path=rec.section_path,
                    title=title,
                    source="fts5",
                ))
        else:
            # Fallback: note has no chunks, create a synthetic result
            content = row["content"] or ""
            fts5_chunks.append(ChunkSearchResult(
                file_id=fid,
                chunk_id=0,
                text=content[:500],
                title=title,
                source="fts5",
            ))

    # Build semantic chunk results
    semantic_chunks: list[ChunkSearchResult] = []
    for rec in semantic_records:
        note = db.get_note(rec.id)
        title = note["title"] if note else rec.id
        semantic_chunks.append(ChunkSearchResult(
            file_id=rec.id,
            chunk_id=rec.chunk_id,
            text=rec.text,
            section_path=rec.section_path,
            title=title,
            source="semantic",
        ))

    # RRF fusion at chunk level
    fused: dict[tuple[str, int], float] = {}
    sources: dict[tuple[str, int], str] = {}

    for rank, chunk in enumerate(fts5_chunks):
        key = (chunk.file_id, chunk.chunk_id)
        fused[key] = fused.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
        sources[key] = "hybrid" if key in sources else "fts5"

    for rank, chunk in enumerate(semantic_chunks):
        key = (chunk.file_id, chunk.chunk_id)
        fused[key] = fused.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
        sources[key] = "hybrid" if key in sources else "semantic"

    # Score-based re-rank: combine RRF with cosine similarity
    query_vec = embed_result.vector
    reranked: list[tuple[tuple[str, int], float, str]] = []
    for key, rrf_score in fused.items():
        cos_sim = _cosine_similarity_for_key(key, semantic_records, query_vec)
        final_score = 0.6 * rrf_score + 0.4 * cos_sim
        reranked.append((key, final_score, sources[key]))

    reranked.sort(key=lambda x: x[1], reverse=True)

    # Build final results
    chunk_lookup: dict[tuple[str, int], ChunkSearchResult] = {}
    for chunk in fts5_chunks:
        chunk_lookup[(chunk.file_id, chunk.chunk_id)] = chunk
    for chunk in semantic_chunks:
        chunk_lookup[(chunk.file_id, chunk.chunk_id)] = chunk

    results: list[ChunkSearchResult] = []
    for key, score, source in reranked[:limit]:
        chunk = chunk_lookup.get(key)
        if chunk:
            results.append(ChunkSearchResult(
                file_id=chunk.file_id,
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                section_path=chunk.section_path,
                score=score,
                source=source,
                title=chunk.title,
            ))

    return results


def _cosine_similarity_for_key(
    key: tuple[str, int],
    semantic_records: list,
    query_vec: list[float],
) -> float:
    """Find cosine similarity for a chunk key from semantic records."""
    for rec in semantic_records:
        if (rec.id, rec.chunk_id) == key:
            return cosine_similarity(rec.vector, query_vec)
    return 0.0


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
